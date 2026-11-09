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

# Chart colours, in a fixed order (an entity keeps its colour whatever the filter shows). All four
# passed the palette validator on the card surface; a chart never needs a fifth (the tail is folded
# into "Інші").
SERIES = ("#8481F5", "#E5603B", "#26A08F", "#B58A1F")
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

_MOTION = """
/* motion: things arrive in steps (pixel style), never glide; all of it stops for reduced motion */
@keyframes dw-rise { from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; } }
@keyframes dw-wipe { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
@keyframes dw-type { from { width: 0; } to { width: var(--chars); } }
@keyframes dw-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
[data-testid="stMetric"], .dw-stat, .dw-dir, .dw-vac, .dw-hero {
  animation: dw-rise 0.4s steps(5) both; animation-delay: calc(var(--i, 0) * 50ms);
}
[data-testid="stVegaLiteChart"] { animation: dw-wipe 1.1s steps(28) both; }
.dw-typed { display: inline-block; overflow: hidden; white-space: nowrap;
  border-right: 2px solid var(--accent); width: var(--chars);
  animation: dw-type 1.6s steps(var(--steps)) both, dw-caret 0.9s steps(1) 1.6s 3; }
@keyframes dw-caret { 50% { border-right-color: transparent; } }
.dw-pulse span:last-child { animation: dw-pulse 1.6s steps(2) infinite; }
.dw-dir, .dw-vac, [data-testid="stMetric"] { transition: transform 0.12s steps(2),
  border-color 0.12s steps(2); }
.dw-dir:hover, .dw-vac:hover, [data-testid="stMetric"]:hover {
  transform: translate(-2px, -2px); border-color: var(--accent); }
@keyframes dw-bob { 0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); } }
@keyframes dw-blink-lid { 0%, 91% { opacity: 0; } 92%, 96% { opacity: 1; }
  97%, 100% { opacity: 0; } }
.dw-frog { animation: dw-bob 1.8s steps(2) infinite; image-rendering: pixelated; }
.dw-frog-sleepy { animation-duration: 2.8s; }
.dw-frog-party { animation-duration: 0.6s; }
.dw-lid { animation: dw-blink-lid 4.2s steps(1) infinite; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
  .dw-typed { width: auto; border-right: 0; }
}
"""

