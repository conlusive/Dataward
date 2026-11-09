"""Dataward dashboard: `streamlit run dashboard/app.py`. Reads only the files of `make export`."""

import streamlit as st

from jobmarket import dashboard_ui as ui

st.set_page_config(
    page_title="Dataward · ринок праці в ІТ України",
    page_icon=":material/query_stats:",
    layout="wide",
)
ui.setup()

navigation = st.navigation(
    {
        "Dataward": [
            st.Page("views/home.py", title="Головна", icon=":material/home:", default=True),
        ],
        "Аналітика": [
            st.Page("views/market.py", title="Ринок", icon=":material/monitoring:"),
            st.Page("views/skills.py", title="Навички", icon=":material/psychology:"),
            st.Page("views/salary.py", title="Зарплати", icon=":material/payments:"),
        ],
        "Система": [
            st.Page("views/system.py", title="Стан і дані", icon=":material/health_and_safety:"),
        ],
    }
)
navigation.run()
