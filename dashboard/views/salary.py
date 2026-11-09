import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

st.title("Зарплати")

survey = ui.table("fct_salary_survey")
lifetime = ui.table("fct_vacancy_lifetime")

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