_BLOCKS = """
/* bracket statistics: [ ВІДКРИТО: 6 710 ] */
.dw-stats { display: flex; flex-wrap: wrap; gap: 0.5rem 1.6rem; margin: 0.2rem 0 1rem; }
.dw-stat { display: inline-flex; align-items: baseline; gap: 0.55rem; font-size: 0.82rem;
  color: var(--ink-3); letter-spacing: 0.04em; text-transform: uppercase; }
.dw-stat i { font-style: normal; color: var(--accent); font-size: 1.5rem; line-height: 1; }
.dw-stat b { font-family: var(--display); font-weight: 400; color: var(--ink); font-size: 1.9rem;
  letter-spacing: 0.02em; }
.dw-stat em { font-style: normal; }

/* the frog card in the sidebar and the profile */
.dw-pet { display: flex; gap: 0.8rem; align-items: center; padding: 0.6rem 0.4rem 0.2rem; }
.dw-pet-text { min-width: 0; flex: 1; font-size: 0.78rem; color: var(--ink-3); line-height: 1.5; }
.dw-pet-name { font-family: var(--display); font-size: 1.05rem; color: var(--ink); }
.dw-pet-name b { color: var(--accent); font-weight: 400; }
.dw-xp { height: 8px; background: var(--line); margin: 0.35rem 0 0.25rem; }
.dw-xp span { display: block; height: 100%; background: var(--accent); }
.dw-medal { display: inline-block; border: 2px solid var(--line); color: var(--ink-3);
  padding: 0.15rem 0.55rem; margin: 0 0.4rem 0.4rem 0; font-size: 0.78rem; }
.dw-medal.on { border-color: var(--accent); color: var(--accent);
  background: rgba(170, 168, 255, 0.1); }
.dw-medal.on::before { content: "★ "; }
.dw-resource { font-size: 0.85rem; }

/* the sidebar is part of the layout, not a drawer: it cannot be collapsed */
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"], button[kind="headerNoPadding"] { display: none !important; }

/* a rerun must not dim the page: the old content stays, then is replaced in place */
[data-stale="true"] { opacity: 1 !important; transition: none !important; }
[data-testid="stAppViewContainer"] [data-stale="true"] * { transition: none !important; }

/* the last pipeline runs as squares, the newest pulsing */
.dw-pulse { display: inline-flex; gap: 4px; vertical-align: middle; }
.dw-pulse span { width: 12px; height: 12px; background: var(--line); }
.dw-pulse .ok { background: var(--ok); }
.dw-pulse .warn { background: var(--warn); }
.dw-pulse .bad { background: var(--bad); }

/* a legend of bracketed entries: [ ■ dou ] */
.dw-legend { display: flex; flex-wrap: wrap; gap: 0.4rem 1.4rem; margin: 0.2rem 0 0.6rem;
  font-size: 0.8rem; color: var(--ink-2); }
.dw-leg i { font-style: normal; color: var(--accent); }
.dw-leg b { display: inline-block; width: 0.7rem; height: 0.7rem; margin: 0 0.45rem 0 0.4rem; }

/* tiles: a direction, a vacancy */
.dw-dir, .dw-vac { background: var(--card); border: 2px solid var(--line); padding: 0.9rem 1rem;
  margin-bottom: 0.4rem; box-sizing: border-box;
  clip-path: polygon(0 4px, 4px 4px, 4px 0, calc(100% - 4px) 0,
  calc(100% - 4px) 4px, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) calc(100% - 4px),
  calc(100% - 4px) 100%, 4px 100%, 4px calc(100% - 4px), 0 calc(100% - 4px)); }
.dw-dir-name { font-family: var(--display); font-size: 1.15rem; color: var(--ink);
  letter-spacing: 0.04em; text-transform: uppercase; }
.dw-dir-count { font-family: var(--display); font-size: 2.2rem; color: var(--accent);
  line-height: 1.1; margin: 0.2rem 0; }
.dw-dir-count small { font-size: 0.8rem; color: var(--ink-3); margin-left: 0.4rem; }
.dw-meter { height: 8px; background: var(--line); margin: 0.4rem 0 0.7rem; }
.dw-meter span { display: block; height: 100%; background: var(--accent);
  animation: dw-grow 0.9s steps(16) both; }
@keyframes dw-grow { from { width: 0; } }
.dw-dir { height: 14.5rem; overflow: hidden; }
.dw-vac { height: 12.5rem; overflow: hidden; }
.dw-vac-title { font-family: var(--display); font-size: 1.15rem; color: var(--ink);
  line-height: 1.2; }
.dw-vac-meta { color: var(--ink-3); font-size: 0.8rem; margin: 0.3rem 0 0.5rem; }
.dw-vac-pay { color: var(--accent); font-size: 0.9rem; }

/* filters: an active one must look different from an idle one */
[data-baseweb="select"]:not(:has([data-baseweb="tag"])) > div { border-style: dashed !important; }
[data-baseweb="select"]:has([data-baseweb="tag"]) > div { border-color: var(--accent) !important;
  background: rgba(170, 168, 255, 0.08) !important; }
[data-baseweb="tag"] { background: var(--accent) !important; color: #1B1B1D !important;
  border-radius: 0 !important; }
[data-baseweb="tag"] span { color: #1B1B1D !important; }
button[kind="pillsActive"] { background: var(--accent) !important; color: #1B1B1D !important;
  border-color: var(--accent) !important; }
button[kind="pills"], button[kind="pillsActive"],
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"] {
  border-radius: 0 !important; border-width: 2px !important; }
[data-testid="stBaseButton-pillsActive"] { background: var(--accent) !important;
  color: #1B1B1D !important; border-color: var(--accent) !important; }
[data-testid="stBaseButton-pillsActive"] * { color: #1B1B1D !important; }
.dw-active { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;
  margin: 0.4rem 0 1rem; font-size: 0.78rem; }
.dw-active .dw-tag { border: 2px solid var(--accent); color: var(--accent);
  padding: 0.1rem 0.6rem; background: rgba(170, 168, 255, 0.08); }
.dw-active .dw-none { color: var(--ink-3); }
.dw-answer { border-left: 4px solid var(--accent); background: var(--card); padding: 0.8rem 1rem;
  margin: 0.6rem 0; color: var(--ink); font-size: 0.95rem; line-height: 1.55; }
.dw-q-meta { color: var(--ink-3); font-size: 0.8rem; margin-bottom: 0.3rem; }
.dw-fl { font-family: var(--display); font-size: 0.95rem; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-2); margin-bottom: 0.3rem; }
.dw-badge { display: inline-block; min-width: 1.3rem; padding: 0 0.35rem; margin-left: 0.5rem;
  background: var(--accent); color: #1B1B1D; text-align: center; font-size: 0.78rem; }
"""


def css() -> str:
    """The stylesheet, ready for a <style> tag."""
    variables = (
        f":root {{ --bg: {BG}; --card: {CARD}; --line: {LINE}; --ink: {INK}; --ink-2: {INK_2};"
        f" --ink-3: {INK_3}; --accent: {ACCENT}; --cursor: {SERIES[1]}; --ok: #7ED5B0;"
        f" --warn: #F2A56D; --bad: #FF7A6B;"
        f" --body: {FONT_BODY}; --display: {FONT_DISPLAY}; }}"
    )
    return f"<style>{variables}{_STYLE}{_MOTION}{_BLOCKS}</style>"


def pill(text: str, tone: str = "neutral") -> str:
    """A small status chip: an icon and a word, so the state never depends on colour alone."""
    icon, color = TONES.get(tone, TONES["neutral"])
    return f'<span class="dw-pill"><i style="color:{color}">{icon}</i>{escape(text)}</span>'


