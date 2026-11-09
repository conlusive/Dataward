"""Charts in the dashboard's look, built with Altair (it ships with Streamlit).

Marks follow the dataviz rules: thin bars with a rounded data end, two-pixel lines, markers of at
least eight pixels, hairline grid, a legend only when two series share a chart, values on the
marks selectively, and a tooltip on every mark. Colours come from ``dashboard_theme``; a source
keeps its colour whatever the filter leaves on the screen.

Every function takes a frame with the fixed column names it documents (the pages prepare it), so
no field name carries a space or a dot that Vega would read as a path.
"""

from typing import Any, Literal

import altair as alt
import pandas as pd

from jobmarket import dashboard_theme as t

FONT = "JetBrains Mono, ui-monospace, Menlo, monospace"


def series_domain(names: list[str]) -> tuple[list[str], list[str]]:
    """A fixed colour per series: the known sources first, any other series after them."""
    known = [name for name in t.SOURCE_ORDER if name in names]
    rest = sorted(name for name in names if name not in known)
    ordered = known + rest
    colors = [t.SERIES[i % len(t.SERIES)] for i in range(len(ordered))]
    return ordered, colors


def _finish(chart: Any, height: int) -> Any:
    """The shared chrome: transparent surface, hairline grid, muted text, a quiet legend."""
    return (
        chart.properties(
            height=height,
            background="transparent",
            padding={"left": 2, "right": 10, "top": 6, "bottom": 2},
        )
        .configure_view(stroke=None)
        .configure_axis(
            domain=False,
            ticks=False,
            grid=True,
            gridColor=t.GRID,
            gridWidth=1,
            labelColor=t.INK_3,
            labelFont=FONT,
            labelFontSize=11,
            labelPadding=6,
            titleColor=t.INK_3,
            titleFont=FONT,
            titleFontSize=11,
            titleFontWeight="normal",
        )  # fmt: skip
        .configure_legend(
            orient="top",
            title=None,
            labelColor=t.INK_2,
            labelFont=FONT,
            labelFontSize=11,
            symbolType="stroke",
            symbolStrokeWidth=3,
            padding=0,
            offset=8,
        )  # fmt: skip
    )


