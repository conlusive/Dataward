import pandas as pd
import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

st.title("Стан пайплайну")

status = ui.document("status.json")
st.caption(f"Станом на {status['generated_at']}")

st.subheader("Цілі якості (SLO)")
st.dataframe(dd.slo_table(status), hide_index=True)

st.subheader("Останні запуски")
runs = dd.runs_table(status)
if runs.empty:
    st.info("Запусків ще не записано.")
else:
    st.dataframe(runs, hide_index=True)

st.subheader("Перевірки якості")
checks = pd.DataFrame(status["dq_latest"])
if not checks.empty:
    problems = checks[checks["status"].isin(["warn", "error"])]
    st.metric("Перевірок, що потребують уваги", len(problems))
    st.dataframe(
        checks.rename(
            columns={
                "check": "Перевірка",
                "layer": "Шар",
                "status": "Стан",
                "observed": "Значення",
                "detail": "Деталі",
            }
        ),
        hide_index=True,
    )

st.subheader("Скрапінг")
scrape = pd.DataFrame(status["scrape"])
if not scrape.empty:
    scrape["частка помилок, %"] = (
        scrape["errors"] / scrape["pages"].where(scrape["pages"] > 0) * 100
    ).round(2)
    st.dataframe(scrape, hide_index=True)

st.subheader("Обсяги")
st.write(", ".join(f"{name}: {count}" for name, count in status["volumes"].items()))
