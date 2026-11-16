"""Dataward dashboard: `streamlit run dashboard/app.py`. Reads only the files of `make export`."""

from pathlib import Path

import streamlit as st

from jobmarket import dashboard_reload

dashboard_reload.refresh()  # pick up edited modules from src/ before they are imported below

from jobmarket import dashboard_ui as ui  # noqa: E402  (after the refresh on purpose)

STATIC = Path(__file__).parent / "static"  # the wordmark and the favicon (dashboard_logo.py)

st.set_page_config(
    page_title="Dataward · ринок праці в ІТ України",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# the same mark with the name in the menu and in the phone's top bar (where the menu is closed)
st.logo(str(STATIC / "wordmark.svg"), size="large", icon_image=str(STATIC / "wordmark.svg"))
ui.setup()
ui.keep_data_fresh()  # a hosted copy re-fetches the nightly export (no-op without a URL)

personal = not ui.public_demo()  # a profile and what is built on it are for the owner only

home = st.Page("views/home.py", title="Головна", icon=":material/home:", default=True)
catalog = st.Page("views/catalog.py", title="Каталог", icon=":material/list_alt:")
market = st.Page("views/market.py", title="Ринок", icon=":material/monitoring:")
skills = st.Page("views/skills.py", title="Навички", icon=":material/psychology:")
salary = st.Page("views/salary.py", title="Зарплати", icon=":material/payments:")
system = st.Page("views/system.py", title="Стан системи", icon=":material/health_and_safety:")

pages: list[st.Page] | dict[str, list[st.Page]]
grouped: list[st.Page] = []  # pages inside menus: the shortcuts reach them through hidden links
if personal:  # twelve entries would not fit in a row: groups open as menus
    grouped = [
        catalog,
        st.Page("views/fit.py", title="Для мене", icon=":material/person_search:"),
        st.Page("views/saved.py", title="Збережені", icon=":material/bookmark:"),
        st.Page("views/profile.py", title="Профіль", icon=":material/account_circle:"),
        st.Page("views/learn.py", title="Навчання", icon=":material/school:"),
        st.Page("views/practice.py", title="Практика", icon=":material/quiz:"),
    ]
    pages = {
        "": [home],
        "Вакансії": grouped[:3],
        "Розвиток": grouped[3:],
        "Аналітика": [market, skills, salary, system],
    }
else:  # six pages sit in one row
    pages = [home, catalog, market, skills, salary, system]
navigation = st.navigation(pages, position="top")
if personal:
    ui.undo_bar()  # a slim bar while the last action can be taken back (also `z`)
ui.scripts(grouped)  # shortcuts (`?` lists them, pages do not print them) and the page-enter motion
if personal:
    ui.avatar_card()  # you, at the foot of the sidebar, on every page
navigation.run()
