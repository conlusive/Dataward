import pandas as pd
import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_ui as ui

profile = ui.profile()
catalog = ui.catalog()

ui.header(
    "Вакансії для мене",
    "Відкриті вакансії за вашою ціллю, найкращий збіг із вашими навичками першим.",
    eyebrow="вакансії / для мене",
    domain="jobs",
)
ui.show_flash()

if catalog is None:
    st.info(
        "Вакансії для вас рахуються з каталогу, а його в цьому експорті немає: він локальний "
        "(`make pipeline`)."
    )
    st.stop()
if not profile.known():
    st.info("Додайте у профілі навички, які ви вмієте: збіг рахується з ними.")
    st.page_link("views/profile.py", label="Відкрити профіль →")
    st.stop()

ranked = pr.rank_vacancies(catalog, profile)
if ranked.empty:
    st.info("За вашою ціллю відкритих вакансій немає: послабте напрямок, рівень чи зарплату.")
    st.stop()

readiness = pr.readiness(ranked)
best = ranked["match"].max()
one, two, three = st.columns(3)
with one:
    ui.kpi(1, "Вакансій за ціллю", dd.fmt_int(len(ranked)), direction="neutral")
with two:
    ui.kpi(2, "Найкращий збіг", f"{best:.0%}" if pd.notna(best) else "—", direction="neutral")
with three:
    ui.kpi(
        3, "Готовність", f"{readiness:.0%}" if readiness is not None else "—",
        delta="медіана 20 найкращих", direction="neutral",
    )  # fmt: skip

floor = st.slider("Показати від, % збігу", 0, 100, 0, step=5, key="pf_floor")
shown = ranked[ranked["match"].fillna(0) * 100 >= floor].reset_index(drop=True)
if shown.empty:
    st.info("Немає вакансій із таким збігом: зменште поріг.")
    st.stop()

table = pd.DataFrame(
    {
        "Збіг, %": (shown["match"] * 100).round(0).to_numpy(),
        "Назва": shown["title"].to_numpy(),
        "Компанія": shown["company"].to_numpy(),
        "Є": [", ".join(have[:4]) for have in shown["have"]],
        "Бракує": [
            ", ".join(lack[:4]) + (f" +{len(lack) - 4}" if len(lack) > 4 else "")
            for lack in shown["missing"]
        ],
        "Зарплата": [
            dd.salary_label(low, high)
            for low, high in zip(shown["salary_usd_min"], shown["salary_usd_max"], strict=True)
        ],
        "Посилання": shown["url"].to_numpy(),
    }
)
event = st.dataframe(
    table, hide_index=True, height=420, key="pf_jobs", on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Збіг, %": st.column_config.ProgressColumn(
            format="%d", min_value=0, max_value=100, width=120
        ),
        "Назва": st.column_config.TextColumn(width=300),
        "Бракує": st.column_config.TextColumn(width=260),
        "Посилання": st.column_config.LinkColumn(display_text="відкрити ↗"),
    },
)  # fmt: skip
rows = event.selection.rows
with st.container(border=True):
    if rows and rows[0] < len(shown):
        ui.vacancy_card(shown.iloc[rows[0]], profile=profile)
    else:
        st.markdown(
            '<div class="dw-muted">▸ Клікніть рядок: побачите вакансію докладно, що вам '
            "бракує, і зможете зберегти її в профіль.</div>",
            unsafe_allow_html=True,
        )
