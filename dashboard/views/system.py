import os

import pandas as pd
import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

status = ui.document("status.json")
update = ui.document("last_update.json")
tone, headline, detail = dd.health(status)

ui.header(
    "Стан і дані",
    "Чи здорові дані: цілі якості, перевірки, запуски пайплайну, скрапінг, і звідки все береться.",
    eyebrow="Система",
    pills=[theme.pill(f"станом на {dd.stamp(status['generated_at'])}"), theme.pill(headline, tone)],
)

state_tab, checks_tab, scrape_tab, about_tab = st.tabs(
    ["Стан", "Перевірки", "Скрапінг", "Про дані"]
)

with state_tab:
    runs = dd.runs_table(status)
    done = int((runs["статус"] == "success").sum()) if not runs.empty else 0
    one, two, three = st.columns(3)
    with one:
        ui.kpi(1, "Стан", headline, delta=detail, direction="neutral")
    with two:
        newest = runs.iloc[0] if not runs.empty else None
        ui.kpi(
            2, "Останній запуск", str(newest["статус"]) if newest is not None else "—",
            delta=str(newest["дата"]) if newest is not None else None, direction="neutral",
        )  # fmt: skip
    with three:
        ui.kpi(3, "Успішних запусків", f"{done} з {len(runs)}", direction="neutral")

    ui.section("Цілі якості (SLO)")
    st.dataframe(dd.slo_table(status), hide_index=True)
    ui.section("Останні запуски")
    if runs.empty:
        st.info("Запусків ще не записано.")
    else:
        st.dataframe(runs, hide_index=True)

with checks_tab:
    checks = pd.DataFrame(status["dq_latest"])
    if checks.empty:
        st.info("Перевірок ще не записано.")
    else:
        problems = checks[checks["status"].isin(["warn", "error"])]
        ui.kpi(1, "Перевірок, що потребують уваги", len(problems), direction="neutral")
        icons = {"pass": "✓ норма", "warn": "▲ попередження", "error": "✕ помилка"}
        st.dataframe(
            checks.assign(status=checks["status"].map(icons).fillna(checks["status"])).rename(
                columns={
                    "check": "Перевірка",
                    "layer": "Шар",
                    "status": "Стан",
                    "observed": "Значення",
                    "detail": "Деталі",
                }
            ),  # fmt: skip
            hide_index=True,
            height=420,
        )

with scrape_tab:
    scrape = pd.DataFrame(status["scrape"])
    if scrape.empty:
        st.info("Скрапінгу ще не записано.")
    else:
        scrape["частка помилок, %"] = (
            scrape["errors"] / scrape["pages"].where(scrape["pages"] > 0) * 100
        ).round(2)
        st.dataframe(scrape, hide_index=True)
    ui.section("Обсяги")
    volumes = list(status["volumes"].items())
    for column, (name, count) in zip(st.columns(max(len(volumes), 1)), volumes, strict=False):
        with column:
            ui.kpi(volumes.index((name, count)) + 1, name, dd.fmt_int(count), direction="neutral")

with about_tab:
    st.markdown(f"Останнє оновлення експорту: **{update['exported_at']}**")
    rows = pd.DataFrame(
        [
            {"Таблиця": name, "Рядків": info["rows"]}
            for name, info in sorted(update["tables"].items())
        ]
    )
    st.dataframe(rows, hide_index=True)

    ui.section("Звідки дані")
    st.markdown(
        "- **jobs.dou.ua** і **djinni.co**: публічні сторінки вакансій (обережний скрапінг: "
        "robots.txt, 1–2 запити на секунду, чесний User-Agent).\n"
        "- **Опитування DOU** (зарплати, 2010–2025): відкриті дані DOU.\n"
        "- **Курси НБУ**: для переведення зарплат у USD на дату публікації."
    )
    ui.section("Обмеження")
    st.markdown(
        "- Зарплату вказує мала частка вакансій, тож зарплатні числа мають зміщену вибірку.\n"
        "- Навички знаходить словник (і, коли ввімкнено, LLM); точність вимірюється на "
        "розміченому наборі: F1 близько 0.8, розмітку зробив LLM, а не людина "
        "(докладно в `docs/metrics.md`).\n"
        "- Історія накопичується з листопада 2026: тренди з'являться за кілька тижнів.\n"
        "- Усе — кореляція, не причинність."
    )
    docs_url = os.environ.get("DBT_DOCS_URL")
    if docs_url:
        st.markdown(f"[Документація моделей (dbt docs)]({docs_url})")
