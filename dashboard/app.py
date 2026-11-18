"""Dataward dashboard: `streamlit run dashboard/app.py`. Reads only the files of `make export`."""

from pathlib import Path

import streamlit as st

from jobmarket import dashboard_reload

dashboard_reload.refresh()  # pick up edited modules from src/ before they are imported below

from jobmarket import dashboard_head as head  # noqa: E402  (after the refresh on purpose)
from jobmarket import dashboard_ui as ui  # noqa: E402

STATIC = Path(__file__).parent / "static"  # the wordmark and the favicon (dashboard_logo.py)

st.set_page_config(
    page_title=head.TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)
# the same mark with the name in the menu and in the phone's top bar (where the menu is closed)
st.logo(str(STATIC / "wordmark.svg"), size="large", icon_image=str(STATIC / "wordmark.svg"))
ui.setup()
ui.keep_data_fresh()  # a hosted copy re-fetches the nightly export (no-op without a URL)

personal = not ui.public_demo()  # a profile and what is built on it are for the owner only

# The menu has no group headings: a group is a gap, and a heading made only of invisible characters
# (every key of a dict must differ) gives Streamlit something to draw as that gap.
sections = {
    "": [st.Page("views/home.py", title="Головна", icon=":material/home:", default=True)],
    "\u200b": [st.Page("views/catalog.py", title="Вакансії", icon=":material/list_alt:")],
}
if personal:
    sections["\u200b"] += [
        st.Page("views/fit.py", title="Вакансії для мене", icon=":material/person_search:"),
        st.Page("views/saved.py", title="Збережені вакансії", icon=":material/bookmark:"),
    ]
    sections["\u200b\u200b"] = [
        st.Page("views/profile.py", title="Мій профіль", icon=":material/account_circle:"),
        st.Page("views/learn.py", title="План навчання", icon=":material/school:"),
        st.Page("views/practice.py", title="Практика співбесід", icon=":material/quiz:"),
    ]
sections["\u200b\u200b\u200b"] = [
    st.Page("views/market.py", title="Ринок праці", icon=":material/monitoring:"),
    st.Page("views/skills.py", title="Навички у вакансіях", icon=":material/psychology:"),
    st.Page("views/salary.py", title="Зарплати", icon=":material/payments:"),
]
sections["\u200b\u200b\u200b\u200b"] = [
    st.Page("views/system.py", title="Стан системи", icon=":material/health_and_safety:"),
    st.Page("views/about.py", title="Про проєкт", icon=":material/info:"),
]
navigation = st.navigation(sections, expanded=True)  # every item visible, never behind "View more"
if personal:
    ui.undo_bar()  # a slim bar while the last action can be taken back (also `z`)
ui.scripts()  # shortcuts (`?` lists them, pages do not print them) and the page-enter motion
ui.sidebar_footer()  # how fresh the data is, and the code, under the menu
if personal:
    ui.avatar_card()  # you, at the foot of the sidebar, on every page
navigation.run()