def hero(
    eyebrow: str,
    title: str,
    subtitle: str = "",
    pills: list[str] | None = None,
    *,
    typed_subtitle: bool = False,
) -> str:
    """The header of a page; ``pills`` are already-built chips (see ``pill``).

    With ``typed_subtitle`` the line under the title types itself out.
    """
    line = typed(subtitle) if typed_subtitle and subtitle else escape(subtitle)
    sub = f'<div class="dw-sub">{line}</div>' if subtitle else ""
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


def stats(items: list[tuple[str, str]]) -> str:
    """Bracketed figures in a row: ``[ ВІДКРИТО: 6 710 ]``; they arrive one after another."""
    parts = "".join(
        f'<span class="dw-stat" style="--i:{n}"><i>[</i><em>{escape(label)}:</em>'
        f"<b>{escape(value)}</b><i>]</i></span>"
        for n, (label, value) in enumerate(items)
    )
    return f'<div class="dw-stats">{parts}</div>'


def pulse(states: list[tuple[str, str]]) -> str:
    """Squares for the last runs, oldest first: (what it was, a tone). The newest one pulses."""
    squares = "".join(
        f'<span class="{tone if tone in TONES else "neutral"}" title="{escape(label)}"></span>'
        for label, tone in states
    )
    return f'<div class="dw-pulse" role="img" aria-label="останні запуски">{squares}</div>'


def legend(names: list[str], colours: list[str]) -> str:
    """The key of a multi-series chart: ``[ ■ dou ]``, in the order of the stack."""
    items = "".join(
        f'<span class="dw-leg"><i>[</i><b style="background:{colour}"></b>{escape(name)}'
        "<i>]</i></span>"
        for name, colour in zip(names, colours, strict=False)
    )
    return f'<div class="dw-legend">{items}</div>'


def typed(text: str) -> str:
    """A line that types itself out; the text is there from the start for readers and tests."""
    return (
        f'<span class="dw-typed" style="--chars:{len(text)}ch;--steps:{len(text)}">'
        f"{escape(text)}</span>"
    )


def direction_tile(index: int, name: str, open_count: str, share: float, skills: list[str]) -> str:
    """A direction of the market: its name, open vacancies, a meter of its share, top skills."""
    width = max(2, min(100, round(share * 100)))
    return (
        f'<div class="dw-dir" style="--i:{index}"><div class="dw-dir-name">{escape(name)}</div>'
        f'<div class="dw-dir-count">{escape(open_count)}<small>відкритих</small></div>'
        f'<div class="dw-meter" role="img" aria-label="{width}% ринку">'
        f'<span style="width:{width}%"></span></div>{chips(skills)}</div>'
    )


def vacancy_tile(index: int, title: str, company: str, pay: str, skills: list[str]) -> str:
    """A vacancy as a tile: title, company, salary and a few skills."""
    meta = escape(company) if company else "компанія не вказана"
    salary = f'<div class="dw-vac-pay">{escape(pay)}</div>' if pay else ""
    return (
        f'<div class="dw-vac" style="--i:{index}"><div class="dw-vac-title">{escape(title)}</div>'
        f'<div class="dw-vac-meta">{meta}</div>{salary}{chips(skills)}</div>'
    )


def active_filters(items: list[tuple[str, str]]) -> str:
    """What is filtered now, as tags: ``Джерело: dou``; a quiet note when nothing is."""
    if not items:
        none = "фільтри не задано: показано все"
        return f'<div class="dw-active"><span class="dw-none">{none}</span></div>'
    tags = "".join(
        f'<span class="dw-tag">{escape(name)}: {escape(value)}</span>' for name, value in items
    )
    return f'<div class="dw-active">{tags}</div>'


def count_badge(count: int) -> str:
    """A small filled square with a number, for a heading with active filters."""
    return f'<span class="dw-badge">{count}</span>' if count else ""


def pet(svg: str, name: str, level: int, ratio: float, xp: str, notes: list[str]) -> str:
    """The frog with its stage, level, an experience bar and a few short notes beside it.

    ``svg`` is the mascot's inline SVG (see ``dashboard_mascot``); the text is escaped.
    """
    width = max(2, min(100, round(ratio * 100)))
    lines = "".join(f"<div>{escape(note)}</div>" for note in notes)
    return (
        f'<div class="dw-pet">{svg}<div class="dw-pet-text">'
        f'<div class="dw-pet-name">{escape(name)} · <b>рівень {level}</b></div>'
        f'<div class="dw-xp" role="img" aria-label="{width}% до наступного рівня">'
        f'<span style="width:{width}%"></span></div>'
        f"<div>{escape(xp)}</div>{lines}</div></div>"
    )


def medals(items: list[tuple[str, str, bool]]) -> str:
    """Achievements as small tags: (title, how to earn it, earned); the earned ones are lit."""
    parts = "".join(
        f'<span class="dw-medal{" on" if earned else ""}" title="{escape(hint)}">'
        f"{escape(title)}</span>"
        for title, hint, earned in items
    )
    return f'<div class="dw-medals">{parts}</div>'


def pet_free(svg: str) -> str:
    """The frog on its own (no text), centred in its column."""
    return f'<div class="dw-pet" style="justify-content:center">{svg}</div>'
