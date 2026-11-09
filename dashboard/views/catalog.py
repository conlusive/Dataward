from datetime import timedelta

import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

catalog = ui.catalog()
if catalog is None:
    ui.header(
        "Каталог вакансій",
        "Список вакансій з фільтрами за напрямком, рівнем, навичками й зарплатою.",
        eyebrow="вакансії · каталог",
    )
    st.info(
        "У цьому експорті каталогу немає. Це навмисно: вакансії належать іншим людям, тому каталог "
        "не потрапляє в публічний артефакт CI. Щоб побачити його, збудуйте експорт у себе: "
        "`make pipeline` (або `make dbt-build` і `make export` для вже наявної бази)."
    )
    st.stop()

SINCE = {"будь-коли": 0, "за 1 день": 1, "за 3 дні": 3, "за 7 днів": 7, "за 30 днів": 30}
DEFAULTS: dict[str, object] = {
    "cat_q": "", "cat_dirs": [], "cat_levels": [], "cat_sources": [], "cat_skills": [],
    "cat_skill_mode": "усі", "cat_salary_only": False, "cat_min_salary": 0, "cat_remote": False,
    "cat_open": True, "cat_since": "будь-коли",
}  # fmt: skip
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, list(value) if isinstance(value, list) else value)


def reset_filters() -> None:
    for name, default in DEFAULTS.items():
        st.session_state[name] = list(default) if isinstance(default, list) else default


category_counts = catalog["category"].value_counts()
level_names = {dd.NO_LEVEL: "не вказано"}

with st.sidebar:
    ui.sidebar_label("Пошук")
    query = st.text_input("Назва або компанія", key="cat_q", placeholder="наприклад: python senior")
    ui.sidebar_label("Напрямок і рівень")
    directions = st.multiselect(
        "Напрямок",
        dd.catalog_options(catalog, "category"),
        key="cat_dirs",
        placeholder="Усі напрямки",
        format_func=lambda name: f"{name} ({category_counts.get(name, 0)})",
    )
    levels = st.multiselect(
        "Рівень",
        dd.catalog_options(catalog, "seniority"),
        key="cat_levels",
        placeholder="Усі рівні",
        format_func=lambda name: level_names.get(name, name),
    )
    ui.sidebar_label("Навички")
    skills = st.multiselect(
        "Навички", dd.skill_options(catalog), key="cat_skills", placeholder="Будь-які"
    )
    mode = st.radio("Потрібні", ["усі", "будь-яка"], key="cat_skill_mode", horizontal=True)
    ui.sidebar_label("Умови")
    only_open = st.toggle("Лише відкриті", key="cat_open")
    with_salary = st.toggle("Лише з вилкою", key="cat_salary_only")
    top_salary = int(catalog["salary_top"].max()) if catalog["salary_top"].notna().any() else 0
    min_salary = (
        st.slider("Зарплата від, USD/міс", 0, top_salary, step=100, key="cat_min_salary")
        if top_salary > 0
        else 0
    )
    remote_only = st.toggle("Лише віддалено", key="cat_remote")
    since = st.selectbox("З'явилась", list(SINCE), key="cat_since")
    sources = st.multiselect(
        "Джерело", dd.catalog_options(catalog, "source"), key="cat_sources", placeholder="Усі"
    )
    st.button("Скинути фільтри", on_click=reset_filters, width="stretch")

latest = catalog["first_listed_on"].max()
result = dd.filter_catalog(
    catalog,
    query=query,
    categories=directions,
    levels=levels,
    sources=sources,
    skills=skills,
    all_skills=mode == "усі",
    only_open=only_open,
    with_salary=with_salary,
    min_salary=min_salary,
    remote_only=remote_only,
    listed_since=latest - timedelta(days=SINCE[since] - 1) if SINCE[since] else None,
)

ui.header(
    "Каталог вакансій",
    "Шукайте за напрямком, рівнем, навичками й зарплатою: фільтри зліва, список нижче. "
    "Клік по рядку відкриває вакансію докладно.",
    eyebrow="вакансії · каталог",
    pills=[theme.pill(f"{dd.fmt_int(len(result))} з {dd.fmt_int(len(catalog))}")],
)

