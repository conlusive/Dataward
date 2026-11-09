"""The dashboard's look: colour tokens, one stylesheet and small HTML pieces.

No Streamlit import here, so the pieces are tested directly. The surface and the accent are the
"smoky lilac" pair (#303032, #AAA8FF). The style is pixel and terminal: Tiny5 for headings
and figures, JetBrains Mono for text, stepped corners and a prompt before each title. The two chart
colours were checked with the dataviz palette validator on that surface (dark lightness band,
colour-blind separation, contrast); the accent itself is lighter than the chart band allows for
large fills, so it is used for text, lines and highlights, and the charts use the slightly deeper
``SERIES`` colours.
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
FONT_DISPLAY = "'Tiny5', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

# State is never colour alone: every tone carries an icon and a word.
TONES = {
    "ok": ("✓", "var(--ok)"),
    "warn": ("▲", "var(--warn)"),
    "bad": ("✕", "var(--bad)"),
    "neutral": ("●", "var(--ink-3)"),
}

_STYLE = """
.stApp { background-color: var(--bg); font-family: var(--body);
  background-image: radial-gradient(circle, #39393D 1px, transparent 1px);
  background-size: 22px 22px; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1400px; }
h1, h2, h3, h4 { font-family: var(--display) !important; }

/* stepped (pixel) corners: the clip removes the four corner squares of the border */
[data-testid="stMetric"], .dw-pill, .dw-card-box, .dw-facts-box,
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
  border-radius: 0 !important;
  clip-path: polygon(0 4px, 4px 4px, 4px 0, calc(100% - 4px) 0, calc(100% - 4px) 4px,
    100% 4px, 100% calc(100% - 4px), calc(100% - 4px) calc(100% - 4px),
    calc(100% - 4px) 100%, 4px 100%, 4px calc(100% - 4px), 0 calc(100% - 4px));
}

/* sidebar */
[data-testid="stSidebar"] { background: var(--card); border-right: 2px solid var(--line); }
[data-testid="stSidebarNavLink"] { border-radius: 0; font-size: 0.85rem;
  border-left: 4px solid transparent; }
[data-testid="stSidebarNavLink"]:hover { border-left-color: var(--line); }
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: rgba(170, 168, 255, 0.12); color: var(--accent); border-left-color: var(--accent);
}
[data-testid="stSidebarNavSeparator"], [data-testid="stSidebarNav"] span[class*="Header"] {
  font-family: var(--display); font-size: 0.95rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-3);
}
[data-testid="stSidebarHeader"] { padding-bottom: 0.4rem; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 0.5rem; }
.dw-side-label { font-family: var(--display); font-size: 0.95rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-3); margin: 1.1rem 0 0.35rem;
  border-top: 2px solid var(--line); padding-top: 0.7rem; }
.dw-side-label::before { content: "// "; color: var(--accent); font-family: var(--body); }

/* the page header: a prompt, the title and a blinking cursor */
.dw-hero { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 1.5rem; flex-wrap: wrap; margin: 0 0 1.4rem; }
.dw-eyebrow { font-size: 0.74rem; letter-spacing: 0.06em; color: var(--accent);
  margin-bottom: 0.6rem; }
.dw-eyebrow::before { content: "$ "; color: var(--ink-3); }
.dw-title { font-family: var(--display); font-weight: 400; font-size: 3rem; line-height: 1.1;
  letter-spacing: 0.02em; color: var(--ink); margin: 0; }
.dw-title::after { content: "_"; color: var(--cursor); margin-left: 0.12em;
  animation: dw-blink 1.1s steps(1) infinite; }
@keyframes dw-blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .dw-title::after { animation: none; } }
.dw-sub { color: var(--ink-3); font-size: 0.88rem; margin-top: 0.6rem; max-width: 48rem; }
.dw-pills { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.dw-pill { display: inline-flex; align-items: center; gap: 0.5rem; background: var(--card);
  border: 2px solid var(--line); padding: 0.28rem 0.8rem; font-size: 0.72rem;
  color: var(--ink-2); white-space: nowrap; }
.dw-pill i { font-style: normal; }

/* section labels: "// 01 DYNAMICS" */
.dw-section { font-family: var(--display); font-size: 1rem; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--ink-3); margin: 1.8rem 0 0.7rem; }
.dw-section::before { content: "// "; color: var(--accent); font-family: var(--body); }
.dw-section b { color: var(--accent); font-weight: 500; margin-right: 0.7rem; }

