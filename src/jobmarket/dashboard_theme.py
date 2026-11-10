"""The dashboard's look: colour tokens, one stylesheet and small HTML pieces.

No Streamlit import here, so the pieces are tested directly. The surface and the accent are the
"smoky lilac" pair (#303032, #AAA8FF). The style is pixel and terminal: Tektur for headings
and figures, JetBrains Mono for text, stepped corners and a prompt before each title. The two chart
colours were checked with the dataviz palette validator on that surface (dark lightness band,
colour-blind separation, contrast); the accent itself is lighter than the chart band allows for
large fills, so it is used for text, lines and highlights, and the charts use the slightly deeper
``SERIES`` colours.
"""

from html import escape
from typing import Any

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
# Each part of the product has its own colour, so a glance says where you are: vacancies are teal,
# growth (profile, learning, practice) amber, the market lilac, the system terracotta.
DOMAINS = {  # a colour per part of the product
    "jobs": "#26A08F",  # vacancies: teal
    "grow": "#8481F5",  # learning: violet
    "market": "#F0605A",  # analytics: red
    "system": "#E2B93B",  # state of the system: yellow
}  # fmt: skip
MUTED_MARK = "#7A7A82"  # context marks next to an emphasised one (3:1 on the card)

FONT_BODY = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
FONT_DISPLAY = "'Tektur', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

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
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 0 !important; }
[data-testid="stMetric"], .dw-pill, .dw-card-box, .dw-facts-box {
  border-radius: 0 !important;
  clip-path: polygon(0 4px, 4px 4px, 4px 0, calc(100% - 4px) 0, calc(100% - 4px) 4px,
    100% 4px, 100% calc(100% - 4px), calc(100% - 4px) calc(100% - 4px),
    calc(100% - 4px) 100%, 4px 100%, 4px calc(100% - 4px), 0 calc(100% - 4px));
}

/* no toolbar over tables and charts: full screen and the table's own search or download only get
   in the way (there are explicit download buttons where a download makes sense) */
[data-testid="stElementToolbar"], button[title*="ullscreen"] { display: none !important; }

/* a ring (progress): a conic gradient, so there is no chart to draw */
.dw-ring { position: relative; width: 6rem; height: 6rem; margin: var(--s2) auto var(--s2);
  border-radius: 50%; display: grid; place-items: center;
  background: conic-gradient(var(--dom, var(--accent)) calc(var(--p) * 1%), var(--line) 0); }
.dw-ring::before { content: ""; position: absolute; inset: 0.9rem; border-radius: 50%;
  background: var(--card); }
.dw-ring b { position: relative; font-family: var(--display); font-size: var(--fs-md);
  color: var(--ink); }
.dw-ring-cap { text-align: center; font-size: var(--fs-xs); color: var(--ink-3); }

/* sidebar */
[data-testid="stSidebar"] { background: var(--card); border-right: 2px solid var(--line); }
[data-testid="stSidebarNavLink"] { border-radius: 0; font-size: var(--fs-sm);
  border-left: 4px solid transparent; }
[data-testid="stSidebarNavLink"]:hover { border-left-color: var(--line); }
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: rgba(170, 168, 255, 0.12); color: var(--accent); border-left-color: var(--accent);
}
[data-testid="stSidebarNavSeparator"], [data-testid="stSidebarNav"] span[class*="Header"] {
  font-family: var(--display); font-size: var(--fs-md); letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-3);
}
[data-testid="stSidebarHeader"] { padding-bottom: 0.4rem; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 0.5rem; }
.dw-side-label { font-family: var(--display); font-size: var(--fs-md); letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-3); margin: 1.1rem 0 0.35rem;
  border-top: 2px solid var(--line); padding-top: 0.7rem; }
.dw-side-label::before { content: "// "; color: var(--accent); font-family: var(--body); }

/* the page header: a prompt, the title and a blinking cursor */
.dw-hero { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 1.5rem; flex-wrap: wrap; margin: 0 0 1.4rem; }
.dw-eyebrow { font-size: var(--fs-xs); letter-spacing: 0.06em; color: var(--accent);
  margin-bottom: 0.6rem; }
