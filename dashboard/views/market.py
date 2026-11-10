import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

ui.header(
    "Ринок",
    "Скільки вакансій відкрито, скільки з'являється і зникає, в яких напрямках і для якого рівня.",
    eyebrow="аналітика / ринок",
    domain="market",
)

market = ui.table("fct_market_daily")

DEFAULTS: dict[str, list[str]] = {"mk_sources": [], "mk_levels": [], "mk_cats": []}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, list(value))


def reset_filters() -> None:
    for name, default in DEFAULTS.items():
        st.session_state[name] = list(default)


level_names = {dd.NO_LEVEL: "не вказано"}

ui.section("Фільтри")
with st.container(border=True):
    one, two, three = st.columns([2, 5, 3])
    with one:
        ui.html('<div class="dw-fl">Джерело</div>')
        sources = st.pills(
            "Джерело", sorted(market["source"].unique()), selection_mode="multi",
            key="mk_sources", label_visibility="collapsed",
        )  # fmt: skip
    with two:
        ui.html('<div class="dw-fl">Рівень</div>')
        levels = st.pills(
            "Рівень", sorted(market["seniority"].unique()), selection_mode="multi",
            key="mk_levels", label_visibility="collapsed",
            format_func=lambda name: level_names.get(name, name),
        )  # fmt: skip
    with three:
        ui.html('<div class="dw-fl">Напрямок</div>')
        categories = st.multiselect(
            "Напрямок", sorted(market["category"].unique()), key="mk_cats",
            placeholder="Усі напрямки", label_visibility="collapsed",
        )  # fmt: skip

chosen = [
    ("Джерело", dd.short_list(sources)) if sources else None,
    ("Рівень", dd.short_list([level_names.get(x, x) for x in levels])) if levels else None,
    ("Напрямок", dd.short_list(categories)) if categories else None,
]
active = [pair for pair in chosen if pair]
ui.html(theme.active_filters(active))
if active:
    st.button("Скинути фільтри", on_click=reset_filters)

selected = dd.filter_market(market, sources=sources, categories=categories, seniorities=levels)
if selected.empty:
    st.info("За вибраними фільтрами вакансій немає.")
    st.stop()

totals = dd.market_totals(selected)
last = totals.iloc[-1]
before = totals.iloc[-2] if len(totals) > 1 else None


def change(column: str) -> str | None:
    return None if before is None else f"{int(last[column] - before[column]):+d}"


ui.section("Показники за останній день")
one, two, three = st.columns(3)
with one:
    ui.kpi(
        1, "Відкриті вакансії", int(last["open_vacancies"]), delta=change("open_vacancies"),
        history=totals["open_vacancies"].astype(float).tolist(),
    )  # fmt: skip
with two:
    ui.kpi(
        2, "Нові за день", int(last["new_vacancies"]), delta=change("new_vacancies"),
        history=totals["new_vacancies"].astype(float).tolist(),
    )  # fmt: skip
with three:
    ui.kpi(
        3, "Закриті за день", int(last["closed_vacancies"]), delta=change("closed_vacancies"),
        history=totals["closed_vacancies"].astype(float).tolist(), direction="neutral",
    )  # fmt: skip
if selected["date"].max() == market["date"].min():
    st.caption(
        "Це перший день спостереження: усі вакансії позначено «новими», бо раніше ми їх не бачили. "
        "Реальні нові й закриті з'являться з другого дня."
    )

st.write("")
dynamics, vacancies_tab, categories_tab, levels_tab, table_tab = st.tabs(
    ["Динаміка", "Вакансії", "Напрямки", "Рівні", "Таблиця"], on_change="rerun", key="market_tab"
)
# only the open tab is built, so the charts of the closed ones cost nothing; Streamlit forgets a
# widget it did not draw, so the selectors of a closed tab are kept by hand
ui.keep("mk_metric", "mk_split", "mkt_sort")

