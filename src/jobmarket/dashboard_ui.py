"""Streamlit helpers shared by the dashboard pages: cached loading and error handling."""

import re
import time
from datetime import date
from html import escape
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_interview as iv
from jobmarket import dashboard_keys as dk
from jobmarket import dashboard_mascot as mascot
from jobmarket import dashboard_mobile as dmo
from jobmarket import dashboard_motion as dm
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_progress as pg
from jobmarket import dashboard_resources as rs
from jobmarket import dashboard_theme as theme

CACHE_SECONDS = 300  # the data changes once a day; five minutes keeps a deploy's new files visible


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def _table(directory: str, name: str) -> pd.DataFrame:
    return dd.read_table(Path(directory), name)


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def _json(directory: str, name: str) -> dict[str, Any]:
    return dd.read_json(Path(directory), name)


def table(name: str) -> pd.DataFrame:
    """A gold table; a missing file or column is shown as a message and stops the page."""
    try:
        return _table(str(dd.data_dir()), name)
    except dd.DataError as error:
        st.error(f"Немає даних: {error}")
        st.stop()


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def _catalog(directory: str) -> pd.DataFrame | None:
    return dd.read_catalog(Path(directory))


def catalog() -> pd.DataFrame | None:
    """The vacancy catalog, or None when this export has none (it is local-only data)."""
    try:
        return _catalog(str(dd.data_dir()))
    except dd.DataError as error:
        st.error(f"Немає даних: {error}")
        st.stop()


def optional_document(name: str) -> dict[str, Any] | None:
    """A JSON file the page can do without (None when it is missing)."""
    try:
        return _json(str(dd.data_dir()), name)
    except dd.DataError:
        return None


def document(name: str) -> dict[str, Any]:
    try:
        return _json(str(dd.data_dir()), name)
    except dd.DataError as error:
        st.error(f"Немає даних: {error}")
        st.stop()


# ---- look -------------------------------------------------------------------------------------
def setup() -> None:
    """The stylesheet, once per rerun (called by the entry point, not by the pages)."""
    st.markdown(theme.css(), unsafe_allow_html=True)


def header(
    title: str,
    subtitle: str = "",
    *,
    eyebrow: str = "Dataward",
    pills: list[str] | None = None,
    typed: bool = False,
    domain: str | None = None,
) -> None:
    """The page title: an <h1> with a small label above it and status chips on the right."""
    st.markdown(
        theme.hero(eyebrow, title, subtitle, pills, typed_subtitle=typed, domain=domain),
        unsafe_allow_html=True,
    )


def html(markup: str) -> None:
    """Already-built markup from ``dashboard_theme`` (every piece of text in it is escaped)."""
    st.markdown(markup, unsafe_allow_html=True)


def open_with(page: str, key: str, value: object) -> None:
    """A button callback: set a filter of another page, then go there."""
    st.session_state[key] = value
    st.switch_page(page)


def section(label: str, number: int | None = None, domain: str | None = None) -> None:
    st.markdown(theme.section(label, number, domain), unsafe_allow_html=True)


def kpi(
    number: int,
    label: str,
    value: str | int,
    *,
    delta: str | float | None = None,
    help: str | None = None,
    history: list[float] | None = None,
    direction: str = "up_good",
) -> None:
    """A numbered tile: label, big value, an optional change, a sparkline of ``history``.

    ``direction`` says how to colour the change: "up_good", "down_good" or "neutral" (no colour,
    no arrow: the delta is a remark, not a change).
    """
    colors: dict[str, Literal["normal", "inverse", "off"]] = {
        "up_good": "normal", "down_good": "inverse", "neutral": "off",
    }  # fmt: skip
    st.metric(
        f"{number:02d} · {label}",
        value,
        delta=delta,
        delta_color=colors.get(direction, "off"),
        delta_arrow="off" if direction == "neutral" else "auto",
        help=help,
        border=True,
        chart_data=history if history and len(history) > 1 else None,
        chart_type="line",
    )


def keep(*keys: str) -> None:
    """Keep the values of widgets that are not drawn on this run (the ones in a closed tab)."""
    for key in keys:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def chart(figure: Any) -> None:
    """An Altair chart in the dashboard's look (the chart carries its own colours)."""
    st.altair_chart(figure, theme=None, width="stretch")