if result.empty:
    st.info("За цими фільтрами вакансій немає: послабте умови або натисніть «Скинути фільтри».")
    st.stop()

paid = int(result["salary_top"].notna().sum())
median = dd.median_salary(result)
ui.section("Вибірка")
one, two, three, four = st.columns(4)
with one:
    ui.kpi(
        1, "Знайдено", dd.fmt_int(len(result)), delta=f"з {dd.fmt_int(len(catalog))}",
        direction="neutral",
    )  # fmt: skip
with two:
    ui.kpi(
        2, "З вилкою", dd.fmt_int(paid), delta=f"{paid / len(result):.0%} вибірки",
        direction="neutral",
    )  # fmt: skip
with three:
    ui.kpi(
        3, "Медіана вилки", dd.fmt_int(median) if median else "—",
        delta="USD на місяць" if median else "зарплат у вибірці немає",
        direction="neutral",
    )  # fmt: skip
with four:
    ui.kpi(
        4, "Нові за 7 днів", dd.fmt_int(dd.listed_within(result, 7)),
        delta=f"{dd.listed_within(result, 7) / len(result):.0%} вибірки", direction="neutral",
    )  # fmt: skip

st.write("")
list_tab, skills_tab, companies_tab = st.tabs(["Вакансії", "Що вимагають", "Компанії"])

with list_tab:
    sort = st.selectbox("Сортування", list(dd.SORTS), key="cat_sort")
    ordered = dd.sort_catalog(result, sort).reset_index(drop=True)
    table = dd.catalog_table(ordered)
    event = st.dataframe(
        table,
        hide_index=True,
        height=520,
        key="cat_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Посилання": st.column_config.LinkColumn("Посилання", display_text="відкрити ↗"),
            "Назва": st.column_config.TextColumn(width=320),
            "Компанія": st.column_config.TextColumn(width=170),
            "Напрямок": st.column_config.TextColumn(width=150),
            "Рівень": st.column_config.TextColumn(width=90),
            "Зарплата": st.column_config.TextColumn(width=140),
            "Навички": st.column_config.TextColumn(width=340),
            "Де": st.column_config.TextColumn(width=170),
            "Джерело": st.column_config.TextColumn(width=90),
            "З'явилась": st.column_config.DateColumn(format="DD.MM.YYYY"),
        },
    )
    picked = event.selection.rows
    with st.container(border=True):
        if picked and picked[0] < len(ordered):
            ui.vacancy_card(ordered.iloc[picked[0]])
        else:
            st.markdown(
                '<div class="dw-muted">▸ Клікніть рядок у таблиці, щоб побачити вакансію '
                "докладно: усі навички (з позначкою вимог), дати й посилання.</div>",
                unsafe_allow_html=True,
            )
    st.download_button(
        "Завантажити CSV",
        table.to_csv(index=False).encode("utf-8"),
        file_name="dataward_vacancies.csv",
        mime="text/csv",
    )

with skills_tab:
    counts = dd.skill_counts(result, top=15)
    with ui.card("Що вимагають у цій вибірці", f"частка серед {len(result)} вакансій вибірки."):
        if counts.empty:
            st.caption("У вакансіях цієї вибірки не знайдено навичок.")
        else:
            ui.chart(
                charts.ranked_bars(
                    counts.rename(columns={"skill": "label", "share": "value"})[["label", "value"]],
                    fmt=".0%",
                    unit="Частка вакансій вибірки",
                )  # fmt: skip
            )

with companies_tab:
    companies = dd.company_counts(result, top=15)
    with ui.card("Компанії з найбільшою кількістю вакансій у вибірці"):
        if companies.empty:
            st.caption("У вакансіях цієї вибірки немає назв компаній.")
        else:
            ui.chart(
                charts.ranked_bars(
                    companies.rename(columns={"company": "label", "vacancies": "value"}),
                    unit="Вакансій",
                )
            )
