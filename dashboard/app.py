"""Dataward dashboard: `streamlit run dashboard/app.py`. Reads only the files of `make export`."""

from pathlib import Path

import streamlit as st

from jobmarket import dashboard_reload

dashboard_reload.refresh()  # pick up edited modules from src/ before they are imported below

from jobmarket import dashboard_ui as ui  # noqa: E402  (after the refresh on purpose)

STATIC = Path(__file__).parent / "static"  # the pixel logo and the favicon (dashboard_logo.py)

st.set_page_config(
    page_title="Dataward · ринок праці в ІТ України",
    page_icon=str(STATIC / "favicon.png"),
    layout="wide",
    initial_sidebar_state="expanded",
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
            st.Page("views/fit.py", title="Для мене", icon=":material/person_search:"),
            st.Page("views/saved.py", title="Збережені", icon=":material/bookmark:"),
        ],
        "Розвиток": [
            st.Page("views/profile.py", title="Профіль", icon=":material/account_circle:"),
            st.Page("views/learn.py", title="Навчання", icon=":material/school:"),
            st.Page("views/practice.py", title="Практика", icon=":material/quiz:"),
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
ui.pet_card()  # the frog sits under the menu on every page
navigation.run()