/* cards: metrics and bordered containers */
[data-testid="stMetric"] { background: var(--card); border: 2px solid var(--line);
  padding: 1rem 1.15rem; min-height: 7.4rem; }
[data-testid="stMetricLabel"] * { font-family: var(--display); font-size: 0.95rem !important;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3); }
[data-testid="stMetricValue"] { font-family: var(--display); font-weight: 400;
  font-size: 2.6rem; }
.dw-card-title { font-family: var(--display); font-size: 1rem; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-2); margin: 0 0 0.2rem; }
.dw-card-title::before { content: "▪ "; color: var(--accent); }
.dw-card-note { color: var(--ink-3); font-size: 0.78rem; margin: 0 0 0.6rem; }

/* tabs: the open one gets a prompt arrow */
[data-baseweb="tab-list"] { gap: 0.3rem; border-bottom: 2px solid var(--line); }
button[data-baseweb="tab"] { font-family: var(--display); font-size: 1rem;
  letter-spacing: 0.06em; text-transform: uppercase; padding: 0.7rem 0.9rem; }
button[data-baseweb="tab"][aria-selected="true"]::before { content: "▸ "; color: var(--accent); }
[data-baseweb="tab-highlight"] { background-color: var(--accent) !important; height: 4px; }
[data-baseweb="tab-border"] { display: none; }

/* inputs and buttons: square */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="base-input"],
button[kind], [data-testid="stDownloadButton"] button, [data-testid="stLinkButton"] a {
  border-radius: 0 !important;
}
[data-testid="stDataFrame"] { border: 2px solid var(--line); overflow: hidden; }
[data-testid="stCaptionContainer"] { color: var(--ink-3); }
[data-testid="stPageLink"] a { padding: 0.2rem 0; background: transparent; border-radius: 0; }
[data-testid="stPageLink"] a:hover { color: var(--accent); }
[data-testid="stAlert"] { border-radius: 0; border-left: 4px solid var(--accent); }

/* skill tags and fact lists (the vacancy card) */
.dw-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.3rem 0 0.8rem; }
.dw-chip { border: 2px solid var(--line); padding: 0.12rem 0.55rem; font-size: 0.76rem;
  color: var(--ink-2); }
.dw-chip.req { border-color: var(--accent); color: var(--accent);
  background: rgba(170, 168, 255, 0.1); }
.dw-chip.req::before { content: "■ "; font-size: 0.6rem; vertical-align: 0.1em; }
.dw-facts { display: grid; grid-template-columns: max-content 1fr; gap: 0.35rem 1.2rem;
  margin: 0.4rem 0 0.9rem; font-size: 0.84rem; }
.dw-facts dt { color: var(--ink-3); }
.dw-facts dd { margin: 0; color: var(--ink); }
.dw-lead { font-family: var(--display); font-size: 1.9rem; line-height: 1.2; color: var(--ink);
  margin: 0.1rem 0 0.2rem; }
.dw-muted { color: var(--ink-3); font-size: 0.84rem; }

/* a small screen: one column, a smaller title */
@media (max-width: 720px) {
  .dw-title { font-size: 2rem; }
  .block-container { padding-left: 1rem; padding-right: 1rem; }
}
"""


def css() -> str:
    """The stylesheet, ready for a <style> tag."""
    variables = (
        f":root {{ --bg: {BG}; --card: {CARD}; --line: {LINE}; --ink: {INK}; --ink-2: {INK_2};"
        f" --ink-3: {INK_3}; --accent: {ACCENT}; --cursor: {SERIES[1]}; --ok: #7ED5B0;"
        f" --warn: #F2A56D; --bad: #FF7A6B;"
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


def side_label(text: str) -> str:
    """A small heading inside the sidebar, above a group of filters."""
    return f'<div class="dw-side-label">{escape(text)}</div>'


def chips(items: list[str], required: list[str] | None = None) -> str:
    """Skill tags; the required ones are filled and marked with a square, the rest are outlined."""
    must = set(required or [])
    tags = "".join(
        f'<span class="dw-chip{" req" if item in must else ""}">{escape(item)}</span>'
        for item in items
    )
    return f'<div class="dw-chips">{tags}</div>' if tags else ""


def facts(rows: list[tuple[str, str]]) -> str:
    """A two-column list of label and value; rows whose value is empty are left out."""
    body = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in rows if value
    )
    return f'<dl class="dw-facts">{body}</dl>' if body else ""
