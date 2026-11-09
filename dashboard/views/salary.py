import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

st.title("Зарплати")

survey = ui.table("fct_salary_survey")
lifetime = ui.table("fct_vacancy_lifetime")

st.subheader("Калькулятор зарплати")
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
        low.metric("Нижня межа (p10), USD/міс", f"{found['p10']:.0f}")
        mid.metric("Типова (p50), USD/міс", f"{found['p50']:.0f}")
        high.metric("Верхня межа (p90), USD/міс", f"{found['p90']:.0f}")
        year = info["tested_on_year"]
        mae, plain = info["model"]["mae"], info["baseline"]["mae"]
        inside = info["model"]["coverage_10_90"]
        st.caption(
            "Діапазон p10–p90 має вміщати 8 з 10 людей із таким профілем. Модель перевірено на "
            f"опитуваннях {year} року, яких вона не бачила: типова помилка {mae:.0f} USD (проста "
            f"медіана за роллю й досвідом помиляється на {plain:.0f}), реальна зарплата потрапляла "
            f"в діапазон у {inside:.0%} випадків. Це самозвіт учасників опитування, а не "
            "пропозиції роботодавців; кореляція, не причинність."
        )

st.subheader("Орієнтири за опитуванням DOU")
st.caption("Чисті зарплати, USD на місяць; відповіді зважено за кількістю респондентів.")

if survey.empty:
    st.info("Замало відповідей для надійних орієнтирів.")
else:
    left, right = st.columns(2)
    role = left.selectbox("Роль", sorted(survey["role"].unique()))
    levels = sorted(survey.loc[survey["role"] == role, "seniority"].unique())
    level = right.selectbox("Рівень", ["усі", *levels])
    bench = dd.survey_benchmark(survey, role=role, seniority=None if level == "усі" else level)
    if bench.empty:
        st.info("Для цієї комбінації відповідей замало.")
    else:
        newest = bench.iloc[0]
        a, b, c = st.columns(3)
        a.metric(f"p25 ({int(newest['survey_year'])})", f"{newest['salary_p25']:.0f}")
        b.metric("Медіана", f"{newest['salary_median']:.0f}")
        c.metric("p75", f"{newest['salary_p75']:.0f}")
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
            ),
            hide_index=True,
        )

st.subheader("Скільки вакансія лишається відкритою")
if lifetime.empty:
    st.info("Історії ще замало: тривалість рахується за закритими вакансіями.")
else:
    st.dataframe(
        lifetime.rename(
            columns={
                "seniority": "Рівень",
                "closed_vacancies": "Закритих вакансій",
                "lifetime_p25": "p25, днів",
                "lifetime_median": "Медіана, днів",
                "lifetime_p75": "p75, днів",
            }
        ),
        hide_index=True,
    )
st.caption(
    "Опитування — це самозвіт респондентів, а не пропозиції роботодавців; "
    "кореляція, не причинність."
)