.dw-eyebrow::before { content: "$ "; color: var(--ink-3); }
.dw-title { font-family: var(--display); font-weight: 600; font-size: var(--fs-2xl);
  line-height: 1.1;
  letter-spacing: 0.02em; color: var(--ink); margin: 0; }
.dw-title::after { content: "_"; color: var(--cursor); margin-left: 0.12em;
  animation: dw-blink 1.1s steps(1) infinite; }
@keyframes dw-blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .dw-title::after { animation: none; } }
.dw-sub { color: var(--ink-3); font-size: var(--fs-sm); margin-top: 0.6rem; max-width: 48rem; }
.dw-pills { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.dw-pill { display: inline-flex; align-items: center; gap: 0.5rem; background: var(--card);
  border: 2px solid var(--line); padding: 0.28rem 0.8rem; font-size: var(--fs-xs);
  color: var(--ink-2); white-space: nowrap; }
.dw-pill i { font-style: normal; }

/* section labels: "// 01 DYNAMICS" */
.dw-section { font-family: var(--display); font-size: var(--fs-md); letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--ink-3); margin: var(--s6) 0 var(--s3); }
.dw-section::before { content: "// "; color: var(--accent); font-family: var(--body); }
.dw-section b { color: var(--accent); font-weight: 500; margin-right: 0.7rem; }

/* cards: metrics and bordered containers */
[data-testid="stMetric"] { background: var(--card); border: 2px solid var(--line);
  padding: var(--s4); min-height: 8rem; height: 100%; box-sizing: border-box; }
[data-testid="stHorizontalBlock"] { align-items: stretch; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] { height: 100%; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > :only-child { height: 100%; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > :only-child >
  [data-testid="stVerticalBlockBorderWrapper"] { height: 100%; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] >
  [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]) { height: 100%; }
[data-testid="stMetricLabel"] * { font-family: var(--display); font-size: var(--fs-sm) !important;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3); }
[data-testid="stMetricValue"] { font-family: var(--display); font-weight: 600;
  font-size: var(--fs-xl); }
.dw-card-title { font-family: var(--display); font-size: var(--fs-md); letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-2); margin: 0 0 0.2rem; }
.dw-card-title::before { content: "▪ "; color: var(--accent); }
.dw-card-note { color: var(--ink-3); font-size: var(--fs-xs); margin: 0 0 0.6rem; }

/* tabs: the open one gets a prompt arrow */
[data-baseweb="tab-list"] { gap: 0.3rem; border-bottom: 2px solid var(--line); }
button[data-baseweb="tab"] { font-family: var(--display); font-size: var(--fs-md);
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
.dw-chip { border: 2px solid var(--line); padding: 0.12rem 0.55rem; font-size: var(--fs-xs);
  color: var(--ink-2); }
.dw-chip.req { border-color: var(--accent); color: var(--accent);
  background: rgba(170, 168, 255, 0.1); }
.dw-chip.req::before { content: "■ "; font-size: 0.8em; vertical-align: 0.1em; }
.dw-facts { display: grid; grid-template-columns: max-content 1fr; gap: 0.35rem 1.2rem;
  margin: 0.4rem 0 0.9rem; font-size: var(--fs-sm); }
.dw-facts dt { color: var(--ink-3); }
.dw-facts dd { margin: 0; color: var(--ink); }
.dw-lead { font-family: var(--display); font-size: var(--fs-xl); line-height: 1.2;
  color: var(--ink);
  margin: 0.1rem 0 0.2rem; }
.dw-muted { color: var(--ink-3); font-size: var(--fs-sm); }

/* a small screen: one column, a smaller title */
@media (max-width: 720px) {
  .dw-title { font-size: var(--fs-xl); }
  .block-container { padding-left: 1rem; padding-right: 1rem; }
}
"""

_MOTION = """
/* motion: things arrive in steps (pixel style), never glide; all of it stops for reduced motion */
@keyframes dw-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
/* nothing here plays on arrival: a rerun redraws the page after every click, and an entrance that
   replays each time reads as lag; only a state (the frog, a running pulse) moves */
.dw-typed { display: inline-block; }
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
}
"""

_BLOCKS = """
/* bracket statistics: [ ВІДКРИТО: 6 710 ] */
.dw-stats { display: flex; flex-wrap: wrap; gap: 0.5rem 1.6rem; margin: 0.2rem 0 1rem; }
.dw-stat { display: inline-flex; align-items: baseline; gap: 0.55rem; font-size: var(--fs-sm);
  color: var(--ink-3); letter-spacing: 0.04em; text-transform: uppercase; }
