import pandas as pd
import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

market = ui.table("fct_market_daily")
demand = ui.table("fct_skill_demand_monthly")
skills = ui.table("dim_skill")
update = ui.optional_document("last_update.json")
status = ui.optional_document("status.json")
vacancies = ui.catalog()

pills = []
if status:
    runs = dd.run_states(status)
    if runs:
        pills.append(theme.pulse(runs))
    health = dd.health(status)
    pills.append(theme.pill(health[1], health[0]))
if update:
    pills.append(theme.pill(f"дані: {dd.stamp(update['exported_at'])}"))
ui.header(
    "Ринок праці IT·UA",
    "вакансії DOU і Djinni · навички · стеки · зарплати · оновлюється щодня",
    eyebrow="dataward / головна",
    pills=pills,
    typed=True,
)

totals = dd.market_totals(market)
last = totals.iloc[-1]
month = dd.latest_month(demand)
seen = int((demand.loc[demand["month"] == month, "vacancies"] > 0).sum())
ui.html(
    theme.stats(
        [
            ("Відкрито", dd.fmt_int(last["open_vacancies"])),
            ("Нових за день", dd.fmt_int(last["new_vacancies"])),
            ("Закрито за день", dd.fmt_int(last["closed_vacancies"])),
            ("Навичок", dd.fmt_int(seen)),
            ("Джерел", str(market["source"].nunique())),
        ]
    )
)
if len(totals) < 2:
    st.caption(
        "Це перший день спостереження: усі вакансії позначено «новими», бо раніше ми їх не бачили. "
        "Реальні нові й закриті з'являться з другого дня."
    )

# ---- the profile at a glance -----------------------------------------------------------------
mine = ui.profile()
ui.section("Мій профіль")
if mine.is_empty():
    st.caption(
        "Додайте свої навички: дашборд знайде вакансії, що вам підходять, складе план навчання, "
        "підкаже матеріали й дасть тренажер до співбесід. Жабка росте разом із вами."
    )
    st.page_link("views/profile.py", label="Створити профіль →")
else:
    fit = None
    if vacancies is not None and mine.known():
        fit = pr.readiness(pr.rank_vacancies(vacancies, mine))
    pet = ui.pet_state(mine)
    ui.html(
        theme.stats(
            [
                ("Рівень", str(pet["level"].level)),
                ("Серія", f"{pet['streak']} дн."),
                ("Знаю", str(len(mine.known()))),
                ("До повтору", str(pet["counts"]["due"])),
                ("Готовність", f"{fit:.0%}" if fit is not None else "—"),
            ]
        )
    )
    st.page_link("views/profile.py", label="Відкрити профіль →")

# ---- the breakdown panel: a metric split by source, level or direction -----------------------
ui.section("Динаміка")


@st.fragment
def breakdown_panel() -> None:
    """Only this panel reruns when a selector changes."""
    with ui.card(
        "Розріз ринку за днями", "тонкий стовпчик — один день; кольори — частини розрізу."
    ):
        left, middle, right = st.columns([3, 1, 1])
        metric = middle.selectbox("Показник", list(dd.METRICS), key="home_metric")
        split = right.selectbox("Розріз", list(dd.BREAKDOWNS), key="home_split")
        daily, order = dd.daily_breakdown(market, dd.METRICS[metric], dd.BREAKDOWNS[split])
        names, colours = charts.series_domain(order, keep_order=True)
        left.markdown("")
        ui.html(theme.legend(names, colours))
        ui.chart(charts.stacked_bars(daily, order=order, unit=metric))


breakdown_panel()

# ---- directions: the way into the catalog ---------------------------------------------------
directions = dd.direction_stats(market, vacancies)
ui.section("Напрямки")
st.caption("Найбільші напрямки за відкритими вакансіями. Кнопка відкриває вакансії цього напрямку.")
target = "views/catalog.py" if vacancies is not None else "views/market.py"
filter_key = "cat_dirs" if vacancies is not None else "mk_cats"
for start in range(0, len(directions), 4):
    for column, (n, row) in zip(
        st.columns(4),
        enumerate(directions.iloc[start : start + 4].itertuples(), start),
        strict=False,
    ):
        with column:
            ui.html(
                theme.direction_tile(
                    n % 4, row.category, dd.fmt_int(row.open), row.share, list(row.skills)
                )
            )
            st.button(
                "Вакансії →" if vacancies is not None else "Розріз →",
                key=f"dir_{n}",
                on_click=ui.open_with,
                args=(target, filter_key, [row.category]),
                width="stretch",
            )

# ---- skills -------------------------------------------------------------------------------
ui.section("Навички")
older = [m for m in dd.month_options(demand) if m < month]
ranking = dd.skill_ranking(demand, skills, ui.table("fct_salary_by_skill"), month=month,
                           previous=older[0] if older else None)  # fmt: skip
left, right = st.columns([3, 2])
with left, ui.card("Топ-10 навичок", f"частка вакансій місяця {month:%m.%Y}"):
    top = ranking.head(10).rename(columns={"canonical": "label", "share": "value"})
    ui.chart(charts.ranked_bars(top[["label", "value"]], fmt=".1%", unit="Частка вакансій"))
with right, ui.card("Що змінюється", "порівняння з минулим місяцем, в. п."):
    moved = ranking.dropna(subset=["change_pp"])
    if moved.empty:
        st.caption("Динаміка з'явиться, коли накопичиться другий місяць даних.")
    else:
        rising = moved.sort_values("change_pp", ascending=False).head(5)
        falling = moved.sort_values("change_pp").head(3)
        shown = pd.concat([rising, falling]).drop_duplicates("skill_id")
        st.dataframe(
            shown[["canonical", "change_pp"]].rename(
                columns={"canonical": "Навичка", "change_pp": "Зміна, п. п."}
            ),
            hide_index=True,
            column_config={"Зміна, п. п.": st.column_config.NumberColumn(format="%+.1f")},
        )

# ---- fresh vacancies (only where a catalog was built) --------------------------------------
if vacancies is not None:
    ui.section("Свіжі вакансії")
    fresh = dd.sort_catalog(dd.filter_catalog(vacancies, only_open=True), "Нові спочатку").head(6)
    for start in range(0, len(fresh), 3):
        for column, (n, (_, row)) in zip(
            st.columns(3), enumerate(fresh.iloc[start : start + 3].iterrows(), start), strict=False
        ):
            with column:
                ui.html(
                    theme.vacancy_tile(
                        n % 3,
                        str(row["title"]),
                        str(row["company"]),
                        dd.salary_label(row["salary_usd_min"], row["salary_usd_max"]),
                        list(row["skills"])[:4],
                    )
                )
                st.link_button("Відкрити ↗", str(row["url"]), width="stretch")
    st.page_link("views/catalog.py", label="Весь каталог з фільтрами →")
