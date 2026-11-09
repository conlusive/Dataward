"""The dashboard's look: colour tokens, one stylesheet and small HTML pieces.

No Streamlit import here, so the pieces are tested directly. The surface and the accent are the
"smoky lilac" pair (#303032, #AAA8FF). The two chart colours were checked with the dataviz palette
validator on that surface (dark lightness band, colour-blind separation, contrast); the accent
itself is lighter than the chart band allows for large fills, so it is used for text, lines and
highlights, and the charts use the slightly deeper ``SERIES`` colours.
"""

from html import escape

BG = "#303032"
CARD = "#28282A"
LINE = "#414145"
GRID = "#3B3B3F"
INK = "#ECECF1"
INK_2 = "#B9B9C4"
INK_3 = "#9A9AA6"  # muted text: 4.8:1 on the surface
ACCENT = "#AAA8FF"

# Chart colours, in a fixed order (an entity keeps its colour whatever the filter shows).
SERIES = ("#8481F5", "#E5603B")
SOURCE_ORDER = ("dou", "djinni")  # the sources always wear the first two colours in this order
MARK = SERIES[0]  # one-series bars and lines
MUTED_MARK = "#7A7A82"  # context marks next to an emphasised one (3:1 on the card)

FONT_BODY = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
FONT_DISPLAY = "'Martian Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

# State is never colour alone: every tone carries an icon and a word.
TONES = {
    "ok": ("✓", "var(--ok)"),
    "warn": ("▲", "var(--warn)"),
    "bad": ("✕", "var(--bad)"),
    "neutral": ("●", "var(--ink-3)"),
}

_STYLE = """
.stApp { background: var(--bg); font-family: var(--body); }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1380px; }
h1, h2, h3, h4 { font-family: var(--display) !important; letter-spacing: -0.01em; }

/* sidebar */
[data-testid="stSidebar"] { background: var(--card); border-right: 1px solid var(--line); }
[data-testid="stSidebarNavLink"] { border-radius: 10px; font-size: 0.85rem; }
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: rgba(170, 168, 255, 0.14); color: var(--accent);
}
[data-testid="stSidebarNavSeparator"], [data-testid="stSidebarNav"] span[class*="Header"] {
  font-family: var(--display); font-size: 0.65rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--ink-3);
}

/* the page header */
.dw-hero { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 1.5rem; flex-wrap: wrap; margin: 0 0 1.4rem; }
.dw-eyebrow { font-family: var(--display); font-size: 0.68rem; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.55rem; }
.dw-title { font-family: var(--display); font-weight: 500; font-size: 2.1rem; line-height: 1.15;
  letter-spacing: -0.02em; color: var(--ink); margin: 0; }
.dw-sub { color: var(--ink-3); font-size: 0.9rem; margin-top: 0.55rem; max-width: 46rem; }
.dw-pills { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.dw-pill { display: inline-flex; align-items: center; gap: 0.5rem; background: var(--card);
  border: 1px solid var(--line); border-radius: 999px; padding: 0.3rem 0.8rem;
  font-size: 0.72rem; color: var(--ink-2); white-space: nowrap; }
.dw-pill i { font-style: normal; }

/* section labels: "01  DYNAMICS" */
.dw-section { font-family: var(--display); font-size: 0.7rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--ink-3); margin: 1.8rem 0 0.7rem; }
.dw-section b { color: var(--accent); font-weight: 500; margin-right: 0.7rem; }

/* cards: metrics and bordered containers */
[data-testid="stMetric"] { background: var(--card); border: 1px solid var(--line);
  border-radius: 16px; padding: 1rem 1.15rem; min-height: 7.4rem; }
[data-testid="stMetricLabel"] * { font-family: var(--display); font-size: 0.66rem !important;
  letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); }
[data-testid="stMetricValue"] { font-family: var(--display); letter-spacing: -0.02em; }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
  border-radius: 16px;
}
.dw-card-title { font-family: var(--display); font-size: 0.72rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-2); margin: 0 0 0.2rem; }
.dw-card-note { color: var(--ink-3); font-size: 0.78rem; margin: 0 0 0.6rem; }

/* tabs */
[data-baseweb="tab-list"] { gap: 0.4rem; border-bottom: 1px solid var(--line); }
button[data-baseweb="tab"] { font-family: var(--display); font-size: 0.72rem;
  letter-spacing: 0.08em; text-transform: uppercase; padding: 0.7rem 0.9rem; }
[data-baseweb="tab-highlight"] { background-color: var(--accent) !important; height: 2px; }
[data-baseweb="tab-border"] { display: none; }

/* tables, inputs, links */
[data-testid="stDataFrame"] {
  border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
}
[data-testid="stCaptionContainer"] { color: var(--ink-3); }
[data-testid="stPageLink"] a { padding: 0.2rem 0; background: transparent; }
[data-testid="stPageLink"] a:hover { color: var(--accent); }

/* a small screen: one column, a smaller title */
@media (max-width: 720px) {
  .dw-title { font-size: 1.5rem; }
  .block-container { padding-left: 1rem; padding-right: 1rem; }
}
"""


def css() -> str:
    """The stylesheet, ready for a <style> tag."""
    variables = (
        f":root {{ --bg: {BG}; --card: {CARD}; --line: {LINE}; --ink: {INK}; --ink-2: {INK_2};"
        f" --ink-3: {INK_3}; --accent: {ACCENT}; --ok: #7ED5B0; --warn: #F2A56D; --bad: #FF7A6B;"
        f" --body: {FONT_BODY}; --display: {FONT_DISPLAY}; }}"
    )
    return f"<style>{variables}{_STYLE}</style>"


def pill(text: str, tone: str = "neutral") -> str:
    """A small status chip: an icon and a word, so the state never depends on colour alone."""
    icon, color = TONES.get(tone, TONES["neutral"])
    return f'<span class="dw-pill"><i style="color:{color}">{icon}</i>{escape(text)}</span>'


def hero(eyebrow: str, title: str, subtitle: str = "", pills: list[str] | None = None) -> str:
    """The header of a page; ``pills`` are already-built chips (see ``pill``)."""
    sub = f'<div class="dw-sub">{escape(subtitle)}</div>' if subtitle else ""
    chips = f'<div class="dw-pills">{"".join(pills)}</div>' if pills else ""
    return (
        '<div class="dw-hero"><div>'
        f'<div class="dw-eyebrow">{escape(eyebrow)}</div>'
        f'<h1 class="dw-title">{escape(title)}</h1>{sub}</div>{chips}</div>'
    )


def section(label: str, number: int | None = None) -> str:
    """A small uppercase label above a block, numbered like the cards of a control panel."""
    mark = f"<b>{number:02d}</b>" if number is not None else ""
    return f'<div class="dw-section">{mark}{escape(label)}</div>'


def card_title(title: str, note: str = "") -> str:
    extra = f'<div class="dw-card-note">{escape(note)}</div>' if note else ""
    return f'<div class="dw-card-title">{escape(title)}</div>{extra}'
