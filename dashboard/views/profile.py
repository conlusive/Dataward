from datetime import date
from html import escape

import pandas as pd
import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_interview as iv
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

TODAY = date.today()
profile = ui.profile()
catalog = ui.catalog()
market = ui.table("fct_market_daily")
skill_names = sorted(ui.table("dim_skill")["canonical"].dropna().unique())
bank = iv.load_bank()
questions = {q.id: q for q in bank}

# the vacancies that suit the target (needs a catalog) and what they say about the profile
ranked = pr.rank_vacancies(catalog, profile) if catalog is not None else None
readiness = pr.readiness(ranked) if ranked is not None and profile.known() else None
tally = iv.counts(bank, profile.practice, TODAY)

ui.header(
    f"Профіль{': ' + profile.name if profile.name else ''}",
    "Ваші навички й ціль, вакансії, що вам підходять, збережені відгуки, план навчання і тренажер "
    "до співбесід. Усе лежить у файлі на цьому комп'ютері.",
    eyebrow="кабінет / профіль",
)
ui.show_flash()
ui.html(
    theme.stats(
        [
            ("Знаю", str(len(profile.known()))),
            ("Вчу", str(len(profile.learning()))),
            ("Збережено", str(len(profile.saved))),
            ("До повтору", str(tally["due"])),
            ("Готовність", f"{readiness:.0%}" if readiness is not None else "—"),
        ]
    )
)

profile_tab, jobs_tab, saved_tab, plan_tab, practice_tab = st.tabs(
    ["Профіль", "Вакансії для мене", "Збережені", "Що вчити", "Практика"]
)

# ---- the profile itself ----------------------------------------------------------------------
with profile_tab:
    categories = ["", *sorted(market["category"].dropna().unique())]
    with st.form("profile_form"):
        one, two = st.columns(2)
        name = one.text_input("Ім'я (необов'язково)", value=profile.name, key="pf_name")
        category = two.selectbox(
            "Цільовий напрямок", categories, key="pf_category",
            index=categories.index(profile.category) if profile.category in categories else 0,
            format_func=lambda value: value or "будь-який",
        )  # fmt: skip
        three, four, five = st.columns(3)
        level = three.selectbox(
            "Рівень", list(pr.LEVELS), key="pf_level", index=pr.LEVELS.index(profile.level),
            format_func=lambda value: value or "будь-який",
        )  # fmt: skip
        min_salary = four.number_input(
            "Зарплата від, USD/міс", 0, 20000, value=profile.min_salary, step=100, key="pf_salary"
        )
        remote = five.toggle("Лише віддалено", value=profile.remote, key="pf_remote")
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
        outside = {s: state for s, state in profile.skills.items() if s not in skill_names}
        profile.name, profile.category, profile.level = name.strip(), category, level
        profile.min_salary, profile.remote = int(min_salary), bool(remote)
        pr.set_skills(profile, know, learning)
        profile.skills.update(outside)  # a skill the taxonomy no longer lists is not thrown away
        if ui.persist(profile):
            ui.flash("Профіль збережено.")
            st.rerun()
    if profile.is_empty():
        st.caption(
            "Почніть із навичок: за ними рахується збіг із вакансіями, а напрямок і рівень "
            "звужують список."
        )

# ---- vacancies that suit the profile ---------------------------------------------------------
with jobs_tab:
    if catalog is None or ranked is None:
        st.info(
            "Вакансії для вас рахуються з каталогу, а його в цьому експорті немає: він локальний "
            "(`make pipeline`). Профіль, план і тренажер працюють і без нього."
        )
    elif not profile.known():
        st.info("Додайте у вкладці «Профіль» навички, які ви вмієте: збіг рахується з ними.")
    elif ranked.empty:
        st.info("За вашою ціллю відкритих вакансій немає: послабте напрямок, рівень чи зарплату.")
    else:
        best = ranked["match"].max()
        one, two, three = st.columns(3)
        with one:
            ui.kpi(1, "Вакансій за ціллю", dd.fmt_int(len(ranked)), direction="neutral")
        with two:
            ui.kpi(
                2, "Найкращий збіг", f"{best:.0%}" if pd.notna(best) else "—", direction="neutral"
            )
        with three:
            ui.kpi(
                3, "Готовність", f"{readiness:.0%}" if readiness is not None else "—",
                delta="медіана 20 найкращих", direction="neutral",
            )  # fmt: skip
        floor = st.slider("Показати від, % збігу", 0, 100, 0, step=5, key="pf_floor")
        shown = ranked[ranked["match"].fillna(0) * 100 >= floor].reset_index(drop=True)
        if shown.empty:
            st.info("Немає вакансій із таким збігом: зменште поріг.")
        else:
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
                        for low, high in zip(
                            shown["salary_usd_min"], shown["salary_usd_max"], strict=True
                        )
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
                        '<div class="dw-muted">▸ Клікніть рядок: побачите вакансію докладно, що '
                        "вам бракує, і зможете зберегти її в профіль.</div>",
                        unsafe_allow_html=True,
                    )

