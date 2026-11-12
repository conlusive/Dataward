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
    gap = max(step, min(30.0, 300 / count))  # between columns: few days spread out, many pack in
    width, height = (count - 1) * gap + 12, rows * step + 16
    body = []
    for i, label in enumerate(labels):
        x = 6 + i * gap
        values_here = [float(values[i]) for _, _, values in parts]
        counts = [max(1, round(v / per_dot)) if v > 0 else 0 for v in values_here]
        while sum(counts) > rows:  # "at least one dot" may overshoot: the biggest part gives way
            counts[counts.index(max(counts))] -= 1
        used = 0
        for (name, colour, _), value, dots in zip(parts, values_here, counts, strict=True):
            tip = f"{label} · {name}: {value:,.0f}".replace(",", "\u00a0") + (
                f" {unit}" if unit else ""
            )
            for k in range(dots):
                y = height - 14 - (used + k) * step
                body.append(_dot(x, y, 3.2, colour, tip, index=i))
            used += dots
        for k in range(used, rows):  # the unlit rest of the column, so the grid reads as a grid
            body.append(_dot(x, height - 14 - k * step, 1.2, REST))
        if i in (0, count - 1) or (count > 8 and i % max(1, count // 6) == 0):
            body.append(
                f'<text class="dw-dot-axis" x="{x:.1f}" y="{height - 2:g}" font-size="5.5" '
                f'text-anchor="middle">'
                f"{escape(label)}</text>"
            )
    summary = f"стовпчики з крапок, одна крапка ≈ {per_dot:,.0f}".replace(",", " ")
    return _svg(width, height, "".join(body), f"{summary} {unit}".strip(), cls="dw-dot-cols")


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
