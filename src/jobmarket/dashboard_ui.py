"""Streamlit helpers shared by the dashboard pages: cached loading and error handling."""

from html import escape
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import streamlit as st

from jobmarket import dashboard_data as dd
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
    title: str, subtitle: str = "", *, eyebrow: str = "Dataward", pills: list[str] | None = None
) -> None:
    """The page title: an <h1> with a small label above it and status chips on the right."""
    st.markdown(theme.hero(eyebrow, title, subtitle, pills), unsafe_allow_html=True)


def section(label: str, number: int | None = None) -> None:
    st.markdown(theme.section(label, number), unsafe_allow_html=True)


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


def _has(value: Any) -> bool:
    return bool(pd.notna(value))


def vacancy_card(row: Any) -> None:
    """One vacancy in full: title, facts, skills (required ones marked) and the links out."""
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
