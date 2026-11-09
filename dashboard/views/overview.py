import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

st.title("Огляд ринку")

market = ui.table("fct_market_daily")
demand = ui.table("fct_skill_demand_monthly")
skills = ui.table("dim_skill")

left, middle, right = st.columns(3)
sources = left.multiselect("Джерело", sorted(market["source"].unique()))
categories = middle.multiselect("Категорія", sorted(market["category"].unique()))
levels = right.multiselect("Рівень", sorted(market["seniority"].unique()))

selected = dd.filter_market(market, sources=sources, categories=categories, seniorities=levels)
if selected.empty:
    st.info("За вибраними фільтрами вакансій немає.")
    st.stop()

today = selected[selected["date"] == selected["date"].max()]
one, two, three = st.columns(3)
one.metric("Відкриті вакансії", int(today["open_vacancies"].sum()))
two.metric("Нові за день", int(today["new_vacancies"].sum()))
three.metric("Закриті за день", int(today["closed_vacancies"].sum()))
if selected["date"].max() == market["date"].min():
    st.caption(
        "Це перший день спостереження: усі вакансії позначено «новими», бо раніше ми їх не бачили. "
        "Реальні нові й закриті з'являться з другого дня."
    )

st.subheader("Динаміка відкритих вакансій")
st.line_chart(dd.open_by_day(selected))

st.subheader("За категоріями")
st.bar_chart(dd.open_by_category(selected), x="category", y="open_vacancies", horizontal=True)

st.subheader("Найпопулярніші навички")
month = dd.latest_month(demand)
top = dd.top_skills(demand, skills, month=month, n=20)
top["Частка вакансій, %"] = (top["share"] * 100).round(1)
st.dataframe(
    top.rename(columns={"canonical": "Навичка", "category": "Група", "vacancies": "Вакансій"})[
        ["Навичка", "Група", "Вакансій", "Частка вакансій, %"]
    ],
    hide_index=True,
)
st.caption(
    f"Частка — від усіх унікальних вакансій місяця {month:%Y-%m}; вакансія з обох сайтів рахується "
    "один раз, навичка рахується і для батьківських (Next.js → React). У графіках вище DOU і "
    "Djinni рахуються окремо, тож одна вакансія на обох сайтах там — два рядки."
)
