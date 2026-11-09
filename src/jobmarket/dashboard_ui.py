"""Streamlit helpers shared by the dashboard pages: cached loading and error handling."""

from datetime import date
from html import escape
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import streamlit as st

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_interview as iv
from jobmarket import dashboard_mascot as mascot
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
        st.page_link("views/profile.py", label="Мій профіль →")
        if due:
            st.page_link("views/practice.py", label=f"Повторити питань: {due} →")


def go_practice(skill: str) -> None:
    """A button callback: open the trainer on one skill."""
    st.session_state.update(iv_scope="Одна навичка", iv_skill=skill)
    st.switch_page("views/practice.py")


def profile() -> pr.Profile:
    """The saved profile (an empty one on a fresh machine)."""
    return pr.load()


def persist(profile: pr.Profile) -> bool:
    """Write the profile; a failure is a message on the page, not a stack trace."""
    try:
        pr.save(profile)
    except OSError as error:
        st.error(f"Не вдалося зберегти профіль у {pr.default_path()}: {error}")
        return False
    return True


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
    if added and persist(current):
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
def _save_picked(key: str) -> None:
    """A button callback: keep every selected vacancy of the list ``key`` in the profile."""
    rows = st.session_state.get(f"{key}_picked", [])
    current = pr.load()
    added = pr.save_vacancies(current, rows, date.today())
    if added and persist(current):
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


def vacancy_list(
    frame: pd.DataFrame,
    *,
    key: str,
    profile: pr.Profile,
    catalog: pd.DataFrame,
    shares: dict[str, float],
) -> None:
    """A list of vacancies: sort, select one or many, open, analyse, save, download.

    It is a fragment, so choosing a row or a sort order redraws only the list and its card.
    """
    if frame.empty:
        st.info("За цими умовами вакансій немає.")
        return
    mine = profile.known()

    @st.fragment
    def view() -> None:
        sort = st.selectbox("Сортування", list(dd.SORTS), key=f"{key}_sort")
        ordered = dd.sort_catalog(frame, sort).reset_index(drop=True)
        table = dd.catalog_table(ordered)
        if mine:
            scores = [
                pr.match(list(s), list(r), mine)[0]
                for s, r in zip(ordered["skills"], ordered["skills_required"], strict=True)
            ]
            table.insert(0, "Збіг, %", [round((x or 0) * 100) for x in scores])
        event = st.dataframe(
            table, hide_index=True, height=460, key=f"{key}_table", on_select="rerun",
            selection_mode="multi-row",
            column_config={
                "Збіг, %": st.column_config.ProgressColumn(
                    format="%d", min_value=0, max_value=100, width=110
                ),
                "Назва": st.column_config.TextColumn(width=300),
                "Компанія": st.column_config.TextColumn(width=170),
                "Напрямок": st.column_config.TextColumn(width=150),
                "Рівень": st.column_config.TextColumn(width=90),
                "Зарплата": st.column_config.TextColumn(width=140),
                "Навички": st.column_config.TextColumn(width=340),
                "Де": st.column_config.TextColumn(width=170),
                "Джерело": st.column_config.TextColumn(width=90),
                "Посилання": st.column_config.LinkColumn("Посилання", display_text="відкрити ↗"),
                "З'явилась": st.column_config.DateColumn(format="DD.MM.YYYY"),
            },
        )  # fmt: skip
        picked = [i for i in event.selection.rows if i < len(ordered)]
        st.session_state[f"{key}_picked"] = [
            {
                "id": str(ordered.iloc[i]["vacancy_id"]), "title": str(ordered.iloc[i]["title"]),
                "company": str(ordered.iloc[i]["company"]), "url": str(ordered.iloc[i]["url"]),
            }
            for i in picked
        ]  # fmt: skip
        save, csv = st.columns([1, 1])
        save.button(
            f"★ Зберегти вибрані ({len(picked)})", key=f"{key}_save", disabled=not picked,
            on_click=_save_picked, args=(key,),
        )  # fmt: skip
        csv.download_button(
            "Завантажити CSV", table.to_csv(index=False).encode("utf-8"),
            file_name=f"dataward_{key}.csv", mime="text/csv", key=f"{key}_csv",
        )  # fmt: skip
        with st.container(border=True):
            if len(picked) == 1:
                row = ordered.iloc[picked[0]]
                vacancy_card(row, profile=profile)
                analysis_block(row, dd.vacancy_analysis(row, catalog, shares), mine)
            elif picked:
                st.markdown(
                    f'<div class="dw-muted">Вибрано вакансій: {len(picked)}. Натисніть «Зберегти '
                    "вибрані», щоб додати їх у профіль, або виберіть одну, щоб побачити аналіз."
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="dw-muted">▸ Клікніть рядок: побачите вакансію й порівняння з '
                    "ринком; відмічайте кілька, щоб зберегти разом.</div>",
                    unsafe_allow_html=True,
                )

    view()
