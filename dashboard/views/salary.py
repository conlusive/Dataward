import pandas as pd
import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

ui.header(
    "Зарплати",
    "Скільки платять: калькулятор за моделлю, орієнтири опитування DOU, зарплати в вакансіях "
    "за навичками і скільки вакансія лишається відкритою.",
    eyebrow="Аналітика · зарплати",
    domain="market",
)

survey = ui.table("fct_salary_survey")
lifetime = ui.table("fct_vacancy_lifetime")
salary = ui.table("fct_salary_by_skill")
skills = ui.table("dim_skill")

calculator, benchmarks, by_skill, open_time = st.tabs(
    ["Калькулятор", "Орієнтири DOU", "За навичками", "Тривалість вакансій"]
)

# ---- the calculator: the model's p10-p50-p90 for a profile -----------------------------------
with calculator:
    loaded = dd.read_grid(dd.data_dir())
    if loaded is None:
        st.info("Модель ще не навчена. Запустіть `make train`, і тут з'явиться калькулятор.")
    else:
        grid, info = loaded
        a, b = st.columns(2)
        role_choice = a.selectbox("Роль", sorted(grid["role"].unique()), key="calc_role")
        level_choice = b.selectbox(
            "Рівень",
            sorted(grid.loc[grid["role"] == role_choice, "seniority"].unique()),
            key="calc_level",
        )
        c, d, e = st.columns(3)
        experience = c.slider("Досвід, років", 0.0, 15.0, 3.0, 0.5, key="calc_experience")
        english = d.selectbox("Англійська", sorted(grid["english"].unique()), key="calc_english")
        city = e.selectbox("Де працює", sorted(grid["city_group"].unique()), key="calc_city")
        found = dd.grid_lookup(
            grid, role=role_choice, seniority=level_choice, experience=experience,
            english=english, city_group=city,
        )  # fmt: skip
        if found is None:
            st.info("Для такого поєднання в опитуванні замало відповідей.")
        else:
            low, mid, high = st.columns(3)
            with low:
                ui.kpi(1, "Нижня межа (p10), USD/міс", dd.fmt_int(found["p10"]))
            with mid:
                ui.kpi(2, "Типова (p50), USD/міс", dd.fmt_int(found["p50"]))
            with high:
                ui.kpi(3, "Верхня межа (p90), USD/міс", dd.fmt_int(found["p90"]))
            profile = pd.DataFrame(
                {"label": ["Ваш профіль"], "low": [found["p10"]], "mid": [found["p50"]],
                 "high": [found["p90"]]}
            )  # fmt: skip
            with ui.card("Діапазон", "від p10 до p90; точка — типова зарплата."):
                ui.chart(charts.ranges(profile, height=110))
            year = info["tested_on_year"]
            mae, plain = info["model"]["mae"], info["baseline"]["mae"]
            inside = info["model"]["coverage_10_90"]
            ui.explain(
                "Діапазон p10–p90 має вміщати 8 з 10 людей із таким профілем. Модель перевірено на "
                f"опитуваннях {year} року, яких вона не бачила: типова помилка {mae:.0f} USD "
                f"(проста медіана за роллю й досвідом помиляється на {plain:.0f}), реальна "
                f"зарплата потрапляла в діапазон у {inside:.0%} випадків. Це самозвіт учасників "
                "опитування, а не пропозиції роботодавців; кореляція, не причинність."
            )

