"""The frog: a pixel mascot that grows with the person and reacts to what they do.

Drawn from character grids (like the logo), so there is no image file to keep in step: a tadpole,
a froglet, a frog and a king of frogs, each in a mood (idle, happy, party, sleepy, sad, think). No
Streamlit import. The idle bob and the blink are CSS (see ``dashboard_theme``), stepped like the
rest of the interface and switched off for reduced motion.
"""

from html import escape

PALETTE = {
    "o": "#2C6E55",  # outline
    "g": "#7ED5B0",  # skin
    "l": "#CFF3E1",  # belly
    "w": "#F4F4F8",  # eye white
    "k": "#1B1B1D",  # pupil, mouth
    "r": "#E5603B",  # cheeks, hearts
    "y": "#E0B33A",  # crown, stars, question mark
    "b": "#8FB8FF",  # tear
    "z": "#AAA8FF",  # sleep
}
MOODS = ("idle", "happy", "party", "sleepy", "sad", "think")
STAGES = ("tadpole", "froglet", "frog", "king")
CELL = {"tadpole": 4, "froglet": 3, "frog": 4, "king": 4}
WIDTH, HEIGHT = 20, 18  # the canvas: room for a crown above and a mood sign beside

FROG = (  # 16 wide, 14 tall
    "..oooo....oooo..",
    ".owwwwo..owwwwo.",
    ".owkkwo..owkkwo.",
    ".ogggggoogggggo.",
    "oggggggggggggggo",
    "ogrrggggggggrrgo",
    "oggggggggggggggo",
    "ogllllllllllllgo",
    "ogllllllllllllgo",
    "oogllllllllllgoo",
    ".ooggggggggggoo.",
    "ogggo......ogggo",
    "oggggo....oggggo",
    "oooooo....oooooo",
)
TADPOLE = (  # 16 wide, 7 tall, facing left, the tail wiggling to the right
    "...oooooo.......",
    "..oggggggo......",
    ".ogwwgggggooo...",
    ".ogwkgggggggggoo",
    ".oggggggggggooo.",
    "..ogggggggo..oo.",
    "...oooooo...o...",
)
FROG_AT = (2, 4)  # column, row of the frog on the canvas
TADPOLE_AT = (2, 9)

# Small signs drawn beside or above the creature: (column, row, colour) on the canvas.
CROWN = [(8, 2, "y"), (11, 2, "y"), (8, 3, "y"), (9, 3, "y"), (10, 3, "y"), (11, 3, "y")]
HEART = [(16, 1, "r"), (18, 1, "r"), (16, 2, "r"), (17, 2, "r"), (18, 2, "r"), (17, 3, "r")]
SLEEP = [
    (16, 0, "z"),
    (17, 0, "z"),
    (18, 0, "z"),
    (18, 1, "z"),
    (17, 2, "z"),
    (16, 3, "z"),
    (16, 4, "z"),
    (17, 4, "z"),
    (18, 4, "z"),
]  # fmt: skip  (a Z)
QUESTION = [(17, 0, "y"), (16, 1, "y"), (18, 1, "y"), (18, 2, "y"), (17, 3, "y"), (17, 5, "y")]
STAR = [(1, 1, "y"), (0, 1, "y"), (2, 1, "y"), (1, 0, "y"), (1, 2, "y")]
STAR_RIGHT = [(x + 16, y, c) for x, y, c in STAR]
TEAR = [(6, 8, "b")]  # on the canvas, under the left eye


def _patch(grid: tuple[str, ...], changes: dict[tuple[int, int], str]) -> list[list[str]]:
    rows = [list(row) for row in grid]
    for (row, col), char in changes.items():
        rows[row][col] = char
    return rows


EYE_COLUMNS = ((2, 3, 4, 5), (10, 11, 12, 13))  # the inside of the left and the right eye


def _eye_rows(top: str, bottom: str) -> dict[tuple[int, int], str]:
    changes: dict[tuple[int, int], str] = {}
    for columns in EYE_COLUMNS:
        for row, pattern in ((1, top), (2, bottom)):
            changes.update({(row, col): char for col, char in zip(columns, pattern, strict=True)})
    return changes


