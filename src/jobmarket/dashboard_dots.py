"""Dot-matrix figures: a ring, columns, a waffle and a spark line, all made of dots.

Plain SVG strings, no chart library: they draw at once and need no script. A dot is a unit you can
count, so each figure says what one dot stands for in its accessible label and its tooltips. The
colours come from ``dashboard_theme``; text is escaped. Values are clamped, an empty input gives an
empty figure rather than an error.
"""

import math
from collections.abc import Sequence
from html import escape

from jobmarket import dashboard_theme as t

REST = "var(--dot-rest)"  # a dot that is not lit: the track of a ring, the empty cells of a column


def _svg(width: float, height: float, body: str, label: str, *, cls: str = "") -> str:
    return (
        f'<svg class="dw-dots {cls}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'viewBox="0 0 {width:g} {height:g}" aria-label="{escape(label)}">{body}</svg>'
    )


def _dot(x: float, y: float, r: float, fill: str, title: str = "", index: int = 0) -> str:
    tip = f"<title>{escape(title)}</title>" if title else ""
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:g}" fill="{fill}" style="--i:{index}">'
        f"{tip}</circle>"
    )


def ring(ratio: float, caption: str, *, colour: str = t.ACCENT, dots: int = 36) -> str:
    """One value from 0 to 1 as a circle of dots: the lit ones are the share, clockwise from 12.

    Two rows of dots (an outer and an inner circle) give it body; the percent sits in the middle.
    """
    share = min(max(float(ratio), 0.0), 1.0)
    lit = round(share * dots)
    body = []
    for row, (radius, size) in enumerate(((44, 2.6), (36, 1.9))):
        for i in range(dots):
            angle = 2 * math.pi * i / dots - math.pi / 2
            x, y = 50 + radius * math.cos(angle), 50 + radius * math.sin(angle)
            body.append(_dot(x, y, size, colour if i < lit else REST, index=i if row == 0 else 0))
    percent = f"{share:.0%}"
    body.append(
        f'<text class="dw-num" x="50" y="57" font-size="20" text-anchor="middle">{percent}</text>'
    )
    return _svg(100, 100, "".join(body), f"{caption}: {percent}", cls="dw-dot-ring")


