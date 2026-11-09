import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

st.title("Стеки")
st.caption(
    "Навички, які часто вимагають разом, об'єднано в кластери "
    "(метод Лувена на парах із високим NPMI)."
)

skills = ui.table("dim_skill")
pairs = ui.table("fct_skill_pairs")
clusters = ui.table("skill_clusters")

overview = dd.cluster_overview(clusters, skills)
if overview.empty:
    st.info("Кластерів поки немає: потрібно більше вакансій.")
    st.stop()

st.dataframe(
    overview.rename(
        columns={"cluster_id": "№", "size": "Навичок", "label": "Ядро", "members": "Склад"}
    ),
    hide_index=True,
)

options = {
    f"{row.cluster_id}. {row.label} ({row.size})": int(row.cluster_id)
    for row in overview.itertuples()
}
choice = st.selectbox("Стек", list(options))
threshold = st.slider("Мінімальний NPMI зв'язку", 0.0, 1.0, 0.3, 0.05)
st.graphviz_chart(dd.stack_dot(pairs, clusters, skills, options[choice], min_npmi=threshold))
st.caption("Товщина лінії — сила зв'язку (NPMI від −1 до 1).")