.dw-stat i { font-style: normal; color: var(--accent); font-size: var(--fs-lg); line-height: 1; }
.dw-stat b { font-family: var(--display); font-weight: 400; color: var(--ink);
  font-size: var(--fs-lg);
  letter-spacing: 0.02em; }
.dw-stat em { font-style: normal; }

/* the frog card in the sidebar and the profile */
.dw-pet { display: flex; gap: 0.8rem; align-items: center; padding: 0.6rem 0.4rem 0.2rem; }
.dw-pet-text { min-width: 0; flex: 1; font-size: var(--fs-xs); color: var(--ink-3);
  line-height: 1.5; }
.dw-pet-name { font-family: var(--display); font-size: var(--fs-sm); color: var(--ink); }
.dw-pet-name b { color: var(--accent); font-weight: 400; }
.dw-xp { height: 8px; background: var(--line); margin: 0.35rem 0 0.25rem; }
.dw-xp span { display: block; height: 100%; background: var(--accent); }
.dw-medal { display: inline-block; border: 2px solid var(--line); color: var(--ink-3);
  padding: 0.15rem 0.55rem; margin: 0 0.4rem 0.4rem 0; font-size: var(--fs-xs); }
.dw-medal.on { border-color: var(--accent); color: var(--accent);
  background: rgba(170, 168, 255, 0.1); }
.dw-medal.on::before { content: "★ "; }
.dw-resource { font-size: var(--fs-sm); }

/* the menu sections are headings, not folders: no chevron, no click */
[data-testid="stNavSectionHeader"] { pointer-events: none; cursor: default; }
[data-testid="stNavSectionHeader"] [data-testid="stIconMaterial"] { display: none; }

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
  font-size: var(--fs-sm); color: var(--ink-2); }
.dw-leg i { font-style: normal; color: var(--accent); }
.dw-leg b { display: inline-block; width: 0.7rem; height: 0.7rem; margin: 0 0.45rem 0 0.4rem; }

/* tiles: a direction, a vacancy */
.dw-dir, .dw-vac { background: var(--card); border: 2px solid var(--line); padding: var(--s4);
  margin-bottom: 0.4rem; box-sizing: border-box;
  clip-path: polygon(0 4px, 4px 4px, 4px 0, calc(100% - 4px) 0,
  calc(100% - 4px) 4px, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) calc(100% - 4px),
  calc(100% - 4px) 100%, 4px 100%, 4px calc(100% - 4px), 0 calc(100% - 4px)); }
.dw-dir-name { font-family: var(--display); font-size: var(--fs-lg); color: var(--ink);
  letter-spacing: 0.04em; text-transform: uppercase; }
.dw-dir-count { font-family: var(--display); font-size: var(--fs-xl); color: var(--accent);
  line-height: 1.1; margin: 0.2rem 0; }
.dw-dir-count small { font-size: var(--fs-sm); color: var(--ink-3); margin-left: 0.4rem; }
.dw-meter { height: 8px; background: var(--line); margin: 0.4rem 0 0.7rem; }
.dw-meter span { display: block; height: 100%; background: var(--accent); }
.dw-dir { height: 12rem; overflow: hidden; }
.dw-vac { height: 11rem; overflow: hidden; }
.dw-vac-title { font-family: var(--display); font-size: var(--fs-lg); color: var(--ink);
  line-height: 1.2; }
.dw-vac-meta { color: var(--ink-3); font-size: var(--fs-sm); margin: 0.3rem 0 0.5rem; }
.dw-vac-pay { color: var(--accent); font-size: var(--fs-sm); }

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
  margin: 0.4rem 0 1rem; font-size: var(--fs-xs); }