def _eyes(kind: str) -> dict[tuple[int, int], str]:
    """Cells that turn the open eyes into something else (rows 1 and 2 of the frog)."""
    if kind == "closed":
        return _eye_rows("gggg", "oooo")
    if kind == "happy":  # arches: ^ ^
        return _eye_rows("goog", "oggo")
    return {}


def _mouth(kind: str) -> dict[tuple[int, int], str]:
    line = range(4, 12)
    if kind == "smile":
        return {(6, 3): "o", (6, 12): "o", **{(7, c): "o" for c in line}}
    if kind == "frown":
        return {(7, 3): "o", (7, 12): "o", **{(6, c): "o" for c in line}}
    if kind == "open":
        return {**{(6, c): "o" for c in line}, **{(7, c): "k" for c in range(5, 11)},
                **{(7, c): "r" for c in (7, 8)}}  # fmt: skip
    return {(6, c): "o" for c in line}


def _cells(stage: str, mood: str) -> list[tuple[int, int, str]]:
    """Every coloured cell of the mascot on the canvas, signs included."""
    cells: list[tuple[int, int, str]] = []
    if stage == "tadpole":
        grid = _patch(TADPOLE, {})
        if mood in {"sleepy", "happy"}:
            grid = _patch(TADPOLE, {(2, 3): "g", (2, 4): "g", (3, 3): "o", (3, 4): "o"})
        origin = TADPOLE_AT
    else:
        eyes = {"sleepy": "closed", "happy": "happy", "party": "happy"}.get(mood, "open")
        mouth = {"happy": "smile", "party": "open", "sad": "frown", "sleepy": "flat"}.get(
            mood, "flat"
        )
        changes = {**_eyes(eyes), **_mouth(mouth)}
        grid = _patch(FROG, changes)
        origin = FROG_AT
    for row, line in enumerate(grid):
        for col, char in enumerate(line):
            if char != ".":
                cells.append((origin[0] + col, origin[1] + row, char))
    signs = {"happy": HEART, "party": STAR + STAR_RIGHT, "sleepy": SLEEP, "think": QUESTION}.get(
        mood, []
    )
    if mood == "sad" and stage != "tadpole":
        signs = TEAR
    if stage == "king":
        signs = signs + CROWN
    return cells + [(x, y, c) for x, y, c in signs]


def _blink_cells(stage: str) -> list[tuple[int, int, str]]:
    """The closed-eye cells drawn over open eyes now and then."""
    if stage == "tadpole":
        eyes = ((2, 3, "g"), (2, 4, "g"), (3, 3, "o"), (3, 4, "o"))
        return [(TADPOLE_AT[0] + c, TADPOLE_AT[1] + r, ch) for r, c, ch in eyes]
    return [(FROG_AT[0] + c, FROG_AT[1] + r, ch) for (r, c), ch in _eyes("closed").items()]


def _paths(cells: list[tuple[int, int, str]]) -> str:
    by_colour: dict[str, list[str]] = {}
    for x, y, char in cells:
        by_colour.setdefault(char, []).append(f"M{x} {y}h1v1h-1z")
    return "".join(
        f'<path fill="{PALETTE[char]}" d="{"".join(parts)}"/>' for char, parts in by_colour.items()
    )


def frog_svg(
    stage: str = "frog", mood: str = "idle", *, label: str = "Жабка", scale: float = 1.0
) -> str:
    """The mascot as inline SVG. The blink layer is hidden by default; CSS flashes it."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage!r}")
    if mood not in MOODS:
        raise ValueError(f"unknown mood: {mood!r}")
    cell = CELL[stage]
    lids = ""
    if mood in {"idle", "think", "sad"}:
        lids = f'<g class="dw-lid" opacity="0">{_paths(_blink_cells(stage))}</g>'
    return (
        f'<svg class="dw-frog dw-frog-{mood}" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" width="{round(WIDTH * cell * scale)}" '
        f'height="{round(HEIGHT * cell * scale)}" '
        f'shape-rendering="crispEdges" role="img" aria-label="{escape(label)}">'
        f"{_paths(_cells(stage, mood))}{lids}</svg>"
    )