def card(title: str, note: str = "") -> Any:
    """A bordered block with a small heading; use it as a context manager."""
    box = st.container(border=True)
    box.markdown(theme.card_title(title, note), unsafe_allow_html=True)
    return box


def sidebar_label(text: str) -> None:
    """A small heading in the sidebar, above a group of filters."""
    st.sidebar.markdown(theme.side_label(text), unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def question_bank() -> list[iv.Question]:
    """The interview questions (a file that does not change while the app runs)."""
    return iv.load_bank()


@st.cache_resource(show_spinner=False)
def resource_bank() -> dict[str, list[rs.Resource]]:
    """The curated learning resources."""
    return rs.load()


def pet_state(profile: pr.Profile, today: date | None = None) -> dict[str, Any]:
    """What the frog shows: stage, level, mood, experience, streak and the questions due."""
    today = today or date.today()
    counts = iv.counts(question_bank(), profile.practice, today)
    parts = pg.xp_breakdown(profile, counts)
    info = pg.level_info(sum(parts.values()))
    return {
        "counts": counts, "parts": parts, "level": info, "stage": pg.stage(info.level),
        "mood": pg.mood(profile, today), "streak": pg.streak(profile.activity, today),
        "today": pg.answers_on(profile, today),
    }  # fmt: skip


def avatar_card() -> None:
    """You, at the foot of the sidebar: the frog in a frame, a name, a level, what waits."""
    profile = pr.load()
    state = pet_state(profile)
    info, stage = state["level"], state["stage"]
    notes = [f"серія {state['streak']} дн."] if state["streak"] else []
    notes.append(f"сьогодні {state['today']}/{profile.goal}")
    due = state["counts"]["due"]
    with st.sidebar.container(key="dw_avatar"):
        st.markdown(
            theme.avatar(
                mascot.frog_svg(stage.key, state["mood"], label=stage.name),
                profile.name or "Гість",
                info.level,
                stage.name,
                info.ratio,
                notes,
            ),  # fmt: skip
            unsafe_allow_html=True,
        )
        with st.container(key="dw_avatar_open"):
            st.page_link("views/profile.py", label="Мій профіль")
        if due:
            st.page_link("views/practice.py", label=f"Повторити питань: {due} →")


def scripts() -> None:
    """Install the shortcuts, the page-enter motion and the phone drawer; they show nothing."""
    with st.container(key="dw_scripts"):
        st.html(dk.script(), unsafe_allow_javascript=True)
        st.html(dm.script(), unsafe_allow_javascript=True)
        st.html(dmo.script(), unsafe_allow_javascript=True)


def go_practice(skill: str) -> None:
    """A button callback: open the trainer on one skill."""
    st.session_state.update(iv_scope="Одна навичка", iv_skill=skill)
    st.switch_page("views/practice.py")


def profile() -> pr.Profile:
    """The saved profile (an empty one on a fresh machine)."""
    return pr.load()


UNDO_SECONDS = 180  # how long a done action can be taken back
UNDO_LIMIT = 20


def persist(profile: pr.Profile, what: str | None = None) -> bool:
    """Write the profile; a failure is a message on the page, not a stack trace.

    With ``what`` (a short phrase: "Збережено вакансію") the state before the write is kept, so the
    action can be taken back with ``undo``. Routine writes, like a trainer answer, pass nothing.
    """
    before = pr.load() if what else None  # the file is still as it was before this action
    try:
        pr.save(profile)
    except OSError as error:
        st.error(f"Не вдалося зберегти профіль у {pr.default_path()}: {error}")
        return False
    if what and before is not None and before != profile:
        stack = st.session_state.setdefault("_undo", [])
        stack.append((what, before, time.time()))
        del stack[:-UNDO_LIMIT]
    return True


def _undoable() -> list[tuple[str, pr.Profile, float]]:
    """The actions that can still be taken back, the newest last; old ones are forgotten."""
    stack: list[tuple[str, pr.Profile, float]] = st.session_state.get("_undo", [])
    stack[:] = [item for item in stack if time.time() - item[2] < UNDO_SECONDS]
    return stack


def undo() -> None:
    """A button callback: put the profile back as it was before the last action."""
    stack = _undoable()
    if not stack:
        return
    what, before, stamp = stack.pop()
    try:
        pr.save(before)
    except OSError as error:
        stack.append((what, before, stamp))
        st.error(f"Не вдалося скасувати: {error}")
        return
    st.toast(f"Скасовано: {what[:1].lower()}{what[1:]}", icon=":material/undo:")


def undo_bar() -> None:
    """A slim bar above the page while there is something to take back (also `z`)."""
    stack = _undoable()
    if not stack:
        return
    with st.container(key="dw_undo"):
        text, button = st.columns([7, 2], vertical_alignment="center")
        extra = f" (ще {len(stack) - 1} до цього)" if len(stack) > 1 else ""
        text.markdown(
            f'<div class="dw-undo">↶ {escape(stack[-1][0])}{extra}</div>', unsafe_allow_html=True
        )
        button.button(
            "Скасувати", key="dw_undo_btn", on_click=undo, icon=":material/undo:", width="stretch"
        )


def flash(message: str) -> None:
    """A message for the next run of the page (a button reruns it, so say it afterwards)."""
    st.session_state["_flash"] = message


def show_flash() -> None:
    message = st.session_state.pop("_flash", None)
    if message:
        st.success(message)


def _save_vacancy(row: Any) -> None:
    """A button callback: keep the vacancy in the profile."""
    current = pr.load()
    added = pr.save_vacancy(
        current, str(row["vacancy_id"]), title=str(row["title"]), company=str(row["company"]),
        url=str(row["url"]), today=date.today(),
    )  # fmt: skip
    if added and persist(current, "Збережено вакансію"):
        st.toast("Вакансію збережено в профілі.", icon=":material/bookmark_added:")


def _has(value: Any) -> bool:
    return bool(pd.notna(value))


def vacancy_card(row: Any, *, profile: pr.Profile | None = None) -> None:
    """One vacancy in full: title, facts, skills (required ones marked) and the links out.

    With a ``profile`` it also says how well the vacancy fits it and offers to save it.
    """
    # a missing link arrives as NaN, which is truthy: test it explicitly
    other = str(row["url_other"]) if _has(row["url_other"]) and row["url_other"] else ""
    rows = [
        ("Компанія", row["company"]),
        ("Напрямок", row["category"]),
        ("Рівень", "" if row["seniority"] == dd.NO_LEVEL else row["seniority"]),
        ("Зарплата", dd.salary_label(row["salary_usd_min"], row["salary_usd_max"]) + " / міс"
         if dd.salary_label(row["salary_usd_min"], row["salary_usd_max"]) else ""),
        ("Де", dd.where_label(row["locations"], row["remote"])),
        ("Досвід", f"від {row['experience_years']:g} р." if _has(row["experience_years"]) else ""),
        ("Англійська", str(row["english_level"]) if pd.notna(row["english_level"]) else ""),
        ("З'явилась", f"{row['first_listed_on']:%d.%m.%Y}"),
        ("Остання зустріч", f"{row['last_seen_on']:%d.%m.%Y}" if _has(row["last_seen_on"]) else ""),
        ("Стан", "відкрита" if row["is_open"] else "закрита"),
        ("Джерело", str(row["source"]) + (" + ще одне оголошення" if other else "")),
    ]  # fmt: skip
    st.markdown(f'<div class="dw-lead">{escape(str(row["title"]))}</div>', unsafe_allow_html=True)
    st.markdown(theme.facts(rows), unsafe_allow_html=True)
    if len(row["skills"]):
        st.markdown(
            '<div class="dw-muted">Навички (■ — названо вимогою)</div>'
            + theme.chips(list(row["skills"]), list(row["skills_required"])),
            unsafe_allow_html=True,
        )
    st.link_button("Відкрити оголошення ↗", row["url"])
    if other:
        st.link_button("Те саме оголошення на іншому сайті ↗", other)
    if profile is None:
        return
    mine = profile.known()
    if mine and len(row["skills"]):
        score, _, missing = pr.match(list(row["skills"]), list(row["skills_required"]), mine)
        lacking = ", ".join(missing[:5]) + (f" +{len(missing) - 5}" if len(missing) > 5 else "")
        st.markdown(
            f'<div class="dw-muted">Збіг із вашим профілем: <b>{(score or 0):.0%}</b>'
            + (f"; бракує: {escape(lacking)}" if missing else "; бракує: нічого") + "</div>",
            unsafe_allow_html=True,
        )  # fmt: skip
    saved = str(row["vacancy_id"]) in profile.saved
    st.button(
        "✓ У профілі" if saved else "★ Зберегти у профіль",
        key=f"save_{row['vacancy_id']}", disabled=saved, on_click=_save_vacancy, args=(row,),
    )  # fmt: skip


# ---- a list of vacancies you can act on ---------------------------------------------------------
def _turn(key: str, step: int) -> None:
    """A pager button: one page forward or back (the page is clamped when it is drawn)."""
    st.session_state[f"{key}_page"] = st.session_state.get(f"{key}_page", 0) + step


def _save_picked(key: str) -> None:
    """A button callback: keep every selected vacancy of the list ``key`` in the profile."""
    rows = st.session_state.get(f"{key}_picked", [])
    current = pr.load()
    added = pr.save_vacancies(current, rows, date.today())
    if added and persist(current, f"Збережено вакансій: {added}"):
        st.toast(f"Збережено вакансій: {added}", icon=":material/bookmark_added:")
    elif not added:
        st.toast("Усі вибрані вакансії вже в профілі.")


def analysis_block(row: Any, analysis: dict[str, Any], mine: set[str]) -> None:
    """One vacancy next to the market: its skills by how common they are, pay, age, rivals."""
    items = [{**item, "mine": item["skill"] in mine} for item in analysis["skills"]]
    st.markdown(
        theme.card_title("Аналіз проти ринку", "частка вакансій ринку, що просять навичку; "
                         "бірюзовим обов'язкові, ✓ у вас є"),
        unsafe_allow_html=True,
    )  # fmt: skip
    if items:
        st.markdown(theme.skill_rows(items), unsafe_allow_html=True)
    salary = analysis["salary"]
    lines = []
    if salary["mid"] is not None and salary["peer_median"]:
        delta = salary["mid"] / salary["peer_median"] - 1
        lines.append(
            f"Зарплата вакансії {dd.fmt_int(salary['mid'])} $ — {abs(delta):.0%} "
            f"{'вище' if delta >= 0 else 'нижче'} за медіану напрямку "
            f"({dd.fmt_int(salary['peer_median'])} $, вакансій із вилкою: {salary['peers']})."
        )
    elif salary["mid"] is not None:
        lines.append(f"Зарплата вакансії {dd.fmt_int(salary['mid'])} $; порівняти з напрямком "
                     "нічим: замало вакансій із вилкою.")  # fmt: skip
    else:
        lines.append("Зарплату не вказано: порівнювати нічого.")
    if analysis["days_listed"] is not None:
        lines.append(
            f"На сайті {analysis['days_listed']} дн.; схожих відкритих: {analysis['similar']}."
        )
    for line in lines:
        st.caption(line)


def _open(key: str, vacancy_id: str) -> None:
    """A row button: show this vacancy on the right."""
    st.session_state[f"{key}_shown"] = vacancy_id


def _close(key: str) -> None:
    """The "back to the list" button of the card on a phone: forget the tapped vacancy."""
    st.session_state.pop(f"{key}_shown", None)


def _plain(text: object) -> str:
    """Text for a button label, which is markdown: a title with `*`, `_` or `$` stays as typed."""
    return re.sub(r"([\\`*_\[\]$~<>])", r"\\\1", str(text))


def _row_label(row: Any, score: float | None) -> str:
    """Up to three short lines on a row: the title, the company and level, then pay and fit.

    Each kind of fact has its own line (and the theme its own colour), so a row reads at a glance
    instead of being one long string that wraps.
    """
    level = "" if row["seniority"] == dd.NO_LEVEL else str(row["seniority"])
    company = str(row["company"]) if _has(row["company"]) else ""
    pay = dd.salary_label(row["salary_usd_min"], row["salary_usd_max"])
    fit = f"збіг {score:.0%}" if score is not None else ""
    who = " · ".join(_plain(x) for x in (company, level) if x)
    # the pay sits in a code span: the theme colours it, and nothing in it needs escaping
    numbers = " · ".join(x for x in (f"`{pay}`" if pay else "", f"*{fit}*" if fit else "") if x)
    return "\n".join(x for x in (f"**{_plain(row['title'])}**", who, numbers) if x)


def vacancy_list(
    frame: pd.DataFrame,
    *,
    key: str,
    profile: pr.Profile,
    catalog: pd.DataFrame,
    shares: dict[str, float],
) -> None:
    """Vacancies as a list with the chosen one already open beside it (no clicking into a table).

    Rows on the left, 15 to a page; the vacancy on the right with its facts, skills, links, the
    comparison with the market and a save button. The first one is open at once; a click on a row
    opens another. It is a fragment, so a click redraws only the list and the card.
    """
    if frame.empty:
        st.info("За цими умовами вакансій немає.")
        return
    mine = profile.known()

    @st.fragment
    def view() -> None:
        with st.container(key=f"{key}_bar"):  # on a phone: the sort on one row, the pager below
            sorting, back, forward, where = st.columns([4, 1, 1, 3], vertical_alignment="bottom")
            sort = sorting.selectbox("Сортування", list(dd.SORTS), key=f"{key}_sort")
        ordered = dd.sort_catalog(frame, sort).reset_index(drop=True)
        signature = (sort, len(ordered), str(ordered.iloc[0]["vacancy_id"]))
        if st.session_state.get(f"{key}_sig") != signature:  # other filters or order: page one
            st.session_state[f"{key}_sig"] = signature
            st.session_state[f"{key}_page"] = 0
            st.session_state.pop(f"{key}_shown", None)
        page, first, last = dd.page_of(
            len(ordered), st.session_state.get(f"{key}_page", 0), dd.PAGE_SIZE
        )
        st.session_state[f"{key}_page"] = page
        pages = max(1, -(-len(ordered) // dd.PAGE_SIZE))
        back.button(
            "←", key=f"{key}_back", on_click=_turn, args=(key, -1), disabled=page == 0,
            width="stretch", help="Попередня сторінка",
        )  # fmt: skip
        forward.button(
            "→", key=f"{key}_next", on_click=_turn, args=(key, 1), disabled=page >= pages - 1,
            width="stretch", help="Наступна сторінка",
        )  # fmt: skip
        where.markdown(
            f'<div class="dw-pager">{first + 1}–{last} з {dd.fmt_int(len(ordered))}</div>',
            unsafe_allow_html=True,
        )
        shown = ordered.iloc[first:last].reset_index(drop=True)
        ids = shown["vacancy_id"].astype(str).tolist()
        opened = st.session_state.get(f"{key}_shown")
        if opened not in ids:  # nothing chosen yet, or it is on another page: open the first
            opened = ids[0]
        listing, detail = st.columns([5, 6], gap="medium")
        with listing, st.container(key=f"{key}_rows"):
            for vacancy_id, (_, row) in zip(ids, shown.iterrows(), strict=True):
                score = (
                    pr.match(list(row["skills"]), list(row["skills_required"]), mine)[0]
                    if mine
                    else None
                )
                st.button(
                    _row_label(row, score if mine else None), key=f"{key}_row_{vacancy_id}",
                    type="primary" if vacancy_id == opened else "secondary",
                    on_click=_open, args=(key, vacancy_id), width="stretch",
                )  # fmt: skip
        # a tapped row changes the key of the "back" button, and only of it: on a phone the
        # stylesheet then lays the card over the whole screen (below the list it would be a page
        # away). The card itself keeps its key, so a click does not mount it anew
        tapped = f"{key}_shown" in st.session_state
        with detail, st.container(border=True, key=f"{key}_detail"):
            st.button(
                "← До списку",
                key=f"{key}_close{'_open' if tapped else ''}",
                on_click=_close,
                args=(key,),
                width="stretch",
            )  # fmt: skip  (shown on a phone only)
            row = shown.iloc[ids.index(opened)]
            vacancy_card(row, profile=profile)
            analysis_block(row, dd.vacancy_analysis(row, catalog, shares), mine)
        st.session_state[f"{key}_picked"] = [
            {
                "id": str(r["vacancy_id"]), "title": str(r["title"]),
                "company": str(r["company"]), "url": str(r["url"]),
            }
            for _, r in shown.iterrows()
        ]  # fmt: skip
        save, csv = st.columns([1, 1])
        save.button(
            f"★ Зберегти всі на сторінці ({len(shown)})", key=f"{key}_save",
            on_click=_save_picked, args=(key,),
        )  # fmt: skip
        csv.download_button(
            "Завантажити CSV (усе)", dd.catalog_table(ordered).to_csv(index=False).encode("utf-8"),
            file_name=f"dataward_{key}.csv", mime="text/csv", key=f"{key}_csv",
        )  # fmt: skip

    view()
