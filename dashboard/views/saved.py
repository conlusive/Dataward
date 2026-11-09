import streamlit as st

from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

profile = ui.profile()

ui.header(
    "Збережені вакансії",
    "Куди ви відгукнулися і на якому етапі кожна: від «збережено» до оффера чи відмови.",
    eyebrow="вакансії / збережені",
)
ui.show_flash()

counts = pr.status_counts(profile)
ui.html(theme.stats([(pr.STATUS_LABELS[status], str(n)) for status, n in counts.items()]))
if not profile.saved:
    st.info(
        "Збережених вакансій ще немає. У каталозі чи на сторінці «Вакансії для мене» відкрийте "
        "вакансію й натисніть «Зберегти у профіль»."
    )
    st.page_link("views/catalog.py", label="До каталогу →")
    st.stop()

edited = st.data_editor(
    pr.saved_table(profile), key="pf_saved", hide_index=True, num_rows="fixed",
    disabled=["id", "Назва", "Компанія", "Посилання", "Збережено"],
    column_order=["Етап", "Назва", "Компанія", "Нотатка", "Посилання", "Збережено", "Видалити"],
    column_config={
        "Етап": st.column_config.SelectboxColumn(
            options=list(pr.STATUS_LABELS.values()), required=True, width=130
        ),
        "Нотатка": st.column_config.TextColumn(max_chars=pr.MAX_NOTE, width=260),
        "Посилання": st.column_config.LinkColumn(display_text="відкрити ↗"),
    },
)  # fmt: skip
st.caption("Змініть етап чи нотатку, або позначте «Видалити», і натисніть кнопку нижче.")
clicked = st.button("Зберегти зміни", key="pf_saved_apply")
if clicked and pr.apply_saved_table(profile, edited) and ui.persist(profile):
    ui.flash("Зміни збережено.")
    st.rerun()
