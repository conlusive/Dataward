from datetime import date
from html import escape

import pandas as pd
import streamlit as st

from jobmarket import dashboard_interview as iv
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_resources as rs
from jobmarket import dashboard_ui as ui

TODAY = date.today()
profile = ui.profile()
catalog = ui.catalog()
bank = ui.question_bank()
resources = ui.resource_bank()
ranked = pr.rank_vacancies(catalog, profile) if catalog is not None else None
plan = (
    pr.learning_plan(ranked, profile.known())
    if ranked is not None and not ranked.empty
    else pd.DataFrame(columns=["skill", "vacancies", "required", "unlocks"])
)

ui.header(
    "Навчання",
    "Що вивчити наступним, де це вчити і наскільки ви просунулись: матеріали, питання, прогрес.",
    eyebrow="розвиток / навчання",
    domain="grow",
)
ui.show_flash()


def toggle(url: str) -> None:
    """A checkbox callback: a resource is finished, or not any more."""
    current = ui.profile()
    pr.toggle_resource(current, url, TODAY)
    ui.persist(current, "Змінено позначку матеріалу")


def finish(skill: str) -> None:
    """A button callback: a skill being learned now counts as known."""
    current = ui.profile()
    pr.mark_skill(current, skill, "know")
    if ui.persist(current, f"«{skill}» позначено як відому"):
        ui.flash(f"«{skill}» тепер серед ваших навичок.")


# ---- what I am learning now ------------------------------------------------------------------
ui.section("Вчу зараз")
learning = sorted(profile.learning())
if not learning:
    st.caption(
        "Нічого не позначено як «вчу зараз». Додайте навичку в профілі або позначте її в плані."
    )
for skill in learning:
    done, total = rs.progress(skill, profile.done, resources)
    asked = iv.progress([q for q in bank if q.skill == skill], profile.practice, TODAY)
    mastered = int(asked["mastered"].sum()) if not asked.empty else 0
    questions = int(asked["total"].sum()) if not asked.empty else 0
    with st.container(border=True):
        left, middle, right = st.columns([3, 3, 2])
        left.markdown(f"**{skill}**")
        left.caption(f"матеріалів: {done} з {total}" if total else "матеріали: пошук нижче")
        middle.progress(
            (done / total) if total else 0.0,
            text="матеріали",
        )
        middle.progress(
            (mastered / questions) if questions else 0.0, text=f"питання: {mastered} з {questions}"
        )
        right.button("Вважати вивченою", key=f"fin_{skill}", on_click=finish, args=(skill,))

# ---- what to learn next ----------------------------------------------------------------------
ui.section("Що вчити далі")
if catalog is None or ranked is None:
    st.info("План береться з вакансій каталогу, якого в цьому експорті немає (`make pipeline`).")
elif ranked.empty:
    st.info("За вашою ціллю немає відкритих вакансій, тож і плану немає: послабте ціль.")
elif plan.empty:
    st.success("Усі навички вакансій за вашою ціллю вже у вашому профілі.")
else:
    st.caption(
        f"На основі {len(ranked)} відкритих вакансій за вашою ціллю. «Відкриває»: у скількох "
        "вакансіях це єдина обов'язкова навичка, якої вам бракує: вивчіть її, і вакансія закрита."
    )
    per_skill = {s: sum(1 for q in bank if q.skill == s) for s in iv.skills_in_bank(bank)}
    edited_plan = st.data_editor(
        pr.plan_table(plan, profile, per_skill), key="pf_plan", hide_index=True, num_rows="fixed",
        disabled=["Навичка", "Відкриває", "Обов'язкова у", "Згадується у", "Питань"],
        column_config={"Навичка": st.column_config.TextColumn(width=200)},
    )  # fmt: skip
    ticked = st.button("Зберегти позначки", key="pf_plan_apply")
    if (
        ticked
        and pr.apply_plan_table(profile, edited_plan)
        and ui.persist(profile, "Змінено позначки плану")
    ):
        ui.flash("Позначки збережено.")
        st.rerun()

# ---- materials for one skill -----------------------------------------------------------------
ui.section("Матеріали")
options = list(dict.fromkeys([*plan["skill"], *learning, *rs.skills_with_resources(resources)]))
skill = st.selectbox("Навичка", options, key="learn_skill")
curated = rs.for_skill(skill, resources)
row = plan[plan["skill"] == skill]
if not row.empty:
    st.caption(
        f"Потрібна у {int(row.iloc[0]['vacancies'])} вакансіях за вашою ціллю, відкриває "
        f"{int(row.iloc[0]['unlocks'])} повністю."
    )
if not curated[0].curated:
    st.caption("Добірки для цієї навички ще немає: нижче пошук, з чого почати.")
for number, item in enumerate(curated):
    one, two, three = st.columns([6, 2, 2])
    tags = f"{rs.KIND_LABELS[item.kind]} · {rs.LANG_LABELS[item.lang]}" + (
        f" · {item.note}" if item.note else ""
    )
    one.markdown(
        f'<div class="dw-resource"><b>{escape(item.title)}</b><br>'
        f'<span class="dw-muted">{escape(tags)}</span></div>',
        unsafe_allow_html=True,
    )
    two.link_button("Відкрити ↗", item.url, width="stretch")
    if item.curated:
        three.checkbox(
            "Пройшов", value=item.url in profile.done, key=f"res_{skill}_{number}",
            on_change=toggle, args=(item.url,),
        )  # fmt: skip
questions_here = sum(1 for q in bank if q.skill == skill)
if questions_here:
    st.button(
        f"Практикувати: питань {questions_here}", key="learn_practice",
        on_click=ui.go_practice, args=(skill,),
    )  # fmt: skip
