"""Dataward dashboard: `streamlit run dashboard/app.py`. Reads only the files of `make export`."""

from pathlib import Path

import streamlit as st

from jobmarket import dashboard_ui as ui

STATIC = Path(__file__).parent / "static"  # the pixel logo and the favicon (dashboard_logo.py)

st.set_page_config(
    page_title="Dataward · ринок праці в ІТ України",
    page_icon=str(STATIC / "favicon.png"),
    layout="wide",
)
st.logo(str(STATIC / "logo.svg"), size="large", icon_image=str(STATIC / "icon.svg"))
ui.setup()

navigation = st.navigation(
    {
        "Огляд": [
            st.Page("views/home.py", title="Головна", icon=":material/home:", default=True),
        ],
        "Вакансії": [
            st.Page("views/catalog.py", title="Каталог", icon=":material/list_alt:"),
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