.dw-active .dw-tag { border: 2px solid var(--accent); color: var(--accent);
  padding: 0.1rem 0.6rem; background: rgba(170, 168, 255, 0.08); }
.dw-active .dw-none { color: var(--ink-3); }
.dw-answer { border-left: 4px solid var(--accent); background: var(--card);
  padding: var(--s3) var(--s4);
  margin: 0.6rem 0; color: var(--ink); font-size: var(--fs-md); line-height: 1.55; }
.dw-q-meta { color: var(--ink-3); font-size: var(--fs-sm); margin-bottom: 0.3rem; }
.dw-fl { font-family: var(--display); font-size: var(--fs-md); letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-2); margin-bottom: 0.3rem; }
.dw-badge { display: inline-block; min-width: 1.3rem; padding: 0 0.35rem; margin-left: 0.5rem;
  background: var(--accent); color: #1B1B1D; text-align: center; font-size: var(--fs-xs); }
"""

_WORKSPACE = """
.dw-skillrow { display: grid; grid-template-columns: 11rem 1fr 7.5rem; gap: var(--s3);
  align-items: center; font-size: var(--fs-sm); margin: 0.25rem 0; }
.dw-skillrow .dw-bar { height: 8px; background: var(--line); }
.dw-skillrow .dw-bar span { display: block; height: 100%; background: var(--d-market); }
.dw-skillrow.req .dw-bar span { background: var(--d-jobs); }
.dw-skillrow .dw-pct { color: var(--ink-3); text-align: right; }
.dw-skillrow .dw-name.mine::after { content: " ✓"; color: var(--d-jobs); }
/* domains: a colour per part of the product, used for the label, the marker and the accent */
.dw-d-jobs { --dom: var(--d-jobs); } .dw-d-grow { --dom: var(--d-grow); }
.dw-d-market { --dom: var(--d-market); } .dw-d-system { --dom: var(--d-system); }
.dw-section::before, .dw-eyebrow, .dw-stat i, .dw-card-title::before { color: var(--dom,
  var(--accent)); }
.dw-section b { color: var(--dom, var(--accent)); }
[data-testid="stSidebarNavItems"] > div:nth-child(2) { --dom: var(--d-jobs); }
[data-testid="stSidebarNavItems"] > div:nth-child(3) { --dom: var(--d-grow); }
[data-testid="stSidebarNavItems"] > div:nth-child(4) { --dom: var(--d-market); }
[data-testid="stSidebarNavItems"] > div:nth-child(5) { --dom: var(--d-system); }
[data-testid="stNavSectionHeader"] { border-left: 4px solid var(--dom, var(--line));
  padding-left: 0.5rem; }
[data-testid="stSidebarNavItems"] a[aria-current="page"] {
  border-left-color: var(--dom, var(--accent)) !important;
  color: var(--dom, var(--accent)) !important; }

/* the menu is compact so that it fits without a scrollbar; the profile is the avatar below */
[data-testid="stSidebarNavLink"] { padding-top: 0.1rem !important;
  padding-bottom: 0.1rem !important; min-height: 1.9rem !important; }
[data-testid="stSidebarNavItems"] { gap: 0 !important; }
[data-testid="stSidebarNavLink"][href$="profile"] { display: none; }
[data-testid="stNavSectionHeader"] { margin-top: 0.3rem; padding-top: 0;
  padding-bottom: 0; min-height: 0; }
[data-testid="stNavSectionHeader"]:empty { display: none; }
[data-testid="stSidebarNavItems"] > div:nth-child(5) [data-testid="stNavSectionHeader"] {
  display: none; }
/* the item has no heading to carry the colour of its group, so the item itself carries it */
[data-testid="stSidebarNavItems"] > div:nth-child(5) a { border-left: 4px solid var(--dom); }
[data-testid="stSidebarHeader"] { padding-top: 0.6rem; padding-bottom: 0.2rem; }
[data-testid="stSidebarNav"] { padding-bottom: 0; }
[data-testid="stSidebarUserContent"] { padding-bottom: 0 !important; }


.st-key-dw_keys { position: absolute; width: 0; height: 0; overflow: hidden; }

.st-key-cat_rows, .st-key-mkt_rows { display: flex; flex-direction: column; gap: var(--s2); }
.st-key-cat_rows button, .st-key-mkt_rows button { height: auto; min-height: 3.4rem;
  padding: var(--s2) var(--s3); justify-content: flex-start; text-align: left;
  white-space: pre-line; background: var(--card); border: 2px solid var(--line);
  border-left-width: 4px; border-radius: 0; }
.st-key-cat_rows button p, .st-key-mkt_rows button p { text-align: left; margin: 0;
  font-size: var(--fs-sm); color: var(--ink-3); line-height: 1.45; }
.st-key-cat_rows button p strong, .st-key-mkt_rows button p strong { color: var(--ink);
  font-size: var(--fs-md); display: block; }
.st-key-cat_rows button:hover, .st-key-mkt_rows button:hover { border-color: var(--accent); }
.st-key-cat_rows button[kind="primary"], .st-key-mkt_rows button[kind="primary"] {
  background: rgba(170, 168, 255, 0.14); border-color: var(--accent); }
.st-key-cat_detail, .st-key-mkt_detail { position: sticky; top: 3.5rem; }
.st-key-dw_undo { border: 2px solid var(--accent); background: rgba(170, 168, 255, 0.10);
  padding: var(--s2) var(--s3); margin-bottom: var(--s3); }
.dw-undo { font-size: var(--fs-sm); color: var(--ink); }
.dw-pager { text-align: right; font-size: var(--fs-sm); color: var(--ink-3);
  padding-bottom: 0.6rem; }

/* the filter bar sits above the list, not in the menu: every control has a label of one height
   above it and the same height, so the rows line up */
.st-key-cat_filters [data-testid="stHorizontalBlock"] { gap: var(--s4); align-items: flex-start; }
.st-key-cat_filters .dw-fl { font-size: var(--fs-xs); height: 1.2rem; margin: 0 0 var(--s2);
  line-height: 1.2rem; }
.st-key-cat_filters button, .st-key-cat_filters [data-baseweb="select"] > div,
.st-key-cat_filters input { min-height: 2.5rem; }
.st-key-cat_filters [data-testid="stPills"] { min-height: 2.5rem; align-items: center;
  flex-wrap: wrap; gap: var(--s2); }
.st-key-cat_filters { border: 2px solid var(--line); background: var(--card);
  padding: var(--s4) var(--s5); margin-bottom: var(--s4); }
.st-key-cat_filters [data-testid="stVerticalBlock"] { gap: var(--s3); }

/* the avatar sits at the bottom of the sidebar whatever else is above it */
[data-testid="stSidebarContent"] { display: flex; flex-direction: column; height: 100vh;
  overflow: hidden; }
[data-testid="stSidebarNav"] { flex: 1 1 auto; min-height: 0; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: var(--line) transparent; }
[data-testid="stSidebarUserContent"] { flex: none; }
.st-key-dw_avatar { position: relative; z-index: 5; background: var(--card);
  border-top: 2px solid var(--line); padding: var(--s2) 0 var(--s1); }
@media (max-height: 780px) {
  [data-testid="stSidebarNavLink"] { min-height: 1.6rem !important;
    border-left: 4px solid color-mix(in srgb, var(--dom, var(--line)) 55%, transparent); }
  [data-testid="stNavSectionHeader"] { display: none; }
  [data-testid="stSidebarNavItems"] > div { margin-top: var(--s2); }
}
/* the whole card opens the profile: the page link is stretched over it and left invisible */
.st-key-dw_avatar { cursor: pointer; }
.st-key-dw_avatar .st-key-dw_avatar_open { position: absolute; inset: 0; z-index: 2; }
.st-key-dw_avatar .st-key-dw_avatar_open a { height: 100%; opacity: 0; }
.st-key-dw_avatar:focus-within, .st-key-dw_avatar:hover { background: rgba(170, 168, 255, 0.08); }
.dw-avatar { display: flex; gap: var(--s3); align-items: center; }
.dw-avatar-pic { flex: none; width: 56px; height: 56px; background: var(--bg); overflow: hidden;
  border: 2px solid var(--dom, var(--d-grow)); display: flex; align-items: center;
  justify-content: center; }
.dw-avatar-pic svg { width: 120%; height: auto; margin-top: 6px; }
.dw-avatar-text { min-width: 0; flex: 1; font-size: var(--fs-xs); color: var(--ink-3);
  line-height: 1.45; }
.dw-avatar-name { font-family: var(--display); font-size: var(--fs-md); color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dw-avatar-name b { color: var(--d-grow); font-weight: 600; }
.dw-kbd { display: inline-block; border: 2px solid var(--line); border-bottom-width: 4px;
  padding: 0 0.4rem; font-size: var(--fs-xs); color: var(--ink-2); background: var(--bg);
  font-family: var(--body); line-height: 1.5; margin: 0 0.15rem; }
.dw-hint { font-size: var(--fs-xs); color: var(--ink-3); margin-top: var(--s2); }

/* an action: what to do now, coloured by the part of the product it leads to */
.dw-todo { background: var(--card); border: 2px solid var(--line);
  border-left: 6px solid var(--dom);
  padding: var(--s3) var(--s4); margin-bottom: var(--s2); }
.dw-todo-kind { font-family: var(--display); font-size: var(--fs-xs); letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--dom); }
.dw-todo-text { font-size: var(--fs-md); color: var(--ink); margin-top: 0.15rem; }

/* a key chip row for the help overlay and the command palette (built by dashboard_keys) */
#dw-overlay { position: fixed; inset: 0; z-index: 100000; background: rgba(20, 20, 22, 0.72);
  display: flex; align-items: flex-start; justify-content: center; padding-top: 12vh; }