with dynamics:
    if dynamics.open:

        @st.fragment
        def breakdown_panel() -> None:
            """Only this panel reruns when a selector changes."""
            title = "Розріз за днями"
            with ui.card(title, "тонкий стовпчик — один день; кольори — частини розрізу."):
                pick_metric, pick_split = st.columns(2)
                metric = pick_metric.selectbox("Показник", list(dd.METRICS), key="mk_metric")
                split = pick_split.selectbox("Розріз", list(dd.BREAKDOWNS), key="mk_split")
                daily, order = dd.daily_breakdown(
                    selected, dd.METRICS[metric], dd.BREAKDOWNS[split]
                )
                names, colours = charts.series_domain(order, keep_order=True)
                ui.html(theme.legend(names, colours))
                ui.chart(charts.stacked_bars(daily, order=order, unit=metric))

        breakdown_panel()
        flow = totals.melt(
            id_vars="date", value_vars=["new_vacancies", "closed_vacancies"], var_name="series"
        ).replace({"new_vacancies": "Нові", "closed_vacancies": "Закриті"})
        started = selected["date"].min() == market["date"].min() and len(totals) > 1
        flow_note = "скільки вакансій з'явилося і скільки зникло з сайтів."
        if started:
            flow_note += " Перші дні завищують «нові»: збір почався з порожньої бази."
        with ui.card("Нові й закриті за днями", flow_note):
            ui.html(theme.legend(["Нові", "Закриті"], list(theme.SERIES[:2])))
            ui.chart(charts.grouped_columns(flow, order=["Нові", "Закриті"]))

with vacancies_tab:
    if vacancies_tab.open:
        vacancies = ui.catalog()
        if vacancies is None:
            ui.no_catalog("Список вакансій береться з каталогу.")
        else:
            demand, skill_table = ui.table("fct_skill_demand_monthly"), ui.table("dim_skill")
            st.caption(
                "Вакансії за фільтрами ринку. Перша вже відкрита праворуч, клік по рядку "
                "відкриває іншу: оголошення, порівняння з ринком."
            )
            ui.listing_note()
            ui.vacancy_list(
                dd.filter_catalog(
                    vacancies, categories=categories, levels=levels, sources=sources,
                    only_open=True,
                ),
                key="mkt", profile=ui.owner_profile(), catalog=vacancies,
                shares=dd.skill_shares(demand, skill_table, month=dd.latest_month(demand)),
            )  # fmt: skip

with categories_tab:
    if categories_tab.open:
        by_category = dd.open_by_category(selected, top=15)
        with ui.card("Напрямки", "відкриті вакансії на останній день, найбільші зверху."):
            ui.chart(
                charts.ranked_bars(
                    by_category.rename(columns={"category": "label", "open_vacancies": "value"}),
                    unit="Відкритих вакансій",
                )
            )

with levels_tab:
    if levels_tab.open:
        by_level = dd.open_by_seniority(selected)
        with ui.card("Рівні", "відкриті вакансії на останній день."):
            ui.chart(
                charts.ranked_bars(
                    by_level.rename(columns={"seniority": "label", "open_vacancies": "value"}),
                    unit="Відкритих вакансій",
                )
            )

with table_tab:
    if table_tab.open:
        shown = selected.sort_values(
            ["date", "open_vacancies"], ascending=[False, False]
        ).rename(
            columns={
                "date": "Дата", "source": "Джерело", "category": "Напрямок",
                "seniority": "Рівень", "open_vacancies": "Відкриті", "new_vacancies": "Нові",
                "closed_vacancies": "Закриті",
            }
        )  # fmt: skip
        st.caption(
            f"{len(shown):,} рядків за вибраними фільтрами; клік по заголовку сортує колонку."
        )
        st.dataframe(shown, hide_index=True, height=420)
        st.download_button(
            "Завантажити CSV",
            shown.to_csv(index=False).encode("utf-8"),
            file_name="dataward_market.csv",
            mime="text/csv",
        )
