import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

market = ui.table("fct_market_daily")
demand = ui.table("fct_skill_demand_monthly")
skills = ui.table("dim_skill")
update = ui.optional_document("last_update.json")
status = ui.optional_document("status.json")

pills = []
if update:
    pills.append(theme.pill(f"дані: {dd.stamp(update['exported_at'])}"))
health = dd.health(status) if status else None
if health:
    pills.append(theme.pill(health[1], health[0]))
ui.header(
    "Ринок праці в ІТ України",
    "Вакансії DOU і Djinni: скільки їх, яких навичок вимагають, що з чим поєднується і скільки "
    "платять. Дані оновлюються щодня.",
    eyebrow="Dataward · головна",
    pills=pills,
)

totals = dd.market_totals(market)
last = totals.iloc[-1]
before = totals.iloc[-2] if len(totals) > 1 else None


def change(column: str) -> str | None:
    return None if before is None else f"{int(last[column] - before[column]):+d}"


def history(column: str) -> list[float]:
    return totals[column].tail(30).astype(float).tolist()


month = dd.latest_month(demand)
top = dd.top_skills(demand, skills, month=month, n=10)
seen = int((demand.loc[demand["month"] == month, "vacancies"] > 0).sum())

ui.section("Показники")
row1 = st.columns(3)
with row1[0]:
    ui.kpi(
        1, "Відкриті вакансії", dd.fmt_int(last["open_vacancies"]), delta=change("open_vacancies"),
        history=history("open_vacancies"), help="Сума по DOU і Djinni на останній день.",
    )  # fmt: skip
with row1[1]:
    ui.kpi(
        2, "Нові за день", dd.fmt_int(last["new_vacancies"]), delta=change("new_vacancies"),
        history=history("new_vacancies"),
    )  # fmt: skip
with row1[2]:
    ui.kpi(
        3, "Закриті за день", dd.fmt_int(last["closed_vacancies"]),
        delta=change("closed_vacancies"), history=history("closed_vacancies"),
        direction="neutral",
    )  # fmt: skip
row2 = st.columns(3)
with row2[0]:
    ui.kpi(
        4, "Навичок у вакансіях", dd.fmt_int(seen), delta=f"за {month:%m.%Y}", direction="neutral"
    )
with row2[1]:
    if top.empty:
        ui.kpi(5, "Найпопулярніша навичка", "—")
    else:
        leader = top.iloc[0]
        ui.kpi(
            5, "Найпопулярніша навичка", str(leader["canonical"]),
            delta=f"{leader['share'] * 100:.1f}% вакансій", direction="neutral",
        )  # fmt: skip
with row2[2]:
    if health:
        ui.kpi(6, "Стан пайплайну", health[1], delta=health[2], direction="neutral")
    else:
        ui.kpi(6, "Стан пайплайну", "—", delta="немає status.json", direction="neutral")

if before is None:
    st.caption(
        "Це перший день спостереження: усі вакансії позначено «новими», бо раніше ми їх не бачили. "
        "Реальні нові й закриті з'являться з другого дня."
    )

ui.section("Динаміка та навички")
left, right = st.columns([3, 2])
with left, ui.card("Відкриті вакансії за днями", "DOU і Djinni рахуються окремо."):
    ui.chart(charts.lines(dd.open_by_day(market)))
top_note = (
    f"частка вакансій місяця {month:%m.%Y}. Серед категорій багато нетехнічних (маркетинг, "
    "продажі, підтримка), тому CRM чи Google Ads теж у топі; словник частково їх завищує "
    "(docs/metrics.md)."
)
with right, ui.card("Топ-10 навичок", top_note):
    ui.chart(
        charts.ranked_bars(
            top.rename(columns={"canonical": "label", "share": "value"})[["label", "value"]],
            fmt=".1%",
            unit="Частка вакансій",
        )  # fmt: skip
    )

ui.section("Розріз ринку")
left, right = st.columns(2)
with left, ui.card("Категорії", "відкриті вакансії на останній день"):
    by_category = dd.open_by_category(market, top=10)
    ui.chart(
        charts.ranked_bars(
            by_category.rename(columns={"category": "label", "open_vacancies": "value"}),
            unit="Відкритих вакансій",
        )
    )
with right, ui.card("Рівні", "відкриті вакансії на останній день"):
    by_level = dd.open_by_seniority(market)
    ui.chart(
        charts.ranked_bars(
            by_level.rename(columns={"seniority": "label", "open_vacancies": "value"}),
            unit="Відкритих вакансій",
        )
    )

vacancies = ui.catalog()
if vacancies is not None:
    ui.section("Свіжі вакансії")
    fresh = dd.sort_catalog(dd.filter_catalog(vacancies, only_open=True), "Нові спочатку").head(8)
    st.dataframe(
        dd.catalog_table(fresh)[
            ["Назва", "Компанія", "Напрямок", "Рівень", "Зарплата", "Посилання"]
        ],
        hide_index=True,
        column_config={
            "Посилання": st.column_config.LinkColumn("Посилання", display_text="відкрити ↗"),
            "Назва": st.column_config.TextColumn(width="large"),
        },
    )
    st.page_link("views/catalog.py", label="Весь каталог з фільтрами →")

ui.section("Куди далі")
tiles = [
    ("views/catalog.py", "Каталог", "Вакансії списком: напрямок, рівень, навички, зарплата."),
    ("views/market.py", "Ринок", "Динаміка, категорії, рівні й таблиця з вакансіями за днями."),
    ("views/skills.py", "Навички", "Рейтинг, одна навичка докладно, стеки, що йдуть разом."),
    ("views/salary.py", "Зарплати", "Калькулятор, орієнтири DOU, зарплати за навичками."),
    ("views/system.py", "Стан і дані", "Чи здорові дані, перевірки якості, звідки вони."),
]
for column, (page, title, text) in zip(st.columns(len(tiles)), tiles, strict=True):
    with column, st.container(border=True):
        st.page_link(page, label=f"{title} →")
        st.caption(text)
