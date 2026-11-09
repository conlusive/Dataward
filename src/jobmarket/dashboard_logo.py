"""The pixel logo: DATAWARD spelled in a 5x7 pixel font, with a shadow and a blinking cursor.

Everything is drawn from the glyph table below, so the logo, the sidebar icon and the favicon are
generated, not hand-edited. ``python -m jobmarket.dashboard_logo`` rewrites the files in
``dashboard/static``; a test keeps the committed copies equal to what this module produces.
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
CURSOR_WIDTH = 3
SHADOW = "#4B4986"  # a darker step of the accent, one pixel down and right
CURSOR = t.SERIES[1]  # the terracotta of the second chart colour
STATIC = Path(__file__).resolve().parents[2] / "dashboard" / "static"


def _pixels(text: str) -> list[tuple[int, int, int]]:
    """(column, row, letter index) of every lit pixel; letters are ``GAP`` columns apart."""
    lit = []
    for index, letter in enumerate(text):
        left = index * (WIDTH + GAP)
        for row, line in enumerate(GLYPHS[letter]):
            lit += [(left + col, row, index) for col, on in enumerate(line) if on == "1"]
    return lit


def _path(cells: list[tuple[int, int]], dx: int = 0, dy: int = 0) -> str:
    return "".join(f"M{x + dx} {y + dy}h1v1h-1z" for x, y in cells)


def wordmark_svg(text: str = "DATAWARD", *, split: int = 4) -> str:
    """The name in pixels: the first ``split`` letters in the accent, the rest in the ink colour."""
    lit = _pixels(text)
    first = [(x, y) for x, y, i in lit if i < split]
    second = [(x, y) for x, y, i in lit if i >= split]
    columns = len(text) * (WIDTH + GAP) - GAP
    cursor_x = columns + 1
    width, height = cursor_x + CURSOR_WIDTH + 1, HEIGHT + 1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width * 4}" height="{height * 4}" shape-rendering="crispEdges" '
        'role="img" aria-label="Dataward">'
        f'<path fill="{SHADOW}" d="{_path(first + second, 1, 1)}"/>'
        f'<path fill="{t.ACCENT}" d="{_path(first)}"/>'
        f'<path fill="{t.INK}" d="{_path(second)}"/>'
        f'<rect x="{cursor_x}" y="{HEIGHT - 2}" width="{CURSOR_WIDTH}" height="2" fill="{CURSOR}">'
        '<animate attributeName="opacity" values="1;1;0;0" dur="1.1s" '
        'repeatCount="indefinite" calcMode="discrete"/></rect></svg>\n'
    )


def icon_svg() -> str:
    """The first letter and the cursor: the sidebar icon when the panel is collapsed."""
    lit = [(x, y) for x, y, _ in _pixels("D")]
    cursor_x = WIDTH + 1
    width, height = cursor_x + 2 + 1, HEIGHT + 1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width * 4}" height="{height * 4}" shape-rendering="crispEdges" '
        'role="img" aria-label="Dataward">'
        f'<path fill="{SHADOW}" d="{_path(lit, 1, 1)}"/>'
        f'<path fill="{t.ACCENT}" d="{_path(lit)}"/>'
        f'<rect x="{cursor_x}" y="{HEIGHT - 2}" width="2" height="2" fill="{CURSOR}"/></svg>\n'
    )


def favicon_png(size: int = 64) -> bytes:
    """A square tab icon: the pixel "D" and the cursor on the dashboard surface."""
    from PIL import Image, ImageDraw  # Pillow comes with Streamlit; only this function needs it

    cell = size // 10
    canvas = Image.new("RGB", (size, size), t.BG)
    draw = ImageDraw.Draw(canvas)
    left = (size - (WIDTH + 3) * cell) // 2
    top = (size - HEIGHT * cell) // 2
    for x, y, _ in _pixels("D"):
        draw.rectangle(
            [left + x * cell, top + y * cell, left + (x + 1) * cell - 1, top + (y + 1) * cell - 1],
            fill=t.ACCENT,
        )
    draw.rectangle(
        [left + (WIDTH + 1) * cell, top + (HEIGHT - 2) * cell,
         left + (WIDTH + 3) * cell - 1, top + HEIGHT * cell - 1],
        fill=CURSOR,
    )  # fmt: skip
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
