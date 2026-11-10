from datetime import date

import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_mascot as mascot
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_progress as pg
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

TODAY = date.today()
profile = ui.profile()
catalog = ui.catalog()
market = ui.table("fct_market_daily")
skill_names = sorted(ui.table("dim_skill")["canonical"].dropna().unique())
state = ui.pet_state(profile, TODAY)
info, stage = state["level"], state["stage"]

ranked = pr.rank_vacancies(catalog, profile) if catalog is not None else None
readiness = pr.readiness(ranked) if ranked is not None and profile.known() else None
plan = pr.learning_plan(ranked, profile.known(), top=1) if ranked is not None else None

ui.header(
    f"Профіль{': ' + profile.name if profile.name else ''}",
    "Ваша жабка росте разом із вами: відповідайте на питання, проходьте матеріали, шукайте "
    "вакансії. Усе лежить у файлі на цьому комп'ютері.",
    eyebrow="розвиток / профіль",
    domain="grow",
)
ui.demo_notice()
ui.show_flash()

# ---- the frog, the numbers and what to do next ------------------------------------------------
with st.container(border=True):
    ui.html(
        theme.pet(
            mascot.frog_svg(stage.key, state["mood"], label=stage.name, scale=1.5),
            stage.name,
            info.level,
            info.ratio,
            f"{info.into} / {info.need} XP до наступного рівня",
            [f"усього {info.xp} XP", f"серія: {state['streak']} дн."],
        )
    )
ui.html(
    theme.stats(
        [
            ("Сьогодні", f"{state['today']}/{profile.goal}"),
            ("Знаю", str(len(profile.known()))),
            ("Вчу", str(len(profile.learning()))),
            ("Збережено", str(len(profile.saved))),
            ("Готовність", f"{readiness:.0%}" if readiness is not None else "—"),
        ]
    )
)

ui.section("Активність", domain="grow")
with ui.card("Відповіді за 20 тижнів", "кожна клітинка — один день; світліша — більше відповідей"):
    ui.chart(charts.activity_grid(dd.activity_grid(profile.activity, TODAY), cell=22))

ui.section("Далі для вас")
top = plan.iloc[0] if plan is not None and not plan.empty else None
steps = pg.next_steps(
    profile, state["counts"], TODAY,
    top_skill=str(top["skill"]) if top is not None else None,
    unlocks=int(top["unlocks"]) if top is not None else 0,
)  # fmt: skip
if steps:
    for step in steps:
        st.page_link(step.page, label=f"{step.text} →")
else:
    st.success("На сьогодні все: ціль виконано, повторювати нічого. Жабка пишається вами.")

ui.section("Досягнення")
ui.html(
    theme.medals([(a.title, a.hint, a.unlocked) for a in pg.achievements(profile, state["counts"])])
)
st.caption(
    "Досвід: " + ", ".join(f"{name} {points}" for name, points in state["parts"].items() if points)
    if any(state["parts"].values())
    else "Досвід з'явиться, щойно ви відповісте на питання чи збережете вакансію."
)

# ---- settings --------------------------------------------------------------------------------
ui.section("Налаштування профілю")
categories = ["", *sorted(market["category"].dropna().unique())]
with st.form("profile_form"):
    one, two = st.columns(2)
    name = one.text_input("Ім'я (необов'язково)", value=profile.name, key="pf_name")
    category = two.selectbox(
        "Цільовий напрямок", categories, key="pf_category",
        index=categories.index(profile.category) if profile.category in categories else 0,
        format_func=lambda value: value or "будь-який",
    )  # fmt: skip
    three, four, five, six = st.columns(4)
    level = three.selectbox(
        "Рівень", list(pr.LEVELS), key="pf_level", index=pr.LEVELS.index(profile.level),
        format_func=lambda value: value or "будь-який",
    )  # fmt: skip
    min_salary = four.number_input(
        "Зарплата від, USD/міс", 0, 20000, value=profile.min_salary, step=100, key="pf_salary"
    )
    remote = five.toggle("Лише віддалено", value=profile.remote, key="pf_remote")
    goal = six.number_input("Ціль дня, відповідей", 1, 50, value=profile.goal, key="pf_goal")
    know = st.multiselect(
        "Що я вмію", skill_names, key="pf_know",
        default=[s for s in sorted(profile.known()) if s in skill_names],
        placeholder="Оберіть навички, які ви справді вмієте",
    )  # fmt: skip
    learning = st.multiselect(
        "Що вчу зараз", skill_names, key="pf_learning",
        default=[s for s in sorted(profile.learning()) if s in skill_names],
        placeholder="Те, що вчите просто зараз",
    )  # fmt: skip
    submitted = st.form_submit_button("Зберегти профіль")
if submitted:
    outside = {s: state_ for s, state_ in profile.skills.items() if s not in skill_names}
    profile.name, profile.category, profile.level = name.strip(), category, level
    profile.min_salary, profile.remote, profile.goal = int(min_salary), bool(remote), int(goal)
    pr.set_skills(profile, know, learning)
    profile.skills.update(outside)  # a skill the taxonomy no longer lists is not thrown away
    if ui.persist(profile, "Змінено профіль"):
        ui.flash("Профіль збережено.")
        st.rerun()
