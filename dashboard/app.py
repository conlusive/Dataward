"""Dataward dashboard: `streamlit run dashboard/app.py`. Reads only the files of `make export`."""

import streamlit as st

st.set_page_config(page_title="Dataward: ринок праці в ІТ України", page_icon="📊", layout="wide")

navigation = st.navigation(
    [
        st.Page("views/overview.py", title="Огляд ринку", icon="📈", default=True),
        st.Page("views/skills.py", title="Навички", icon="🔎"),
        st.Page("views/stacks.py", title="Стеки", icon="🧩"),
        st.Page("views/salary.py", title="Зарплати", icon="💵"),
        st.Page("views/status.py", title="Стан пайплайну", icon="🩺"),
        st.Page("views/about.py", title="Про дані", icon="ℹ️"),
    ]
)
navigation.run()
