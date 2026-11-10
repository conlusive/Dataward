from datetime import date
from html import escape

import streamlit as st

from jobmarket import dashboard_interview as iv
from jobmarket import dashboard_mascot as mascot
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

TODAY = date.today()
profile = ui.profile()
catalog = ui.catalog()
bank = ui.question_bank()
questions = {q.id: q for q in bank}
state = ui.pet_state(profile, TODAY)
ranked = pr.rank_vacancies(catalog, profile) if catalog is not None else None
in_bank = iv.skills_in_bank(bank)

SIZES = [5, 10, 15]
SCOPES = ["Мої навички", "Що вчити", "Одна навичка", "Усі питання"]
REACTIONS = {"know": "happy", "partial": "think", "dont": "sad"}
LINES = {
    "know": "Так тримати!", "partial": "Майже. Повернемося до цього.",
    "dont": "Нічого, завтра запам'ятаємо.",
}  # fmt: skip

ui.header(
    "Практика",
    "Тренажер до співбесід: питання, відповідь, чесна оцінка. Жабка радіє й росте разом із вами.",
    eyebrow="розвиток / практика",
    domain="grow",
)
ui.show_flash()


def scope_skills(scope: str) -> set[str] | None:
    """The skills a session draws from; None means every skill of the bank."""
    if scope == "Усі питання":
        return None
    if scope == "Одна навичка":
        return {st.session_state.get("iv_skill", in_bank[0])}
    if scope == "Мої навички":
        return set(profile.skills) & set(in_bank)
    if ranked is None or ranked.empty:
        return set()
    return set(pr.learning_plan(ranked, profile.known())["skill"]) & set(in_bank)


def start_session(scope: str, levels: list[str], size: int) -> None:
    chosen = iv.build_session(
        bank, profile.practice, today=TODAY, skills=scope_skills(scope),
        levels=set(levels) if levels else None, size=size,
    )  # fmt: skip
    st.session_state.update(
        iv_queue=[q.id for q in chosen], iv_pos=0, iv_show=False, iv_results={}, iv_started=True,
        iv_mood=None, iv_line="",
    )  # fmt: skip


def reveal() -> None:
    st.session_state["iv_show"] = True


def rate(rating: str) -> None:
    queue, position = st.session_state["iv_queue"], st.session_state["iv_pos"]
    question_id = queue[position]
    current = ui.profile()
    current.practice[question_id] = iv.review(current.practice.get(question_id), rating, TODAY)
    pr.record_answer(current, TODAY)
    if not ui.persist(current):
        return
    results = st.session_state["iv_results"]
    results[rating] = results.get(rating, 0) + 1
    last = position + 1 >= len(queue)
    st.session_state.update(
        iv_pos=position + 1, iv_show=False, iv_mood="party" if last else REACTIONS[rating],
        iv_line="Сесію завершено!" if last else LINES[rating], iv_refresh=last,
    )  # fmt: skip


def _frog(mood: str | None) -> str:
    return theme.pet_free(
        mascot.frog_svg(
            state["stage"].key, mood or state["mood"], label=state["stage"].name, scale=1.4
        )
    )


# ---- the numbers ------------------------------------------------------------------------------
tally = state["counts"]
one, two, three, four = st.columns(4)
with one:
    ui.kpi(1, "Питань у банку", str(tally["total"]), direction="neutral")
with two:
    ui.kpi(2, "Вже бачили", str(tally["seen"]), direction="neutral")
with three:
    ui.kpi(3, "Освоєно", str(tally["mastered"]), delta=f"з {tally['total']}", direction="neutral")
with four:
    ui.kpi(4, "На сьогодні", str(tally["due"]), delta="до повтору", direction="neutral")

# ---- a new session ---------------------------------------------------------------------------
ui.section("Нова сесія")
left, middle, right = st.columns([2, 3, 1])
scope = left.radio("Звідки питання", SCOPES, key="iv_scope")
if scope == "Одна навичка":
    middle.selectbox("Навичка", in_bank, key="iv_skill")
else:
    levels = middle.pills(
        "Рівень питань", list(iv.LEVELS), selection_mode="multi", key="iv_levels",
        default=list(iv.LEVELS),
    )  # fmt: skip
levels = st.session_state.get("iv_levels") or list(iv.LEVELS)
size = right.selectbox("Питань", SIZES, index=1, key="iv_size")
pool = scope_skills(scope)
if pool is not None and not pool:
    st.info(
        "У цьому наборі немає навичок із питаннями. Додайте навички в профіль, візьміть «Усі "
        "питання» чи «Одну навичку»."
        if scope != "Що вчити" or ranked is not None
        else "«Що вчити» береться з каталогу, якого немає в цьому експорті."
    )
st.button(
    "Почати", key="iv_start", on_click=start_session, args=(scope, levels, size),
    disabled=pool is not None and not pool,
)  # fmt: skip


@st.fragment
def session() -> None:
    """The question card. Only this block reruns on a click, so the page does not flicker."""
    if st.session_state.pop("iv_refresh", False):
        st.rerun()  # the session ended: redraw the whole page (numbers, sidebar frog)
    if not st.session_state.get("iv_started"):
        return
    queue: list[str] = st.session_state.get("iv_queue", [])
    position: int = st.session_state.get("iv_pos", 0)
    mood = st.session_state.get("iv_mood")
    if not queue:
        st.info("На цей набір питань немає: усе вже вивчено або не відповідає фільтрам.")
        return
    if position >= len(queue):
        results = st.session_state.get("iv_results", {})
        ui.section("Сесію завершено")
        with st.container(border=True):
            ui.html(_frog("party"))
            ui.html(
                theme.stats([(iv.RATING_LABELS[r], str(results.get(r, 0))) for r in iv.RATINGS])
            )
            st.caption(
                "Питання, які ви знаєте, повернуться пізніше, а «Не знаю» вже завтра. Повертайтеся "
                "щодня: повторення працює лише регулярно."
            )
        return
    question = questions[queue[position]]
    ui.section(f"Питання {position + 1} з {len(queue)}")
    st.progress(position / len(queue))
    with st.container(border=True):
        frog, body = st.columns([1, 5])
        with frog:
            ui.html(_frog(mood))
            line = st.session_state.get("iv_line")
            if line:
                st.caption(line)
        with body:
            ui.html(
                f'<div class="dw-q-meta">{escape(question.skill)} · {escape(question.level)}</div>'
                f'<div class="dw-lead">{escape(question.question)}</div>'
            )
            if not st.session_state.get("iv_show"):
                st.button("Показати відповідь", key="iv_reveal", on_click=reveal)
            else:
                ui.html(f'<div class="dw-answer">{escape(question.answer)}</div>')
                st.caption("Скажіть відповідь своїми словами й чесно оцініть себе.")
                for column, rating in zip(st.columns(len(iv.RATINGS)), iv.RATINGS, strict=True):
                    column.button(
                        iv.RATING_LABELS[rating], key=f"iv_rate_{rating}", on_click=rate,
                        args=(rating,), width="stretch",
                    )  # fmt: skip


session()

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
