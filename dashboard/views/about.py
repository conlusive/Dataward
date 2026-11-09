import os

import pandas as pd
import streamlit as st

from jobmarket import dashboard_ui as ui

st.title("Про дані")

update = ui.document("last_update.json")
st.write(f"Останнє оновлення експорту: **{update['exported_at']}**")

rows = pd.DataFrame(
    [{"Таблиця": name, "Рядків": info["rows"]} for name, info in sorted(update["tables"].items())]
)
st.dataframe(rows, hide_index=True)

st.subheader("Звідки дані")
st.markdown(
    "- **jobs.dou.ua** і **djinni.co**: публічні сторінки вакансій (обережний скрапінг: "
    "robots.txt, 1–2 запити на секунду, чесний User-Agent).\n"
    "- **Опитування DOU** (зарплати, 2010–2025): відкриті дані DOU.\n"
    "- **Курси НБУ**: для переведення зарплат у USD на дату публікації."
)
st.subheader("Обмеження")
st.markdown(
    "- Зарплату вказує мала частка вакансій, тож зарплатні числа мають зміщену вибірку.\n"
    "- Навички знаходить словник (і, коли ввімкнено, LLM); точність вимірюється на "
    "розміченому наборі.\n"
    "- Історія накопичується з листопада 2026: тренди з'являться за кілька тижнів.\n"
    "- Усе — кореляція, не причинність."
)
docs_url = os.environ.get("DBT_DOCS_URL")
if docs_url:
    st.markdown(f"[Документація моделей (dbt docs)]({docs_url})")