# ---- saved vacancies and where each stands ---------------------------------------------------
with saved_tab:
    counts = pr.status_counts(profile)
    ui.html(theme.stats([(pr.STATUS_LABELS[status], str(n)) for status, n in counts.items()]))
    if not profile.saved:
        st.info(
            "Збережених вакансій ще немає. У каталозі чи у вкладці «Вакансії для мене» відкрийте "
            "вакансію й натисніть «Зберегти у профіль»."
        )
    else:
        edited = st.data_editor(
            pr.saved_table(profile), key="pf_saved", hide_index=True, num_rows="fixed",
            disabled=["id", "Назва", "Компанія", "Посилання", "Збережено"],
            column_order=[
                "Етап", "Назва", "Компанія", "Нотатка", "Посилання", "Збережено", "Видалити",
            ],
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

# ---- what to learn next ----------------------------------------------------------------------
with plan_tab:
    if catalog is None or ranked is None:
        st.info("План навчання береться з вакансій каталогу, якого в цьому експорті немає.")
    elif ranked.empty:
        st.info("За вашою ціллю немає відкритих вакансій, тож і плану немає: послабте ціль.")
    else:
        plan = pr.learning_plan(ranked, profile.known())
        if plan.empty:
            st.success("Усі навички вакансій за вашою ціллю вже у вашому профілі.")
        else:
            st.caption(
                f"На основі {len(ranked)} відкритих вакансій за вашою ціллю. «Відкриває»: у "
                "скількох вакансіях це єдина обов'язкова навичка, якої вам бракує: вивчіть її, "
                "і вакансія закрита."
            )
            per_skill = {s: sum(1 for q in bank if q.skill == s) for s in iv.skills_in_bank(bank)}
            table = pr.plan_table(plan, profile, per_skill)
            edited_plan = st.data_editor(
                table, key="pf_plan", hide_index=True, num_rows="fixed",
                disabled=["Навичка", "Відкриває", "Обов'язкова у", "Згадується у", "Питань"],
                column_config={"Навичка": st.column_config.TextColumn(width=200)},
            )  # fmt: skip
            ticked = st.button("Зберегти позначки", key="pf_plan_apply")
            if ticked and pr.apply_plan_table(profile, edited_plan) and ui.persist(profile):
                ui.flash("Позначки збережено.")
                st.rerun()

# ---- interview practice ----------------------------------------------------------------------
SIZES = [5, 10, 15]
SCOPES = ["Мої навички", "Що вчити", "Усі питання"]


def scope_skills(scope: str) -> set[str] | None:
    """The skills a session draws from; None means every skill of the bank."""
    if scope == "Усі питання":
        return None
    if scope == "Мої навички":
        return set(profile.skills) & set(iv.skills_in_bank(bank))
    if ranked is None or ranked.empty:
        return set()
    return set(pr.learning_plan(ranked, profile.known())["skill"]) & set(iv.skills_in_bank(bank))


def start_session(scope: str, levels: list[str], size: int) -> None:
    chosen = iv.build_session(
        bank, profile.practice, today=TODAY, skills=scope_skills(scope),
        levels=set(levels) if levels else None, size=size,
    )  # fmt: skip
    st.session_state.update(
        iv_queue=[q.id for q in chosen], iv_pos=0, iv_show=False, iv_results={}, iv_started=True
    )


def reveal() -> None:
    st.session_state["iv_show"] = True


def rate(rating: str) -> None:
    queue, position = st.session_state["iv_queue"], st.session_state["iv_pos"]
    question_id = queue[position]
    current = ui.profile()
    current.practice[question_id] = iv.review(current.practice.get(question_id), rating, TODAY)
    if ui.persist(current):
        results = st.session_state["iv_results"]
        results[rating] = results.get(rating, 0) + 1
        st.session_state.update(iv_pos=position + 1, iv_show=False)


with practice_tab:
    one, two, three, four = st.columns(4)
    with one:
        ui.kpi(1, "Питань у банку", str(tally["total"]), direction="neutral")
    with two:
        ui.kpi(2, "Вже бачили", str(tally["seen"]), direction="neutral")
    with three:
        ui.kpi(
            3, "Освоєно", str(tally["mastered"]), delta=f"з {tally['total']}", direction="neutral"
        )
    with four:
        ui.kpi(4, "На сьогодні", str(tally["due"]), delta="до повтору", direction="neutral")

    ui.section("Нова сесія")
    left, middle, right = st.columns([2, 3, 1])
    scope = left.radio("Звідки питання", SCOPES, key="iv_scope")
    levels = middle.pills(
        "Рівень питань", list(iv.LEVELS), selection_mode="multi", key="iv_levels",
        default=list(iv.LEVELS),
    )  # fmt: skip
    size = right.selectbox("Питань", SIZES, index=1, key="iv_size")
    pool = scope_skills(scope)
    if pool is not None and not pool:
        st.info(
            "У цьому наборі немає навичок із питаннями. Додайте навички в профіль, візьміть «Усі "
            "питання» або подивіться вкладку «Що вчити»."
            if scope != "Що вчити" or ranked is not None
            else "«Що вчити» береться з каталогу, якого немає в цьому експорті."
        )
    st.button(
        "Почати",
        key="iv_start",
        on_click=start_session,
        args=(scope, levels or [], size),
        disabled=pool is not None and not pool,
    )

    queue: list[str] = st.session_state.get("iv_queue", [])
    position: int = st.session_state.get("iv_pos", 0)
    if st.session_state.get("iv_started"):
        if not queue:
            st.info("На цей набір питань немає: усе вже вивчено або не відповідає фільтрам.")
        elif position < len(queue):
            question = questions[queue[position]]
            ui.section(f"Питання {position + 1} з {len(queue)}")
            with st.container(border=True):
                ui.html(
                    f'<div class="dw-q-meta">{question.skill} · {question.level}</div>'
                    f'<div class="dw-lead">{escape(question.question)}</div>'
                )
                if not st.session_state.get("iv_show"):
                    st.button("Показати відповідь", key="iv_reveal", on_click=reveal)
                else:
                    ui.html(f'<div class="dw-answer">{escape(question.answer)}</div>')
                    st.caption("Скажіть відповідь своїми словами й чесно оцініть себе.")
                    columns = st.columns(len(iv.RATINGS))
                    for column, rating in zip(columns, iv.RATINGS, strict=True):
                        column.button(
                            iv.RATING_LABELS[rating],
                            key=f"iv_rate_{rating}",
                            on_click=rate,
                            args=(rating,),
                            width="stretch",
                        )
        else:
            results = st.session_state.get("iv_results", {})
            ui.section("Сесію завершено")
            ui.html(
                theme.stats([(iv.RATING_LABELS[r], str(results.get(r, 0))) for r in iv.RATINGS])
            )
            st.caption(
                "Питання, які ви знаєте, повернуться пізніше, а «Не знаю» вже завтра. Повертайтеся "
                "щодня: повторення працює лише регулярно."
            )

    ui.section("Прогрес за навичками")
    table = iv.progress(bank, profile.practice, TODAY)
    table["Освоєно, %"] = (table["mastered"] / table["total"] * 100).round(0)
    st.dataframe(
        table.rename(
            columns={
                "skill": "Навичка",
                "total": "Питань",
                "seen": "Бачили",
                "mastered": "Освоєно",
                "due": "До повтору",
            }
        ),
        hide_index=True,
        height=320,
        column_config={
            "Освоєно, %": st.column_config.ProgressColumn(format="%d", min_value=0, max_value=100)
        },
    )
