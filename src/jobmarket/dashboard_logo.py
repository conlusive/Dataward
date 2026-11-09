"""The pixel logo: three rising bars, DATAWARD in a 5x7 pixel font, and a full stop.

Everything is drawn from the tables below, so the logo, the sidebar icon and the favicon are
generated, not hand-edited. ``python -m jobmarket.dashboard_logo`` rewrites the files in
``dashboard/static``; a test keeps the committed copies equal to what this module produces.
The stop is static on purpose (the blinking cursor lives in the page titles only).
"""

import io
from pathlib import Path

from jobmarket import dashboard_theme as t

# 5 columns by 7 rows; "1" is a lit pixel. Only the letters of the name are drawn.
GLYPHS = {
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
}
WIDTH, HEIGHT = 5, 7
GAP = 2  # columns between letters: the one-pixel shadow must not close the gap
BARS = (3, 5, 7)  # heights of the emblem's bars, one column each with a column between
EMBLEM_WIDTH = len(BARS) * 2 - 1
EMBLEM_GAP = 3  # columns between the emblem and the first letter
DOT = 2  # the full stop is DOT x DOT pixels
SHADOW = "#4B4986"  # a darker step of the accent, one pixel down and right
DOT_COLOUR = t.SERIES[1]  # the terracotta of the second chart colour
STATIC = Path(__file__).resolve().parents[2] / "dashboard" / "static"


def _emblem() -> list[tuple[int, int]]:
    """The cells of the rising bars, standing on the bottom row."""
    return [(i * 2, HEIGHT - 1 - row) for i, h in enumerate(BARS) for row in range(h)]


def _letters(text: str, left: int) -> list[tuple[int, int, int]]:
    """(column, row, letter index) of every lit pixel; letters are ``GAP`` columns apart."""
    lit = []
    for index, letter in enumerate(text):
        origin = left + index * (WIDTH + GAP)
        for row, line in enumerate(GLYPHS[letter]):
            lit += [(origin + col, row, index) for col, on in enumerate(line) if on == "1"]
    return lit


def _path(cells: list[tuple[int, int]], dx: int = 0, dy: int = 0) -> str:
    return "".join(f"M{x + dx} {y + dy}h1v1h-1z" for x, y in cells)


def _svg(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width * 4}" height="{height * 4}" shape-rendering="crispEdges" '
        f'role="img" aria-label="Dataward">{body}</svg>\n'
    )


def _dot(x: int) -> str:
    return f'<rect x="{x}" y="{HEIGHT - DOT}" width="{DOT}" height="{DOT}" fill="{DOT_COLOUR}"/>'


def wordmark_svg(text: str = "DATAWARD", *, split: int = 4) -> str:
    """The emblem, the name (the first ``split`` letters in the accent, the rest in ink), a stop."""
    left = EMBLEM_WIDTH + EMBLEM_GAP
    lit = _letters(text, left)
    first = [(x, y) for x, y, i in lit if i < split]
    second = [(x, y) for x, y, i in lit if i >= split]
    emblem = _emblem()
    end = left + len(text) * (WIDTH + GAP) - GAP
    dot_x = end + 1
    body = (
        f'<path fill="{SHADOW}" d="{_path(emblem + first + second, 1, 1)}"/>'
        f'<path fill="{t.ACCENT}" d="{_path(emblem + first)}"/>'
        f'<path fill="{t.INK}" d="{_path(second)}"/>' + _dot(dot_x)
    )
    return _svg(dot_x + DOT + 1, HEIGHT + 1, body)


def icon_svg() -> str:
    """The rising bars and the stop: the sidebar icon when the panel is collapsed."""
    emblem = _emblem()
    dot_x = EMBLEM_WIDTH + 1
    body = (
        f'<path fill="{SHADOW}" d="{_path(emblem, 1, 1)}"/>'
        f'<path fill="{t.ACCENT}" d="{_path(emblem)}"/>' + _dot(dot_x)
    )
    return _svg(dot_x + DOT + 1, HEIGHT + 1, body)


def favicon_png(size: int = 64) -> bytes:
    """A square tab icon: the rising bars and the stop on the dashboard surface."""
    from PIL import Image, ImageDraw  # Pillow comes with Streamlit; only this function needs it

    columns = EMBLEM_WIDTH + 1 + DOT
    cell = size // (columns + 3)
    canvas = Image.new("RGB", (size, size), t.BG)
    draw = ImageDraw.Draw(canvas)
    left = (size - columns * cell) // 2
    top = (size - HEIGHT * cell) // 2

    def fill(x: int, y: int, wide: int, colour: str) -> None:
        box = [left + x * cell, top + y * cell, left + (x + wide) * cell - 1]
        draw.rectangle([*box, top + (y + 1) * cell - 1], fill=colour)

    for x, y in _emblem():
        fill(x, y, 1, t.ACCENT)
    for row in range(DOT):
        fill(EMBLEM_WIDTH + 1, HEIGHT - DOT + row, DOT, DOT_COLOUR)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def write_assets(directory: Path = STATIC) -> list[Path]:
    """Write ``logo.svg``, ``icon.svg`` and ``favicon.png``; returns the paths."""
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "logo.svg": wordmark_svg().encode("utf-8"),
        "icon.svg": icon_svg().encode("utf-8"),
        "favicon.png": favicon_png(),
    }
    paths = []
    for name, content in files.items():
        path = directory / name
        path.write_bytes(content)
        paths.append(path)
    return paths


if __name__ == "__main__":
    for written in write_assets():
        print(written)
