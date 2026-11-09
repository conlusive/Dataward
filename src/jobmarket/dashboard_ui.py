"""Streamlit helpers shared by the dashboard pages: cached loading and error handling."""

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
