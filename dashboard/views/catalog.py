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

head = st.container()  # the header goes here once the number of results is known

ADVANCED = ("cat_skill_mode", "cat_open", "cat_salary_only", "cat_min_salary", "cat_remote",
            "cat_since")  # fmt: skip
changed = sum(st.session_state[k] != DEFAULTS[k] for k in ADVANCED)
with st.container(key="cat_filters"):
    first, second, third = st.columns([3, 3, 3])
    query = first.text_input(
        "Назва або компанія", key="cat_q", placeholder="назва або компанія",
        label_visibility="collapsed", icon=":material/search:",
    )  # fmt: skip
    directions = second.multiselect(
        "Напрямок", dd.catalog_options(catalog, "category"), key="cat_dirs",
        placeholder="Усі напрямки", label_visibility="collapsed",
        format_func=lambda name: f"{name} ({category_counts.get(name, 0)})",
    )  # fmt: skip
    skills = third.multiselect(
        "Навички", dd.skill_options(catalog), key="cat_skills", placeholder="Будь-які навички",
        label_visibility="collapsed",
    )  # fmt: skip
    levels_col, sources_col, more_col, reset_col = st.columns(
        [4, 3, 2, 2], vertical_alignment="bottom"
    )
    with levels_col:
        ui.html('<div class="dw-fl">Рівень</div>')
        levels = st.pills(
            "Рівень", dd.catalog_options(catalog, "seniority"), selection_mode="multi",
            key="cat_levels", label_visibility="collapsed",
            format_func=lambda name: level_names.get(name, name),
        )  # fmt: skip
    with sources_col:
        ui.html('<div class="dw-fl">Джерело</div>')
        sources = st.pills(
            "Джерело", dd.catalog_options(catalog, "source"), selection_mode="multi",
            key="cat_sources", label_visibility="collapsed",
        )  # fmt: skip
    with more_col.popover(
        f"Ще фільтри{f' · {changed}' if changed else ''}", icon=":material/tune:", width="stretch"
    ):
        mode = st.radio(
            "Потрібні навички", ["усі", "будь-яка"], key="cat_skill_mode", horizontal=True
        )
        only_open = st.toggle("Лише відкриті", key="cat_open")
        with_salary = st.toggle("Лише з вилкою", key="cat_salary_only")
        remote_only = st.toggle("Лише віддалено", key="cat_remote")
        top_salary = int(catalog["salary_top"].max()) if catalog["salary_top"].notna().any() else 0
        min_salary = (
            st.slider("Зарплата від, USD/міс", 0, top_salary, step=100, key="cat_min_salary")
            if top_salary > 0
            else 0
        )
        since = st.selectbox("З'явилась", list(SINCE), key="cat_since")
    reset_col.button(
        "Скинути", on_click=reset_filters, icon=":material/restart_alt:", width="stretch"
    )

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

chosen = [
    ("Пошук", query.strip()) if query.strip() else None,
    ("Напрямок", dd.short_list(directions)) if directions else None,
    ("Рівень", dd.short_list([level_names.get(x, x) for x in levels])) if levels else None,
    ("Навички", f"{dd.short_list(skills, 3)} ({mode})") if skills else None,
    ("Статус", "відкриті") if only_open else None,
    ("Зарплата", f"від {min_salary} $") if min_salary else None,
    ("Зарплата", "є вилка") if with_salary and not min_salary else None,
    ("Формат", "віддалено") if remote_only else None,
    ("З'явилась", since) if SINCE[since] else None,
    ("Джерело", dd.short_list(sources)) if sources else None,
]
active = [pair for pair in chosen if pair]

with head:
    ui.header(
        "Каталог вакансій",
        "Шукайте за напрямком, рівнем, навичками й зарплатою. Клік по рядку відкриває вакансію.",
        eyebrow="вакансії · каталог",
        pills=[theme.pill(f"{dd.fmt_int(len(result))} з {dd.fmt_int(len(catalog))}")],
        domain="jobs",
    )

ui.html(theme.active_filters(active))

if result.empty:
    st.info("За цими фільтрами вакансій немає: послабте умови або натисніть «Скинути».")
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
    demand, skill_table = ui.table("fct_skill_demand_monthly"), ui.table("dim_skill")
    shares = dd.skill_shares(demand, skill_table, month=dd.latest_month(demand))
    ui.vacancy_list(result, key="cat", profile=ui.profile(), catalog=catalog, shares=shares)

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
