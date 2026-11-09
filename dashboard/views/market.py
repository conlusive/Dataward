import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

ui.header(
    "Ринок",
    "Скільки вакансій відкрито, скільки з'являється і зникає, в яких категоріях і для якого рівня.",
    eyebrow="Аналітика · ринок",
)

market = ui.table("fct_market_daily")

ui.section("Фільтри")
left, middle, right = st.columns(3)
sources = left.multiselect("Джерело", sorted(market["source"].unique()), placeholder="Усі")
categories = middle.multiselect("Категорія", sorted(market["category"].unique()), placeholder="Усі")
levels = right.multiselect("Рівень", sorted(market["seniority"].unique()), placeholder="Усі")

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
dynamics, categories_tab, levels_tab, table_tab = st.tabs(
    ["Динаміка", "Категорії", "Рівні", "Таблиця"]
)

with dynamics:
    with ui.card("Відкриті вакансії за днями", "DOU і Djinni рахуються окремо."):
        ui.chart(charts.lines(dd.open_by_day(selected)))
    flow = totals.melt(
        id_vars="date", value_vars=["new_vacancies", "closed_vacancies"], var_name="series"
    ).replace({"new_vacancies": "Нові", "closed_vacancies": "Закриті"})
    with ui.card(
        "Нові й закриті за днями", "скільки вакансій з'явилося і скільки зникло з сайтів."
    ):
        ui.chart(charts.grouped_columns(flow, order=["Нові", "Закриті"]))

by_category = dd.open_by_category(selected, top=15)
with categories_tab, ui.card("Категорії", "відкриті вакансії на останній день, найбільші зверху."):
    ui.chart(
        charts.ranked_bars(
            by_category.rename(columns={"category": "label", "open_vacancies": "value"}),
            unit="Відкритих вакансій",
        )
    )

with levels_tab:
    by_level = dd.open_by_seniority(selected)
    with ui.card("Рівні", "відкриті вакансії на останній день."):
        ui.chart(
            charts.ranked_bars(
                by_level.rename(columns={"seniority": "label", "open_vacancies": "value"}),
                unit="Відкритих вакансій",
            )
        )

with table_tab:
    shown = selected.sort_values(["date", "open_vacancies"], ascending=[False, False]).rename(
        columns={
            "date": "Дата", "source": "Джерело", "category": "Категорія", "seniority": "Рівень",
            "open_vacancies": "Відкриті", "new_vacancies": "Нові", "closed_vacancies": "Закриті",
        }
    )  # fmt: skip
    st.caption(f"{len(shown):,} рядків за вибраними фільтрами; клік по заголовку сортує колонку.")
    st.dataframe(shown, hide_index=True, height=420)
    st.download_button(
        "Завантажити CSV",
        shown.to_csv(index=False).encode("utf-8"),
        file_name="dataward_market.csv",
        mime="text/csv",
    )