def columns(
    labels: Sequence[str],
    parts: Sequence[tuple[str, str, Sequence[float]]],
    *,
    rows: int = 12,
    unit: str = "",
) -> str:
    """Stacked columns of dots, one column per label (a day): the taller, the more.

    ``parts`` are (name, colour, values per label), drawn from the bottom in that order. A column
    has at most ``rows`` dots; the tallest total fills them all and the others are scaled to it, so
    a dot stands for the same amount everywhere. Each part of a column gets at least one dot when
    it is not zero, so nothing that exists disappears.
    """
    count = len(labels)
    totals = [sum(float(values[i]) for _, _, values in parts) for i in range(count)]
    top = max(totals, default=0.0)
    if count == 0 or top <= 0:
        return _svg(100, 20, "", "немає даних", cls="dw-dot-cols")
    per_dot = top / rows
    step = 9.0  # between the dots of a column
    gap = max(26.0, min(34.0, 300 / count))  # wide enough for a number over every column
    top_pad, foot = 22.0, 14.0  # room for the totals and the key above, the days below
    width, height = (count - 1) * gap + 30, rows * step + top_pad + foot
    every = max(1, -(-count // 14))  # a label on every column while they fit, else every n-th
    body = [
        '<text class="dw-dot-axis" x="0" y="6" font-size="5.5">одна крапка ≈ '
        + f"{per_dot:,.0f}".replace(",", "\u00a0")
        + (f" {escape(unit)}" if unit else "")
        + "</text>"
    ]
    for i, label in enumerate(labels):
        x = 15 + i * gap
        values_here = [float(values[i]) for _, _, values in parts]
        counts = [max(1, round(v / per_dot)) if v > 0 else 0 for v in values_here]
        while sum(counts) > rows:  # "at least one dot" may overshoot: the biggest part gives way
            counts[counts.index(max(counts))] -= 1
        base = height - foot - 4
        used = 0
        for (name, colour, _), value, dots in zip(parts, values_here, counts, strict=True):
            tip = f"{label} · {name}: {value:,.0f}".replace(",", "\u00a0") + (
                f" {unit}" if unit else ""
            )
            for k in range(dots):
                body.append(_dot(x, base - (used + k) * step, 3.2, colour, tip, index=i))
            used += dots
        for k in range(used, rows):  # the unlit rest of the column, so the grid reads as a grid
            body.append(_dot(x, base - k * step, 1.2, REST))
        if i % every == 0 or i == count - 1:
            total = f"{totals[i]:,.0f}".replace(",", "\u00a0")
            body.append(  # the number itself over the column: dots are for shape, this is the fact
                f'<text class="dw-num" x="{x:.1f}" y="{base - used * step - 1:.1f}" '
                f'font-size="7" text-anchor="middle">{total}</text>'
            )
            body.append(
                f'<text class="dw-dot-axis" x="{x:.1f}" y="{height - 2:g}" font-size="5.5" '
                f'text-anchor="middle">{escape(label)}</text>'
            )
    summary = f"стовпчики з крапок, одна крапка ≈ {per_dot:,.0f}".replace(",", "\u00a0")
    return _svg(width, height, "".join(body), f"{summary} {unit}".strip(), cls="dw-dot-cols")


def balance(
    labels: Sequence[str],
    up: tuple[str, str, Sequence[float]],
    down: tuple[str, str, Sequence[float]],
    *,
    rows: int = 6,
) -> str:
    """Two things per day from one axis: ``up`` grows upwards, ``down`` downwards.

    For arrivals against departures: the day is a column with dots above the axis (arrived) and
    below it (left), and the number of each at the end of its dots. A dot is worth the same amount
    on both sides (the biggest value of either fills ``rows`` dots); a value that exists keeps one.
    """
    count = len(labels)
    peak = max([float(v) for v in (*up[2], *down[2])], default=0.0)
    if count == 0 or peak <= 0:
        return _svg(100, 20, "", "немає даних", cls="dw-dot-cols")
    per_dot, step = peak / rows, 9.0
    gap = max(26.0, min(34.0, 300 / count))
    axis = 14 + rows * step
    width, height = (count - 1) * gap + 30, 2 * rows * step + 36
    every = max(1, -(-count // 14))
    body = [
        f'<text class="dw-dot-axis" x="0" y="6" font-size="5.5">одна крапка ≈ '
        f"{per_dot:,.0f}</text>".replace(",", "\u00a0"),
        f'<line x1="6" x2="{width - 6:g}" y1="{axis:g}" y2="{axis:g}" stroke="{t.LINE}"/>',
    ]
    for i, label in enumerate(labels):
        x = 15 + i * gap
        for sign, (name, colour, values) in ((-1, up), (1, down)):
            value = float(values[i])
            dots = min(rows, max(1, round(value / per_dot))) if value > 0 else 0
            tip = f"{label} · {name}: {value:,.0f}".replace(",", "\u00a0")
            for k in range(dots):
                body.append(_dot(x, axis + sign * (6 + k * step), 3.2, colour, tip, index=i))
            if i % every == 0 or i == count - 1:
                edge = axis + sign * (6 + max(dots, 1) * step) + (-2 if sign < 0 else 8)
                body.append(
                    f'<text class="dw-num" x="{x:.1f}" y="{edge:.1f}" font-size="6.5" '
                    f'text-anchor="middle">{value:,.0f}</text>'.replace(",", "\u00a0")
                )
        if i % every == 0 or i == count - 1:
            body.append(
                f'<text class="dw-dot-axis" x="{x:.1f}" y="{height - 2:g}" font-size="5.5" '
                f'text-anchor="middle">{escape(label)}</text>'
            )
    summary = f"{up[0]} угору, {down[0]} вниз, одна крапка ≈ {per_dot:,.0f}".replace(",", "\u00a0")
    return _svg(width, height, "".join(body), summary, cls="dw-dot-cols")


def flow(
    labels: Sequence[str],
    new: Sequence[float],
    closed: Sequence[float],
    *,
    new_colour: str,
    closed_colour: str,
    max_dots: int = 14,
) -> str:
    """One row per day: closed vacancies as dots going left, new ones going right, from one centre.

    The number of each stands at the end of its dots and the day on the left, so nothing is
    drawn over anything else however many days there are. A dot is worth the same on both sides
    (the biggest value of either fills ``max_dots``); a value that exists keeps at least one dot.
    """
    peak = max([float(v) for v in (*new, *closed)], default=0.0)
    if not labels or peak <= 0:
        return ""
    per_dot = peak / max_dots

    def run(value: float, colour: str, name: str, label: str) -> str:
        n = min(max_dots, max(1, round(value / per_dot))) if value > 0 else 0
        tip = f"{label} · {name}: {value:,.0f}".replace(",", "\u00a0")
        return "".join(
            f'<i style="background:{colour}" title="{escape(tip)}"></i>' for _ in range(n)
        )

    def figure(value: float) -> str:
        return f"{float(value):,.0f}".replace(",", "\u00a0")

    rows = []
    for label, up, down in zip(labels, new, closed, strict=True):
        rows.append(
            f'<div class="dw-flow-row"><span class="dw-flow-day">{escape(label)}</span>'
            f'<b class="dw-num">{figure(down)}</b>'
            f'<span class="dw-flow-side left">'
            f"{run(float(down), closed_colour, 'Закриті', label)}</span>"
            f'<span class="dw-flow-axis"></span>'
            f'<span class="dw-flow-side">{run(float(up), new_colour, "Нові", label)}</span>'
            f'<b class="dw-num">{figure(up)}</b></div>'
        )
    note = f"одна крапка ≈ {per_dot:,.0f}".replace(",", "\u00a0")
    return (
        f'<div class="dw-flow" role="img" aria-label="нові та закриті за днями, {escape(note)}">'
        f'<div class="dw-flow-head"><span></span><em>закриті</em><span></span><em>нові</em></div>'
        f'{"".join(rows)}<div class="dw-flow-note">{escape(note)}</div></div>'
    )


def key(parts: Sequence[tuple[str, str, float]]) -> str:
    """What a figure of parts shows, in words and numbers: a row per part with its colour, its
    name, its share (big) and its value. A reader should not have to count dots."""
    total = sum(max(float(value), 0.0) for _, _, value in parts)
    rows = []
    for name, colour, value in parts:
        share = float(value) / total if total > 0 else 0.0
        amount = f"{float(value):,.0f}".replace(",", "\u00a0")
        rows.append(
            f'<div class="dw-key-row"><span class="dw-key-dot" style="background:{colour}">'
            f'</span><span class="dw-key-name">{escape(name)}</span>'
            f'<b class="dw-num">{share:.0%}</b><em>{amount}</em></div>'
        )
    return f'<div class="dw-key">{"".join(rows)}</div>' if rows else ""


def waffle(parts: Sequence[tuple[str, str, float]], *, side: int = 10) -> str:
    """Parts of a whole as a square of dots: 100 dots, each one percent of the whole.

    ``parts`` are (name, colour, value). Largest-remainder rounding, so the dots always add up to
    the square and a small part that exists keeps at least one dot.
    """
    cells = side * side
    total = sum(max(float(value), 0.0) for _, _, value in parts)
    if total <= 0:
        return _svg(100, 100, "", "немає даних", cls="dw-dot-waffle")
    exact = [max(float(value), 0.0) / total * cells for _, _, value in parts]
    counts = [max(1, math.floor(x)) if x > 0 else 0 for x in exact]
    order = sorted(range(len(parts)), key=lambda i: exact[i] - math.floor(exact[i]), reverse=True)
    for i in order:  # hand out what the floors left over, biggest remainder first
        if sum(counts) >= cells:
            break
        if exact[i] > 0:
            counts[i] += 1
    while sum(counts) > cells:  # the "at least one" rule may overshoot: take from the biggest
        counts[counts.index(max(counts))] -= 1
    body, cell = [], 0
    step = 100 / side
    for (name, colour, value), n in zip(parts, counts, strict=True):
        tip = f"{name}: {float(value):,.0f} ({float(value) / total:.0%})".replace(",", " ")
        for _ in range(n):
            column, row = cell % side, cell // side
            body.append(
                _dot(step / 2 + column * step, step / 2 + row * step, 3.6, colour, tip, index=row)
            )
            cell += 1
    names = ", ".join(f"{name} {float(value) / total:.0%}" for name, _, value in parts)
    return _svg(100, 100, "".join(body), f"частки: {names}", cls="dw-dot-waffle")


def spark(values: Sequence[float], *, colour: str = t.ACCENT, caption: str = "") -> str:
    """A small line of dots for a trend; the last dot is bigger (it is "now")."""
    points = [float(v) for v in values]
    if not points:
        return _svg(100, 28, "", caption or "немає даних", cls="dw-dot-spark")
    low, high = min(points), max(points)
    span = (high - low) or 1.0
    gap = 96 / max(len(points) - 1, 1)
    body = []
    for i, value in enumerate(points):
        last = i == len(points) - 1
        y = 24 - (value - low) / span * 20
        tip = f"{value:,.0f}".replace(",", " ")
        body.append(_dot(2 + i * gap, y, 2.6 if last else 1.5, colour, tip, index=i))
    return _svg(100, 28, "".join(body), caption or "динаміка", cls="dw-dot-spark")