def _ticks(count: int, interval: Literal["day", "month"], *, most: int = 7) -> Any:
    """One tick per day (or month) while they fit, else every n-th, so no label repeats."""
    return alt.TimeIntervalStep(interval=interval, step=max(1, -(-count // most)))


def _date(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    out = frame.copy()
    out[column] = pd.to_datetime(out[column])
    return out


def lines(wide: pd.DataFrame, *, height: int = 300) -> Any:
    """A line per series over days. ``wide`` is indexed by date, one column per series.

    One crosshair tooltip lists every series at the day under the pointer. With one or two days
    the dots stay visible (there is no line to see yet); with more they appear under the pointer.
    """
    long = (
        wide.rename_axis("date")
        .reset_index()
        .melt(id_vars="date", var_name="series", value_name="value")
    )
    long = _date(long, "date")
    names, colors = series_domain([str(c) for c in wide.columns])
    color = alt.Color(
        "series:N", scale=alt.Scale(domain=names, range=colors), legend=alt.Legend(title=None)
    )
    x = alt.X(
        "yearmonthdate(date):T",
        axis=alt.Axis(
            format="%d.%m",
            labelAngle=0,
            title=None,
            grid=False,
            tickCount=_ticks(long["date"].nunique(), "day"),
        ),
    )
    y = alt.Y(
        "value:Q", axis=alt.Axis(format=",d", title=None, tickCount=4), scale=alt.Scale(zero=True)
    )
    nearest = alt.selection_point(
        nearest=True, on="pointerover", fields=["date"], empty=False, clear="pointerout"
    )
    always = long["date"].nunique() <= 2
    base = alt.Chart(long).encode(x=x, y=y, color=color)
    line = base.mark_line(strokeWidth=2, interpolate="linear")
    dots = base.mark_point(filled=True, size=70, stroke=t.CARD, strokeWidth=2).encode(
        opacity=alt.value(1) if always else alt.condition(nearest, alt.value(1), alt.value(0))
    )
    columns = [str(c) for c in wide.columns]
    pivot = _date(wide.rename_axis("date").reset_index(), "date")
    pivot.columns = pd.Index(["date", *columns])
    tips = [alt.Tooltip("date:T", title="Дата", format="%d.%m.%Y")] + [
        alt.Tooltip(f"{name}:Q", title=name, format=",d") for name in columns
    ]
    picker = alt.Chart(pivot).mark_point(opacity=0).encode(x="date:T").add_params(nearest)
    rule = (
        alt.Chart(pivot)
        .mark_rule(color=t.LINE, strokeWidth=1)
        .encode(x="date:T", tooltip=tips)
        .transform_filter(nearest)
    )
    return _finish(alt.layer(line, dots, picker, rule), height)


def ranked_bars(
    frame: pd.DataFrame, *, fmt: str = ",d", unit: str = "", height: int | None = None,
    emphasis: str | None = None,
) -> Any:  # fmt: skip
    """Horizontal bars, largest first, the value at the tip. Columns: ``label``, ``value``.

    One hue, because the order already says "more". ``emphasis`` greys everything but that label.
    """
    order = frame["label"].tolist()
    size = 18
    rows = max(len(frame), 1)
    hover = alt.selection_point(on="pointerover", fields=["label"], empty=False, clear="pointerout")
    color: Any = alt.value(t.MARK)
    if emphasis is not None:
        color = alt.condition(
            alt.datum.label == emphasis, alt.value(t.MARK), alt.value(t.MUTED_MARK)
        )
    base = alt.Chart(frame).encode(
        y=alt.Y(
            "label:N",
            sort=order,
            axis=alt.Axis(title=None, labelLimit=190, grid=False, labelColor=t.INK_2),
        ),
        x=alt.X("value:Q", axis=None, scale=alt.Scale(zero=True, nice=False)),
    )
    bars = (
        base.mark_bar(size=size, cornerRadiusEnd=4)
        .encode(
            color=color,
            opacity=alt.condition(hover, alt.value(1), alt.value(0.88)),
            tooltip=[
                alt.Tooltip("label:N", title="Навичка"),
                alt.Tooltip("value:Q", title=unit or "Значення", format=fmt),
            ],
        )
        .add_params(hover)
    )
    labels = base.mark_text(align="left", dx=7, color=t.INK, font=FONT, fontSize=11).encode(
        text=alt.Text("value:Q", format=fmt)
    )
    return _finish(alt.layer(bars, labels), height or rows * (size + 12) + 8)


def grouped_columns(
    frame: pd.DataFrame, *, height: int = 260, order: list[str] | None = None
) -> Any:
    """Columns per day, one per series side by side. Columns: ``date``, ``series``, ``value``."""
    data = frame.copy()
    data["day"] = pd.to_datetime(data["date"]).dt.strftime("%d.%m")
    days = data.sort_values("date")["day"].drop_duplicates().tolist()
    names, colors = series_domain(sorted(data["series"].unique().tolist()))
    if order:
        names, colors = order, [t.SERIES[i % len(t.SERIES)] for i in range(len(order))]
    base = alt.Chart(data).encode(
        x=alt.X("day:N", sort=days, axis=alt.Axis(title=None, labelAngle=0, grid=False)),
        xOffset=alt.XOffset("series:N", sort=names),
        y=alt.Y("value:Q", axis=alt.Axis(title=None, format=",d", tickCount=4)),
        color=alt.Color(
            "series:N", scale=alt.Scale(domain=names, range=colors), legend=alt.Legend(title=None)
        ),
    )
    bars = base.mark_bar(size=10, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        tooltip=[
            alt.Tooltip("day:N", title="День"),
            alt.Tooltip("series:N", title="Показник"),
            alt.Tooltip("value:Q", title="Вакансій", format=",d"),
        ]
    )
    return _finish(bars, height)


def ranges(frame: pd.DataFrame, *, unit: str = "USD/міс", height: int | None = None) -> Any:
    """A range per row with a dot on the middle value: ``label``, ``low``, ``mid``, ``high``.

    Used for percentiles (p25-median-p75, p10-p50-p90): the bar is where the middle half (or
    eight in ten) of the values sit, the dot is the typical one.
    """
    order = frame["label"].tolist()
    rows = max(len(frame), 1)
    base = alt.Chart(frame).encode(
        y=alt.Y(
            "label:N",
            sort=order,
            axis=alt.Axis(title=None, labelLimit=190, grid=False, labelColor=t.INK_2),
        ),
    )
    x_low = alt.X(
        "low:Q",
        axis=alt.Axis(title=unit, format=",d", tickCount=5),
        scale=alt.Scale(zero=False, nice=True),
    )
    tips = [
        alt.Tooltip("label:N", title=""),
        alt.Tooltip("low:Q", title="нижня межа", format=",.0f"),
        alt.Tooltip("mid:Q", title="типова", format=",.0f"),
        alt.Tooltip("high:Q", title="верхня межа", format=",.0f"),
    ]
    span = base.mark_rule(strokeWidth=8, strokeCap="round", color=t.MARK, opacity=0.4).encode(
        x=x_low, x2="high:Q", tooltip=tips
    )
    dot = base.mark_point(filled=True, size=110, color=t.MARK, stroke=t.CARD, strokeWidth=2).encode(
        x="mid:Q", tooltip=tips
    )
    return _finish(alt.layer(span, dot), height or rows * 34 + 50)


def share_trend(frame: pd.DataFrame, *, height: int = 240) -> Any:
    """One series over months, a faint wash under the line: ``month``, ``value`` (0-1)."""
    data = _date(frame, "month")
    base = alt.Chart(data).encode(
        x=alt.X(
            "yearmonth(month):T",
            axis=alt.Axis(
                format="%m.%Y",
                title=None,
                labelAngle=0,
                grid=False,
                tickCount=_ticks(data["month"].nunique(), "month"),
            ),
        ),
        y=alt.Y(
            "value:Q",
            axis=alt.Axis(format=".0%", title=None, tickCount=4),
            scale=alt.Scale(zero=True),
        ),
    )
    tips = [
        alt.Tooltip("month:T", title="Місяць", format="%m.%Y"),
        alt.Tooltip("value:Q", title="Частка вакансій", format=".1%"),
    ]
    area = base.mark_area(color=t.MARK, opacity=0.1)
    line = base.mark_line(color=t.MARK, strokeWidth=2)
    dots = base.mark_point(color=t.MARK, filled=True, size=70, stroke=t.CARD, strokeWidth=2).encode(
        tooltip=tips
    )
    return _finish(alt.layer(area, line, dots), height)


def survey_band(frame: pd.DataFrame, *, height: int = 260) -> Any:
    """Median by year with the p25-p75 band. Columns: ``year``, ``low``, ``mid``, ``high``."""
    base = alt.Chart(frame).encode(
        x=alt.X("year:O", axis=alt.Axis(title=None, labelAngle=0, grid=False)),
    )
    tips = [
        alt.Tooltip("year:O", title="Рік"),
        alt.Tooltip("low:Q", title="p25", format=",.0f"),
        alt.Tooltip("mid:Q", title="медіана", format=",.0f"),
        alt.Tooltip("high:Q", title="p75", format=",.0f"),
    ]
    band = base.mark_area(color=t.MARK, opacity=0.14).encode(
        y=alt.Y(
            "low:Q",
            axis=alt.Axis(title="USD/міс", format=",d", tickCount=5),
            scale=alt.Scale(zero=False),
        ),
        y2="high:Q",
    )
    line = base.mark_line(color=t.MARK, strokeWidth=2).encode(y="mid:Q")
    dots = base.mark_point(color=t.MARK, filled=True, size=70, stroke=t.CARD, strokeWidth=2).encode(
        y="mid:Q", tooltip=tips
    )
    return _finish(alt.layer(band, line, dots), height)