#dw-overlay .dw-box { width: min(640px, 92vw); background: var(--card);
  border: 2px solid var(--accent);
  color: var(--ink); font-family: var(--body); max-height: 70vh; overflow: auto; }
#dw-overlay input { width: 100%; box-sizing: border-box; padding: var(--s3) var(--s4);
  font: inherit;
  font-size: var(--fs-md); background: var(--bg); color: var(--ink); border: 0;
  border-bottom: 2px solid var(--line); outline: none; }
#dw-overlay .dw-row { display: flex; justify-content: space-between; gap: var(--s4);
  padding: var(--s2) var(--s4); font-size: var(--fs-sm); cursor: pointer; }
#dw-overlay .dw-row.on { background: rgba(170, 168, 255, 0.16); color: var(--accent); }
#dw-overlay .dw-row span:last-child { color: var(--ink-3); }
#dw-overlay h3 { margin: 0; padding: var(--s3) var(--s4); font-family: var(--display);
  font-size: var(--fs-md); color: var(--accent); border-bottom: 2px solid var(--line); }
"""


def css() -> str:
    """The stylesheet, ready for a <style> tag."""
    variables = (
        f":root {{ --bg: {BG}; --card: {CARD}; --line: {LINE}; --ink: {INK}; --ink-2: {INK_2};"
        f" --ink-3: {INK_3}; --accent: {ACCENT}; --cursor: {SERIES[1]}; --ok: #7ED5B0;"
        f" --warn: #F2A56D; --bad: #FF7A6B;"
        f" --body: {FONT_BODY}; --display: {FONT_DISPLAY};"
        f" --fs-xs: 0.75rem; --fs-sm: 0.85rem; --fs-md: 1rem; --fs-lg: 1.25rem; --fs-xl: 1.75rem;"
        f" --fs-2xl: 2.5rem; --s1: 0.25rem; --s2: 0.5rem; --s3: 0.75rem; --s4: 1rem; --s5: 1.5rem;"
        f" --s6: 2rem; --d-jobs: {DOMAINS['jobs']}; --d-grow: {DOMAINS['grow']};"
        f" --d-market: {DOMAINS['market']}; --d-system: {DOMAINS['system']}; }}"
    )
    return f"<style>{variables}{_STYLE}{_MOTION}{_BLOCKS}{_WORKSPACE}</style>"


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
    domain: str | None = None,
) -> str:
    """The header of a page; ``pills`` are already-built chips (see ``pill``).

    With ``typed_subtitle`` the line under the title types itself out.
    """
    line = typed(subtitle) if typed_subtitle and subtitle else escape(subtitle)
    sub = f'<div class="dw-sub">{line}</div>' if subtitle else ""
    chips = f'<div class="dw-pills">{"".join(pills)}</div>' if pills else ""
    return (
        f'<div class="dw-hero{_domain(domain)}"><div>'
        f'<div class="dw-eyebrow">{escape(eyebrow)}</div>'
        f'<h1 class="dw-title">{escape(title)}</h1>{sub}</div>{chips}</div>'
    )


def _domain(domain: str | None) -> str:
    return f" dw-d-{domain}" if domain in DOMAINS else ""


def section(label: str, number: int | None = None, domain: str | None = None) -> str:
    """A small uppercase label above a block; ``domain`` (jobs, grow, market, system) colours it."""
    mark = f"<b>{number:02d}</b>" if number is not None else ""
    return f'<div class="dw-section{_domain(domain)}">{mark}{escape(label)}</div>'


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


def stats(items: list[tuple[str, str]], domain: str | None = None) -> str:
    """Bracketed figures in a row: ``[ ВІДКРИТО: 6 710 ]``; they arrive one after another."""
    parts = "".join(
        f'<span class="dw-stat" style="--i:{n}"><i>[</i><em>{escape(label)}:</em>'
        f"<b>{escape(value)}</b><i>]</i></span>"
        for n, (label, value) in enumerate(items)
    )
    return f'<div class="dw-stats{_domain(domain)}">{parts}</div>'


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


def ring(ratio: float, caption: str, domain: str) -> str:
    """One value from 0 to 1 as a ring with the percent inside and a caption below it."""
    percent = round(min(max(float(ratio), 0.0), 1.0) * 100)
    return (
        f'<div class="dw-ring{_domain(domain)}" role="img" style="--p:{percent}" '
        f'aria-label="{escape(caption)}: {percent}%"><b>{percent}%</b></div>'
        f'<div class="dw-ring-cap">{escape(caption)}</div>'
    )


def todo(kind: str, text: str, domain: str) -> str:
    """One thing to do now: a small label, the text, and the colour of where it leads."""
    return (
        f'<div class="dw-todo{_domain(domain)}"><div class="dw-todo-kind">{escape(kind)}</div>'
        f'<div class="dw-todo-text">{escape(text)}</div></div>'
    )


def avatar(svg: str, name: str, level: int, stage: str, ratio: float, notes: list[str]) -> str:
    """The user card for the foot of the sidebar: the frog in a frame, a name, a level bar."""
    width = max(2, min(100, round(ratio * 100)))
    lines = " · ".join(escape(note) for note in notes)
    return (
        f'<div class="dw-avatar dw-d-grow"><div class="dw-avatar-pic">{svg}</div>'
        f'<div class="dw-avatar-text"><div class="dw-avatar-name">{escape(name)}</div>'
        f"<div>{escape(stage)} · <b>рівень {level}</b></div>"
        f'<div class="dw-xp" role="img" aria-label="{width}% до наступного рівня">'
        f'<span style="width:{width}%"></span></div><div>{lines}</div></div></div>'
    )


def kbd(*keys: str) -> str:
    """Key caps for a shortcut hint: ``kbd("g", "c")``."""
    return "".join(f'<span class="dw-kbd">{escape(key)}</span>' for key in keys)


def skill_rows(items: list[dict[str, Any]]) -> str:
    """Skills of one vacancy against the market: a bar for the share of all vacancies asking for
    each, required ones in teal, a tick on the ones you know. Items: skill, share (0-1 or None),
    required, mine."""
    top = max([float(i["share"] or 0) for i in items] + [0.01])
    rows = []
    for item in items:
        share = float(item["share"] or 0)
        width = max(2, round(share / top * 100)) if item["share"] else 0
        pct = f"{share:.0%}" if item["share"] else "—"
        rows.append(
            f'<div class="dw-skillrow{" req" if item["required"] else ""}">'
            f'<span class="dw-name{" mine" if item["mine"] else ""}">{escape(str(item["skill"]))}'
            f'</span><span class="dw-bar"><span style="width:{width}%"></span></span>'
            f'<span class="dw-pct">{pct} ринку</span></div>'
        )
    return "".join(rows)
