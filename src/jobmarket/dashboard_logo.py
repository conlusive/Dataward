"""The pixel logo: three rising bars, DATAWARD in a 5x7 pixel font, and a full stop.

Everything is drawn from the tables below, so the logo, the sidebar icon and the favicon are
generated, not hand-edited. ``python -m jobmarket.dashboard_logo`` rewrites the files in
``dashboard/static``; a test keeps the committed copies equal to what this module produces.
The stop is static on purpose (the blinking cursor lives in the page titles only).
"""

import io
from html import escape
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
SHADOW = "#2F2A55"  # a pale step of the accent, one pixel down and right
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


APPLE_TOUCH_SIZE = 180  # what Safari asks for (start page, favourites, home screen)


FAVICON_SIZE = 192  # a multiple of 48 px, as search engines ask for a site icon
ICO_SIZES = ((16, 16), (32, 32), (48, 48))


def favicon_png(size: int = FAVICON_SIZE, *, round_badge: bool = True) -> bytes:
    """The site icon: three rising bars and a dot, light on a violet disc (a round badge).

    The corners of a round badge are transparent, so a tab or a search result shows a circle; the
    icon of a home screen (``round_badge=False``) is a full square, which the system rounds itself.
    Drawn four times larger and scaled down, so the edges are smooth.
    """
    from PIL import Image, ImageDraw  # Pillow comes with Streamlit; only these functions need it

    big = size * 4
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    disc = [0, 0, big - 1, big - 1]
    if round_badge:
        draw.ellipse(disc, fill=t.VIOLET)
    else:
        draw.rectangle(disc, fill=t.VIOLET)
    unit = big * 0.075  # the height of the shortest step of the bars
    wide, gap = big * 0.11, big * 0.06
    left = (big - (4 * wide + 3 * gap)) / 2
    base = (big + max(BARS) * unit) / 2
    for i, height in enumerate(BARS):
        x = left + i * (wide + gap)
        draw.rounded_rectangle(
            [x, base - height * unit, x + wide, base], radius=wide / 2, fill=t.INK
        )
    x = left + 3 * (wide + gap)
    draw.ellipse([x, base - wide, x + wide, base], fill=DOT_COLOUR)
    buffer = io.BytesIO()
    canvas.resize((size, size), Image.Resampling.LANCZOS).save(buffer, format="PNG")
    return buffer.getvalue()


def favicon_ico() -> bytes:
    """``favicon.ico`` (16, 32 and 48 px) for the browsers that ask for that name by default."""
    from PIL import Image

    image = Image.open(io.BytesIO(favicon_png())).convert("RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="ICO", sizes=list(ICO_SIZES))
    return buffer.getvalue()


def calm_wordmark_svg(text: str = "Dataward") -> str:
    """The wordmark of the light look: three rounded bars and the name in the grotesque.

    The name is real text (an image cannot load a web font, so it falls back to the system sans),
    the bars repeat the emblem of the pixel mark: the same rising heights, the last one a dot of
    the second chart colour.
    """
    bars = "".join(
        f'<rect x="{i * 9}" y="{30 - h * 3.4:.1f}" width="6" height="{h * 3.4:.1f}" rx="3" '
        f'fill="{t.ACCENT}"/>'
        for i, h in enumerate(BARS)
    )
    dot = f'<circle cx="{len(BARS) * 9 + 3}" cy="27" r="3" fill="{DOT_COLOUR}"/>'
    name = (
        f'<text x="{len(BARS) * 9 + 14}" y="29" fill="{t.INK}" font-size="25" '
        'font-weight="800" letter-spacing="-0.8" '
        f"font-family=\"Inter, 'Helvetica Neue', Arial, sans-serif\">{escape(text)}</text>"
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 190 36" role="img" '
        f'aria-label="{escape(text)}">{bars}{dot}{name}</svg>'
    )


def write_assets(directory: Path = STATIC) -> list[Path]:
    """Write the wordmark, the pixel marks, ``favicon.png``, ``favicon.ico``, the touch icon."""
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "wordmark.svg": calm_wordmark_svg().encode("utf-8"),
        "logo.svg": wordmark_svg().encode("utf-8"),
        "icon.svg": icon_svg().encode("utf-8"),
        "favicon.png": favicon_png(),
        "favicon.ico": favicon_ico(),
        "apple-touch-icon.png": favicon_png(APPLE_TOUCH_SIZE, round_badge=False),
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
