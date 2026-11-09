import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

st.title("Навички")

skills = ui.table("dim_skill")
demand = ui.table("fct_skill_demand_monthly")
pairs = ui.table("fct_skill_pairs")
salary = ui.table("fct_salary_by_skill")
clusters = ui.table("skill_clusters")

ranked = dd.top_skills(demand, skills, month=dd.latest_month(demand), n=len(skills))
names = ranked["canonical"].tolist() or sorted(skills["canonical"])
name = st.selectbox("Навичка", names)
skill_id = skills.loc[skills["canonical"] == name, "skill_id"].iloc[0]

trend = dd.skill_trend(demand, skill_id)
st.subheader("Попит")
if trend.empty:
    st.info("Цю навичку ще не знайдено в жодній вакансії.")
else:
    last = trend.iloc[-1]
    st.metric(
        f"Частка вакансій ({last['month']:%Y-%m})",
        f"{last['share'] * 100:.1f}%",
        help=f"{int(last['vacancies'])} з {int(last['month_vacancies'])} вакансій місяця",
    )
    if len(trend) > 1:
        st.line_chart(trend, x="month", y="share")
    else:
        st.caption("Тренд з'явиться, коли накопичиться більше одного місяця.")

st.subheader("Зарплата за вакансіями з вилкою")
declared = dd.skill_salary(salary, skill_id)
if declared is None:
    st.info("Замало вакансій з указаною зарплатою, щоб показати число без шуму.")
else:
    a, b, c = st.columns(3)
    a.metric("p25, USD/міс", f"{declared['p25']:.0f}")
    b.metric("Медіана, USD/міс", f"{declared['median']:.0f}")
    c.metric("p75, USD/міс", f"{declared['p75']:.0f}")
    st.caption(
        f"Вакансій з вилкою: {int(declared['vacancies'])}. Це лише ті, хто вказує зарплату, "
        "тож вибірка зміщена."
    )

st.subheader("З чим зустрічається")
related = dd.related_skills(pairs, skills, skill_id)
if related.empty:
    st.info("Недостатньо спільних вакансій для надійних пар.")
else:
    st.dataframe(
        related.rename(
            columns={
                "canonical": "Навичка",
                "vacancies_together": "Разом у вакансіях",
                "lift": "Lift",
                "npmi": "NPMI",
            }
        ),
        hide_index=True,
    )

cluster = dd.skill_cluster(clusters, skills, skill_id)
if cluster:
    st.subheader("Стек")
    st.write(
        f"Кластер «{cluster['label']}» ({cluster['size']} навичок): "
        + ", ".join(cluster["members"])
    )