# ---- survey benchmarks -----------------------------------------------------------------------
with benchmarks:
    ui.explain("Чисті зарплати, USD на місяць; відповіді зважено за кількістю респондентів.")
    if survey.empty:
        st.info("Замало відповідей для надійних орієнтирів.")
    else:
        left, right = st.columns(2)
        role = left.selectbox("Роль", sorted(survey["role"].unique()), key="survey_role")
        in_role = survey[survey["role"] == role]
        levels = sorted(in_role["seniority"].unique())
        named = in_role[in_role["seniority"] != "unknown"]
        biggest = (
            (named if not named.empty else in_role)
            .groupby("seniority")["respondents"]
            .sum()
            .idxmax()
        )
        level = right.selectbox(
            "Рівень",
            ["усі", *levels],
            index=levels.index(biggest) + 1,
            key="survey_level",
            format_func=lambda value: {"unknown": "не вказано"}.get(value, value),
        )
        bench = dd.survey_benchmark(survey, role=role, seniority=None if level == "усі" else level)
        if bench.empty:
            st.info("Для цієї комбінації відповідей замало.")
        else:
            newest = bench.iloc[0]
            a, b, c = st.columns(3)
            with a:
                ui.kpi(1, f"p25 ({int(newest['survey_year'])})", dd.fmt_int(newest["salary_p25"]))
            with b:
                ui.kpi(2, "Медіана", dd.fmt_int(newest["salary_median"]))
            with c:
                ui.kpi(3, "p75", dd.fmt_int(newest["salary_p75"]))
            if level != "усі" and bench["survey_year"].nunique() > 1:
                years = bench.sort_values("survey_year").rename(
                    columns={
                        "survey_year": "year", "salary_p25": "low", "salary_median": "mid",
                        "salary_p75": "high",
                    }
                )  # fmt: skip
                with ui.card("Медіана за роками", "смуга — від p25 до p75."):
                    ui.chart(charts.survey_band(years[["year", "low", "mid", "high"]]))
            elif level == "усі":
                st.caption("Оберіть один рівень, щоб побачити динаміку за роками.")
            st.dataframe(
                bench.rename(
                    columns={
                        "survey_year": "Рік",
                        "seniority": "Рівень",
                        "respondents": "Респондентів",
                        "salary_p25": "p25",
                        "salary_median": "Медіана",
                        "salary_p75": "p75",
                    }
                ),  # fmt: skip
                hide_index=True,
                height=320,
            )

# ---- declared salaries by skill --------------------------------------------------------------
with by_skill:
    ui.explain(
        "Зарплата з вакансій, де її вказано (вибірка зміщена). Навичок із надто малою кількістю "
        "таких вакансій тут немає."
    )
    top_count = int(salary["vacancies_with_salary"].max()) if not salary.empty else 0
    floor = 1
    if top_count > 1:
        floor = st.slider(
            "Мінімум вакансій із вилкою", 1, top_count, min(5, top_count), key="salary_floor"
        )
    ranked = dd.salary_ranking(salary, skills, min_vacancies=floor)
    if ranked.empty:
        st.info("Немає навичок із достатньою кількістю вакансій із зарплатою.")
    else:
        shown = ranked.head(15).rename(
            columns={"canonical": "label", "salary_p25": "low", "salary_median": "mid",
                     "salary_p75": "high"}
        )  # fmt: skip
        with ui.card("Найвища медіана", "від p25 до p75; точка — медіана."):
            ui.chart(charts.ranges(shown[["label", "low", "mid", "high"]]))
        st.dataframe(
            ranked.rename(
                columns={
                    "canonical": "Навичка",
                    "category": "Група",
                    "vacancies_with_salary": "Вакансій із вилкою",
                    "salary_p25": "p25",
                    "salary_median": "Медіана",
                    "salary_p75": "p75",
                }
            ),  # fmt: skip
            hide_index=True,
            height=380,
            column_config={
                "p25": st.column_config.NumberColumn(format="%d"),
                "Медіана": st.column_config.NumberColumn(format="%d"),
                "p75": st.column_config.NumberColumn(format="%d"),
            },
        )

# ---- how long a vacancy stays open -----------------------------------------------------------
with open_time:
    if lifetime.empty:
        st.info("Історії ще замало: тривалість рахується за закритими вакансіями.")
    else:
        days = lifetime.rename(
            columns={"seniority": "label", "lifetime_p25": "low", "lifetime_median": "mid",
                     "lifetime_p75": "high"}
        )  # fmt: skip
        with ui.card(
            "Скільки вакансія лишається відкритою", "дні; від p25 до p75, точка — медіана."
        ):
            ui.chart(charts.ranges(days[["label", "low", "mid", "high"]], unit="днів"))
        st.dataframe(
            lifetime.rename(
                columns={
                    "seniority": "Рівень",
                    "closed_vacancies": "Закритих вакансій",
                    "lifetime_p25": "p25, днів",
                    "lifetime_median": "Медіана, днів",
                    "lifetime_p75": "p75, днів",
                }
            ),  # fmt: skip
            hide_index=True,
        )

ui.explain(
    "Опитування — це самозвіт респондентів, а не пропозиції роботодавців; "
    "кореляція, не причинність."
)
