"""The dashboard's look: colour tokens, one stylesheet and small HTML pieces.

No Streamlit import here, so the pieces are tested directly. The look is "soft signal": a plombir
(ice-cream white) page, three colours from one study (powder blue, mauve, wine) worn as whole
blocks, a heavy grotesque for titles, small capitals with wide tracking for labels, and numbers
and figures made of dots (``dashboard_dots``). The menu has no panel of its own: it sits on the
page. The four chart colours are saturated relatives of the three (the originals are too pale or
too dark to be marks) and passed the dataviz palette validator on the card.
"""

from html import escape
from typing import Any

BG = "#FBF3E1"  # plombir: the cream of vanilla ice cream, the page everywhere
CARD = "#FFFDF7"
LINE = "#E9DDC8"  # hairlines
GRID = "#EFE4D0"  # chart grid, unlit dots, tracks of meters
INK = "#22252B"
INK_2 = "#474A52"
INK_3 = "#68635C"  # muted text: 4.9:1 on the page, 5.8:1 on the card
POWDER = "#C0D8E6"  # the three colours of the study, worn as blocks
MAUVE = "#C77E96"
WINE = "#5B3044"
ACCENT = WINE  # links, the open page, lit dots

# Chart colours, in a fixed order (an entity keeps its colour whatever the filter shows). All four
# passed the palette validator on the card surface; a chart never needs a fifth (the tail is folded
# into "Інші"). They are relatives of the study: berry, periwinkle, gold, rose.
SERIES = ("#9A3F6C", "#6C8FD8", "#B98A1E", "#D76C8E")
SOURCE_ORDER = ("dou", "djinni")  # the sources always wear the first two colours in this order
MARK = SERIES[0]  # one-series bars and lines
# Each part of the product has its own colour, so a glance says where you are. Small text wears
# them, so they are dark steps (4.5:1 on the card); the page tints them itself.
DOMAINS = {  # a colour per part of the product
    "jobs": "#2F6F94",  # vacancies: the deep step of powder
    "grow": "#6B3F86",  # learning: plum
    "market": "#A8456A",  # analytics: the deep step of mauve
    "system": "#8A6A12",  # state of the system: ochre
}  # fmt: skip
MUTED_MARK = "#8F8A80"  # context marks next to an emphasised one (3:1 on the card)

FONT_BODY = "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif"
FONT_DISPLAY = FONT_BODY  # titles are the same grotesque, heavy
FONT_DOTS = "'Doto', 'Inter', system-ui, sans-serif"  # numbers; Latin only, the rest falls back

# State is never colour alone: every tone carries an icon and a word.
TONES = {
    "ok": ("✓", "var(--ok)"),
    "warn": ("▲", "var(--warn)"),
    "bad": ("✕", "var(--bad)"),
    "neutral": ("●", "var(--ink-3)"),
}

_STYLE = """
.stApp { background-color: var(--bg); font-family: var(--body);
 }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1400px; }
h1, h2, h3, h4 { font-family: var(--display) !important; }

/* stepped (pixel) corners: the clip removes the four corner squares of the border */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: var(--r) !important; }
[data-testid="stMetric"], .dw-pill, .dw-card-box, .dw-facts-box {
  border-radius: var(--r) !important;
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
[data-testid="stSidebar"] { background: var(--card); border-right: 1px solid var(--line); }
[data-testid="stSidebarNavLink"] { border-radius: var(--r); font-size: var(--fs-sm);
  border-left: 4px solid transparent; }
[data-testid="stSidebarNavLink"]:hover { border-left-color: var(--line); }
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent);
  border-left-color: var(--accent);
}
[data-testid="stSidebarNavSeparator"], [data-testid="stSidebarNav"] span[class*="Header"] {
  font-family: var(--display); font-size: var(--fs-md); color: var(--ink-3);
}
[data-testid="stSidebarHeader"] { padding-bottom: 0.4rem; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 0.5rem; }
.dw-side-label { font-family: var(--display); font-size: var(--fs-md); color: var(--ink-3);
  margin: 1.1rem 0 0.35rem;
  border-top: 1px solid var(--line); padding-top: 0.7rem; }

/* the page header: a prompt, the title and a blinking cursor */
.dw-hero { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 1.5rem; flex-wrap: wrap; margin: 0 0 1.4rem; }
.dw-eyebrow { font-size: var(--fs-xs); color: var(--accent);
  margin-bottom: 0.6rem; }
.dw-title { font-family: var(--display); font-weight: 600; font-size: var(--fs-2xl);
  line-height: 1.1; color: var(--ink); margin: 0; }
.dw-sub { color: var(--ink-3); font-size: var(--fs-sm); margin-top: 0.6rem; max-width: 48rem; }
.dw-pills { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.dw-pill { display: inline-flex; align-items: center; gap: 0.5rem; background: var(--card);
  border: 1px solid var(--line); padding: 0.28rem 0.8rem; font-size: var(--fs-xs);
  color: var(--ink-2); white-space: nowrap; }
.dw-pill i { font-style: normal; }

/* section labels: "// 01 DYNAMICS" */
.dw-section { font-family: var(--display); font-size: var(--fs-md); color: var(--ink-3);
  margin: var(--s6) 0 var(--s3); }
.dw-section b { color: var(--accent); font-weight: 500; margin-right: 0.7rem; }

/* cards: metrics and bordered containers */
[data-testid="stMetric"] { background: var(--card); border: 1px solid var(--line);
  padding: var(--s4); min-height: 8rem; height: 100%; box-sizing: border-box; }
[data-testid="stHorizontalBlock"] { align-items: stretch; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] { height: 100%; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > :only-child { height: 100%; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > :only-child >
  [data-testid="stVerticalBlockBorderWrapper"] { height: 100%; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] >
  [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]) { height: 100%; }
[data-testid="stMetricLabel"] * { font-family: var(--display);
  font-size: var(--fs-sm) !important; color: var(--ink-3); }
[data-testid="stMetricValue"] { font-family: var(--display); font-weight: 600;
  font-size: var(--fs-xl); }
.dw-card-title { font-family: var(--display); font-size: var(--fs-md); color: var(--ink-2);
  margin: 0 0 0.2rem; }
.dw-card-note { color: var(--ink-3); font-size: var(--fs-xs); margin: 0 0 0.6rem; }

/* tabs: the open one gets a prompt arrow */
[data-baseweb="tab-list"] { gap: 0.3rem; border-bottom: 1px solid var(--line); }
button[data-baseweb="tab"] { font-family: var(--display); font-size: var(--fs-md);
  padding: 0.7rem 0.9rem; }
[data-baseweb="tab-highlight"] { background-color: var(--accent) !important; height: 4px; }
[data-baseweb="tab-border"] { display: none; }

/* inputs and buttons: square */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="base-input"],
button[kind], [data-testid="stDownloadButton"] button, [data-testid="stLinkButton"] a {
  border-radius: var(--r) !important;
}
[data-testid="stDataFrame"] { border: 1px solid var(--line); overflow: hidden; }
[data-testid="stCaptionContainer"] { color: var(--ink-3); }
[data-testid="stPageLink"] a { padding: 0.2rem 0; background: transparent;
  border-radius: var(--r); }
[data-testid="stPageLink"] a:hover { color: var(--accent); }
[data-testid="stAlert"] { border-radius: var(--r); border-left: 4px solid var(--accent); }

/* skill tags and fact lists (the vacancy card) */
.dw-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.3rem 0 0.8rem; }
.dw-chip { border: 1px solid var(--line); padding: 0.12rem 0.55rem; font-size: var(--fs-xs);
  color: var(--ink-2); }
.dw-chip.req { border-color: var(--accent); color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent); }
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
/* motion: all of it stops for reduced motion */
@keyframes dw-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
/* arrival: once, when a page opens (see dashboard_motion.py). The page body is hidden from the
   start and until the page is built (no html.dw-go), then shown at once, with no fade: a fade
   promotes the whole page to its own layer, and the repaint when it ends showed as a flicker.
   Nothing rises or is staggered, so the building of the page is never seen. Only the meters (a
   transform) and the typed line (html.dw-enter) move. A rerun after a click plays nothing. If the
   script ever fails, the body shows itself after 2 s. Under reduced motion it is never hidden. */
@keyframes dw-unhide { to { opacity: 1; } }
@keyframes dw-type { from { width: 0; } to { width: var(--chars); } }
@keyframes dw-caret { 50% { border-right-color: transparent; } }
@keyframes dw-grow { from { transform: scaleX(0); } }
@media (prefers-reduced-motion: no-preference) {
  html:not(.dw-go) [data-testid="stMainBlockContainer"] { opacity: 0;
    animation: dw-unhide 0s 2s forwards; }
}
html.dw-enter .dw-meter span { transform-origin: left;
  animation: dw-grow 0.6s cubic-bezier(0.3, 0.6, 0.2, 1) 0.15s both; }
.dw-typed { display: inline-block; }
html.dw-enter .dw-typed { overflow: hidden; white-space: nowrap; width: var(--chars);
  border-right: 2px solid var(--accent);
  animation: dw-type 1.2s steps(var(--steps)) both, dw-caret 0.7s steps(1) 1.2s 2; }
.dw-pulse span:last-child { animation: dw-pulse 1.6s steps(2) infinite; }
.dw-dir, .dw-vac, [data-testid="stMetric"] { transition: transform 0.15s ease,
  border-color 0.15s ease, box-shadow 0.15s ease; }
.dw-dir:hover, .dw-vac:hover, [data-testid="stMetric"]:hover {
  transform: translateY(-2px); border-color: var(--line-2);
  box-shadow: 0 6px 18px rgba(31, 30, 28, 0.07); }
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
  color: var(--ink-3); }
.dw-stat i { font-style: normal; color: var(--accent); font-size: var(--fs-lg); line-height: 1; }
.dw-stat b { font-family: var(--display); font-weight: 400; color: var(--ink);
  font-size: var(--fs-lg); }
.dw-stat em { font-style: normal; }

/* the frog card in the sidebar and the profile */
.dw-pet { display: flex; gap: 0.8rem; align-items: center; padding: 0.6rem 0.4rem 0.2rem; }
.dw-pet-text { min-width: 0; flex: 1; font-size: var(--fs-xs); color: var(--ink-3);
  line-height: 1.5; }
.dw-pet-name { font-family: var(--display); font-size: var(--fs-sm); color: var(--ink); }
.dw-pet-name b { color: var(--accent); font-weight: 400; }
.dw-xp { height: 8px; background: var(--line); margin: 0.35rem 0 0.25rem; }
.dw-xp span { display: block; height: 100%; background: var(--accent); }
.dw-medal { display: inline-block; border: 1px solid var(--line); color: var(--ink-3);
  padding: 0.15rem 0.55rem; margin: 0 0.4rem 0.4rem 0; font-size: var(--fs-xs); }
.dw-medal.on { border-color: var(--accent); color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent); }
.dw-medal.on::before { content: "★ "; }
.dw-resource { font-size: var(--fs-sm); }

/* the menu sections are headings, not folders: no chevron, no click */
[data-testid="stNavSectionHeader"] { pointer-events: none; cursor: default; }
[data-testid="stNavSectionHeader"] [data-testid="stIconMaterial"] { display: none; }

/* on a desktop the sidebar is part of the layout, not a drawer: it cannot be collapsed. On a
   phone it is a drawer (closed at the start, see dashboard_mobile.py), so its buttons stay */
@media (min-width: 769px) {
  [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"],
  [data-testid="stExpandSidebarButton"], button[kind="headerNoPadding"] {
    display: none !important; }
}

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
.dw-dir, .dw-vac { background: var(--card); border: 1px solid var(--line); padding: var(--s4);
  margin-bottom: 0.4rem; box-sizing: border-box; }
.dw-dir-name { font-family: var(--display); font-size: var(--fs-lg); color: var(--ink); }
.dw-dir-count { font-family: var(--display); font-size: var(--fs-xl); color: var(--accent);
  line-height: 1.1; margin: 0.2rem 0; }
.dw-dir-count small { font-size: var(--fs-sm); color: var(--ink-3); margin-left: 0.4rem; }
.dw-meter { height: 8px; background: var(--line); margin: 0.4rem 0 0.7rem; }
.dw-meter span { display: block; height: 100%; background: var(--accent); }
.dw-dir { min-height: 12rem; }
.dw-vac { min-height: 11rem; }
.dw-vac-title { font-family: var(--display); font-size: var(--fs-lg); color: var(--ink);
  line-height: 1.2; }
.dw-vac-meta { color: var(--ink-3); font-size: var(--fs-sm); margin: 0.3rem 0 0.5rem; }
.dw-vac-pay { color: var(--accent); font-size: var(--fs-sm); }

/* filters: an active one must look different from an idle one */
[data-baseweb="select"]:not(:has([data-baseweb="tag"])) > div { border-style: dashed !important; }
[data-baseweb="select"]:has([data-baseweb="tag"]) > div { border-color: var(--accent) !important;
  background: color-mix(in srgb, var(--accent) 8%, transparent) !important; }
[data-baseweb="tag"] { background: var(--accent) !important; color: #FFFFFF !important;
  border-radius: var(--r) !important; }
[data-baseweb="tag"] span { color: #FFFFFF !important; }
button[kind="pillsActive"] { background: var(--accent) !important; color: #FFFFFF !important;
  border-color: var(--accent) !important; }
button[kind="pills"], button[kind="pillsActive"],
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"] {
  border-radius: var(--r) !important; border-width: 2px !important; }
[data-testid="stBaseButton-pillsActive"] { background: var(--accent) !important;
  color: #FFFFFF !important; border-color: var(--accent) !important; }
[data-testid="stBaseButton-pillsActive"] * { color: #FFFFFF !important; }
.dw-active { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;
  margin: 0.4rem 0 1rem; font-size: var(--fs-xs); }
.dw-active .dw-tag { border: 2px solid var(--accent); color: var(--accent);
  padding: 0.1rem 0.6rem; background: color-mix(in srgb, var(--accent) 8%, transparent); }
.dw-active .dw-none { color: var(--ink-3); }
.dw-answer { border-left: 4px solid var(--accent); background: var(--card);
  padding: var(--s3) var(--s4);
  margin: 0.6rem 0; color: var(--ink); font-size: var(--fs-md); line-height: 1.55; }
.dw-q-meta { color: var(--ink-3); font-size: var(--fs-sm); margin-bottom: 0.3rem; }
.dw-tip { display: inline-flex; align-items: center; justify-content: center; position: relative;
  width: 1.15rem; height: 1.15rem; margin-left: 0.5rem; border-radius: 50%; vertical-align: middle;
  border: 1px solid var(--line-2); color: var(--ink-3); font-size: 0.7rem; font-weight: 700;
  letter-spacing: 0; text-transform: none; cursor: help; background: var(--card); }
.dw-tip:hover, .dw-tip:focus { color: var(--ink); border-color: var(--ink-3); outline: none; }
.dw-tip::after { content: attr(data-tip); position: absolute; left: var(--dx, 0);
  top: calc(100% + 8px);
  width: max-content; max-width: min(21rem, 78vw); padding: 0.6rem 0.8rem; border-radius: 12px;
  background: var(--ink); color: var(--card); font-family: var(--body); font-size: var(--fs-sm);
  font-weight: 400; line-height: 1.45; text-align: left; text-transform: none; white-space: normal;
  opacity: 0; pointer-events: none; transition: opacity 0.12s; z-index: 60; }
.dw-tip:hover::after, .dw-tip:focus::after { opacity: 1; }
.dw-tipline { display: flex; align-items: center; color: var(--ink-3); font-size: var(--fs-sm);
  margin: var(--s2) 0; }
.dw-fl { font-family: var(--display); font-size: var(--fs-md); color: var(--ink-2);
  margin-bottom: 0.3rem; }
.dw-badge { display: inline-block; min-width: 1.3rem; padding: 0 0.35rem; margin-left: 0.5rem;
  background: var(--accent); color: #FFFFFF; text-align: center; font-size: var(--fs-xs); }
"""

_PHONE = """
/* a phone: Streamlit puts every column on its own row below 640 px, and sets the sidebar as a
   drawer below 768 px (see dashboard_mobile.py). The rules here only change what is too big or too
   long for a narrow screen. Last in the stylesheet, so that they win over the desktop ones. */
@media (max-width: 640px) {
  .block-container { padding-top: 3.2rem; padding-bottom: 3rem; }

  /* the typed line is one line of fixed width: on a phone it ran past the edge while it typed (up
     to 590 px on a 384 px screen) and snapped back when it was done. Here it is plain text. */
  html.dw-enter .dw-typed { display: inline; width: auto; white-space: normal; border-right: 0;
    animation: none; }

  /* figures in pairs, not one tall tile under another */
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"])
    > [data-testid="stColumn"] { min-width: calc(50% - 8px) !important;
    flex: 1 1 calc(50% - 8px) !important; }
  [data-testid="stMetric"] { min-height: 6.5rem; padding: var(--s3); }
  [data-testid="stMetricLabel"] *, [data-testid="stMetricDelta"] * { white-space: normal !important;
    overflow: visible !important; text-overflow: clip !important; }
  [data-testid="stPills"], [data-testid="stPills"] > div { flex-wrap: wrap !important;
    overflow: visible !important; }

  /* the filter bar: search and the buttons on a row of their own, the two lists and the source
     with the reset side by side, the pills wrap instead of scrolling sideways */
  .st-key-cat_filters { padding: var(--s3); }
  .st-key-cat_filters [data-testid="stHorizontalBlock"] { gap: var(--s3); }
  .st-key-cat_filters [data-testid="stColumn"] { min-width: calc(100% - 8px) !important; }
  .st-key-cat_filters [data-testid="stColumn"]:nth-child(2):nth-last-child(3),
  .st-key-cat_filters [data-testid="stColumn"]:nth-child(3):nth-last-child(2),
  .st-key-cat_filters [data-testid="stColumn"]:nth-child(2):nth-last-child(2),
  .st-key-cat_filters [data-testid="stColumn"]:nth-child(3):nth-last-child(1) {
    min-width: calc(50% - 8px) !important; }

  /* the sort on a row, the pager (two arrows and the count) on the next one */
  .st-key-cat_bar [data-testid="stColumn"], .st-key-mkt_bar [data-testid="stColumn"] {
    min-width: 0 !important; flex: 1 1 0 !important; }
  .st-key-cat_bar [data-testid="stColumn"]:first-child,
  .st-key-mkt_bar [data-testid="stColumn"]:first-child { min-width: 100% !important; }
  .st-key-cat_bar [data-testid="stColumn"]:last-child,
  .st-key-mkt_bar [data-testid="stColumn"]:last-child { flex-grow: 2 !important; }

  /* the card of a tapped vacancy (its "back" button has the key *_close_open) covers the screen;
     a card nobody has tapped is hidden: below the list it would be a page away */
  .st-key-cat_detail, .st-key-mkt_detail { display: none; }
  .st-key-cat_detail:has(.st-key-cat_close_open), .st-key-mkt_detail:has(.st-key-mkt_close_open) {
    display: flex; position: fixed; inset: 0; z-index: 1000000; overflow-y: auto;
    border-radius: var(--r); background: var(--bg); padding: var(--s3); box-sizing: border-box; }
  .st-key-cat_close_open, .st-key-mkt_close_open { display: block; position: sticky; top: 0;
    z-index: 2; background: var(--bg); padding-bottom: var(--s2); }
}

/* touch: a finger needs a target of about 44 px */
@media (pointer: coarse) {
  button[kind], [data-testid="stDownloadButton"] button, [data-testid="stLinkButton"] a,
  [data-baseweb="select"] > div, [data-baseweb="base-input"] { min-height: 2.75rem; }
  [data-testid="stSidebarNavLink"] { min-height: 2.75rem !important; }
}

/* the drawer is as tall as the visible screen (100vh is taller than it on a phone) and keeps its
   headings: it can scroll, unlike the sidebar of a short desktop window */
@media (max-width: 768px) {
  [data-testid="stSidebarContent"] { height: 100dvh; }
  [data-testid="stNavSectionHeader"] { display: flex; }
}
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
/* a group takes its colour from a page inside it, not from its place: the public copy has fewer
   groups, and a position would paint "Аналітика" in the colour of the vacancies */
[data-testid="stSidebarNavItems"] > div:has(a[href$="catalog"]) { --dom: var(--d-jobs); }
[data-testid="stSidebarNavItems"] > div:has(a[href$="learn"]) { --dom: var(--d-grow); }
[data-testid="stSidebarNavItems"] > div:has(a[href$="market"]) { --dom: var(--d-market); }
[data-testid="stSidebarNavItems"] > div:has(a[href$="system"]) { --dom: var(--d-system); }
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
[data-testid="stSidebarNavItems"] > div:has(a[href$="system"]) [data-testid="stNavSectionHeader"] {
  display: none; }
/* the item has no heading to carry the colour of its group, so the item itself carries it */
[data-testid="stSidebarNavItems"] > div:has(a[href$="system"]) a {
  border-left: 4px solid var(--dom); }
[data-testid="stSidebarHeader"] { padding-top: 0.6rem; padding-bottom: 0.2rem; }
[data-testid="stSidebarNav"] { padding-bottom: 0; }
[data-testid="stSidebarUserContent"] { padding-bottom: 0 !important; }


.st-key-dw_scripts { position: absolute; width: 0; height: 0; overflow: hidden; }

.st-key-cat_rows, .st-key-mkt_rows { display: flex; flex-direction: column; gap: var(--s2); }
.st-key-cat_rows button, .st-key-mkt_rows button { height: 5.2rem; min-height: 5.2rem;
  box-sizing: border-box;
  padding: var(--s2) var(--s3); justify-content: flex-start; align-items: flex-start;
  text-align: left; background: var(--card); border: 1px solid var(--line);
  border-left-width: 4px; border-radius: var(--r); }
/* every box inside the button spans it and starts at the left (Streamlit centres them and lets
   them shrink to their text, which put each line at a different offset) */
.st-key-cat_rows button div, .st-key-mkt_rows button div { width: 100%; min-width: 0;
  justify-content: flex-start; text-align: left; }
/* the lines are separated by a newline in the label; one line each, cut with an ellipsis. Every
   row has the same fixed height, so a row with two lines and one with three line up. The title is
   bold text, not a block: a block followed by a newline would leave an empty line under it */
.st-key-cat_rows button p, .st-key-mkt_rows button p { margin: 0; width: 100%;
  white-space: pre; overflow: hidden; text-overflow: ellipsis; text-align: left;
  font-size: var(--fs-sm); color: var(--ink-3); line-height: 1.4; }
.st-key-cat_rows button p strong, .st-key-mkt_rows button p strong { color: var(--ink);
  font-size: var(--fs-md); }
.st-key-cat_rows button p code, .st-key-mkt_rows button p code { background: none; padding: 0;
  color: var(--accent); font-family: inherit; font-size: var(--fs-sm); }
.st-key-cat_rows button p em, .st-key-mkt_rows button p em { font-style: normal; }
.st-key-cat_rows button:hover, .st-key-mkt_rows button:hover { border-color: var(--accent); }
.st-key-cat_rows button[kind="primary"], .st-key-mkt_rows button[kind="primary"] {
  background: color-mix(in srgb, var(--accent) 14%, transparent); border-color: var(--accent); }
.st-key-cat_detail, .st-key-mkt_detail { position: sticky; top: 3.5rem; }
.st-key-cat_close, .st-key-mkt_close, .st-key-cat_close_open, .st-key-mkt_close_open {
  display: none; }
.st-key-dw_undo { border: 2px solid var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
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
.st-key-cat_filters { border: 1px solid var(--line); background: var(--card);
  padding: var(--s4) var(--s5); margin-bottom: var(--s4); }
.st-key-cat_filters [data-testid="stVerticalBlock"] { gap: var(--s3); }

/* the avatar sits at the bottom of the sidebar whatever else is above it */
[data-testid="stSidebarContent"] { display: flex; flex-direction: column; height: 100vh;
  overflow: hidden; }
[data-testid="stSidebarNav"] { flex: 1 1 auto; min-height: 0; overflow-y: auto;
  scrollbar-width: thin; scrollbar-color: var(--line) transparent; }
[data-testid="stSidebarUserContent"] { flex: none; }
.st-key-dw_avatar { position: relative; z-index: 5; background: var(--card);
  border-top: 1px solid var(--line); padding: var(--s2) 0 var(--s1); }
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
.st-key-dw_avatar:focus-within, .st-key-dw_avatar:hover { background: color-mix(in srgb,
  var(--accent) 8%, transparent); }
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
.dw-kbd { display: inline-block; border: 1px solid var(--line); border-bottom-width: 4px;
  padding: 0 0.4rem; font-size: var(--fs-xs); color: var(--ink-2); background: var(--bg);
  font-family: var(--body); line-height: 1.5; margin: 0 0.15rem; }
.dw-hint { font-size: var(--fs-xs); color: var(--ink-3); margin-top: var(--s2); }

/* an action: what to do now, coloured by the part of the product it leads to */
.dw-todo { background: var(--card); border: 1px solid var(--line);
  border-left: 6px solid var(--dom);
  padding: var(--s3) var(--s4); margin-bottom: var(--s2); }
.dw-todo-kind { font-family: var(--display); font-size: var(--fs-xs); color: var(--dom); }
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
  border-bottom: 1px solid var(--line); outline: none; }
#dw-overlay .dw-row { display: flex; justify-content: space-between; gap: var(--s4);
  padding: var(--s2) var(--s4); font-size: var(--fs-sm); cursor: pointer; }
#dw-overlay .dw-row.on { background: color-mix(in srgb, var(--accent) 16%, transparent);
  color: var(--accent); }
#dw-overlay .dw-row span:last-child { color: var(--ink-3); }
#dw-overlay h3 { margin: 0; padding: var(--s3) var(--s4); font-family: var(--display);
  font-size: var(--fs-md); color: var(--accent); border-bottom: 1px solid var(--line); }
"""


_CALM = """
/* "soft signal": what a token alone cannot say. It comes last, so it wins. */
.stApp { color: var(--ink); background: var(--bg); }
.dw-title { font-weight: 800; letter-spacing: -0.035em; line-height: 1; }
.dw-sub { font-size: var(--fs-md); color: var(--ink-3); }
.dw-lead, .dw-vac-title, .dw-dir-name { font-weight: 700; letter-spacing: -0.02em; }

/* labels: small capitals, wide tracking */
.dw-eyebrow, .dw-section, .dw-card-title, [data-testid="stMetricLabel"] *, .dw-stat em, .dw-fl,
.dw-todo-kind, [data-testid="stNavSectionHeader"], .dw-ring-cap, .dw-q-meta {
  font-family: var(--body); font-size: var(--fs-xs) !important; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.14em; }
.dw-eyebrow { color: var(--dom, var(--accent)); }
.dw-card-title { color: var(--ink-2); }

/* a section: a rule, its number in dots, its name. The number is counted by the page itself */
[data-testid="stMainBlockContainer"] { counter-reset: dw-sec; }
.dw-section { counter-increment: dw-sec; display: flex; align-items: baseline; gap: var(--s3);
  color: var(--ink-2); border-top: 1px solid var(--line); padding-top: var(--s3); }
.dw-section::before { content: counter(dw-sec, decimal-leading-zero); font-family: var(--dots);
  font-weight: 800; font-size: var(--fs-md); letter-spacing: 0.04em;
  color: var(--dom, var(--accent)); }
.dw-section b { display: none; }

/* numbers are made of dots */
.dw-num, [data-testid="stMetricValue"], .dw-stat b, .dw-dir-count {
  font-family: var(--dots); font-weight: 800; letter-spacing: 0.02em; }

/* surfaces: white cards with generous corners on the plombir page */
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stMetric"], .dw-dir, .dw-vac,
.dw-todo, .dw-answer, .st-key-cat_filters, [data-testid="stDataFrame"], [data-testid="stAlert"] {
  border-radius: var(--r) !important; }
[data-testid="stMetric"], .dw-dir, .dw-vac { box-shadow: none; }
.dw-dir-count { color: var(--ink); }

/* figures in a row: whole blocks of colour, as in the study */
.dw-stats { gap: var(--s3); }
.dw-stat { flex: 1 1 9rem; flex-direction: column; align-items: flex-start; gap: var(--s2);
  padding: var(--s4); min-width: 0; border-radius: var(--r); border: 0; color: var(--ink);
  background: var(--card); box-shadow: inset 0 0 0 1px var(--line); }
.dw-stat:nth-child(4n + 1) { background: var(--powder); box-shadow: none; }
.dw-stat:nth-child(4n + 2) { background: var(--mauve); box-shadow: none; }
.dw-stat:nth-child(4n + 3) { background: var(--wine); box-shadow: none; color: var(--bg); }
.dw-stat:nth-child(4n + 3) b, .dw-stat:nth-child(4n + 3) em { color: var(--bg); }
.dw-stat i, .dw-leg i { display: none; }
.dw-stat b { font-size: var(--fs-xl); line-height: 1; color: var(--ink); }
.dw-stat em { color: var(--ink-2); white-space: nowrap; letter-spacing: 0.08em; }
.dw-leg b { border-radius: 50%; }

/* things to do, tags, meters */
.dw-todo { border: 0; background: color-mix(in srgb, var(--dom) 13%, var(--card)); }
.dw-chip, .dw-medal, .dw-pill, .dw-active .dw-tag, [data-baseweb="tag"],
button[kind="pills"], button[kind="pillsActive"], [data-testid="stBaseButton-pills"],
[data-testid="stBaseButton-pillsActive"] { border-radius: 999px !important;
  border-width: 1px !important; }
.dw-chip.req { background: var(--powder); border-color: var(--powder); color: var(--ink); }
.dw-xp, .dw-meter, .dw-skillrow .dw-bar { border-radius: 999px; background: var(--grid);
  overflow: hidden; }
.dw-xp span, .dw-meter span, .dw-skillrow .dw-bar span { border-radius: 999px; }
.dw-meter span { background: var(--mauve); }
.dw-pulse span { border-radius: 50%; width: 10px; height: 10px; }

/* the menu has no panel: it sits on the page; the open page is a wine pill */
[data-testid="stSidebar"] { background: transparent; border-right: 0; }
[data-testid="stSidebarNavLink"] { border-radius: 999px !important; border-left: 0 !important;
  margin: 1px 0; padding-left: 0.9rem; }
[data-testid="stSidebarNavLink"]:hover { background: color-mix(in srgb, var(--wine) 8%,
  transparent); }
[data-testid="stSidebarNavItems"] a[aria-current="page"] { background: var(--wine) !important; }
[data-testid="stSidebarNavItems"] a[aria-current="page"] * { color: var(--bg) !important; }
[data-testid="stNavSectionHeader"] { border-left: 0 !important; padding-left: 0.9rem;
  color: var(--dom, var(--ink-3)); }
.st-key-dw_avatar { background: transparent; }
.dw-avatar-pic { border-radius: 50%; border-width: 1px; background: var(--powder); }

/* a select shows its whole value, and its list is as wide as its longest option */
[data-baseweb="select"] div[value], [data-baseweb="select"] [role="combobox"] {
  text-overflow: clip; }
[data-baseweb="popover"] [role="listbox"] { min-width: max-content; }
[data-baseweb="popover"] li { white-space: nowrap; }

/* tabs, lists and the open vacancy */
button[data-baseweb="tab"] { font-family: var(--body); font-weight: 600; }
[data-baseweb="tab-highlight"] { height: 3px; border-radius: 999px; }
.st-key-cat_rows button, .st-key-mkt_rows button { border-radius: 16px !important;
  border-width: 1px; border-left-width: 1px; }
.st-key-cat_rows button[kind="primary"], .st-key-mkt_rows button[kind="primary"] {
  background: var(--powder); border-color: var(--powder); }
.st-key-cat_rows button[kind="primary"] p, .st-key-mkt_rows button[kind="primary"] p {
  color: var(--ink-2); }
.st-key-dw_undo { border-radius: var(--r); border-width: 1px; }
#dw-overlay { background: color-mix(in srgb, var(--wine) 35%, transparent); }
#dw-overlay .dw-box { border: 0; border-radius: var(--r);
  box-shadow: 0 24px 60px color-mix(in srgb, var(--wine) 30%, transparent); }
.dw-kbd { border-radius: 6px; border-width: 1px; border-bottom-width: 2px; }

/* a phone: the menu is a drawer over the page, so it is frosted glass, not nothing (on a desktop it
   sits on the page with no panel). A translucent cream, a strong blur, a bright rim and a soft
   shadow; where the browser cannot blur, the cream is opaque enough to read. */
@media (max-width: 768px) {
  [data-testid="stSidebar"] { background: rgba(251, 243, 225, 0.94);
    border-right: 1px solid rgba(255, 255, 255, 0.7); border-radius: 0 28px 28px 0;
    box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.55), 0 18px 60px rgba(34, 37, 43, 0.22); }
  [data-testid="stSidebarContent"] { background: transparent; }
}
@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  @media (max-width: 768px) {
    [data-testid="stSidebar"] { background: rgba(251, 243, 225, 0.55);
      -webkit-backdrop-filter: blur(28px) saturate(1.7);
      backdrop-filter: blur(28px) saturate(1.7); }
  }
}

/* the key of a figure of parts: colour, name, share (big), value */
.dw-key { display: grid; gap: var(--s2); margin: var(--s3) 0 var(--s2); }
.dw-key-row { display: grid; grid-template-columns: 0.8rem 1fr auto 4.5rem; gap: var(--s3);
  align-items: baseline; font-size: var(--fs-sm); color: var(--ink-2);
  border-bottom: 1px solid var(--line); padding-bottom: var(--s2); }
.dw-key-dot { width: 0.7rem; height: 0.7rem; border-radius: 50%; align-self: center; }
.dw-key-row b { font-size: var(--fs-lg); color: var(--ink); }
.dw-key-row em { font-style: normal; text-align: right; color: var(--ink-3); }

/* figures made of dots (dashboard_dots.py) */
.dw-dots { display: block; width: 100%; height: auto; overflow: visible; }
.dw-dot-ring { max-width: 9.5rem; margin: 0 auto; }
.dw-dot-waffle { max-width: 11rem; margin: var(--s2) auto; }
.dw-dot-cols { max-height: 19rem; margin: var(--s2) 0; }
.dw-dot-spark { max-height: 2.2rem; }
.dw-dots .dw-num { font-family: var(--dots); font-weight: 800; fill: var(--ink); }
.dw-dots .dw-dot-axis { font-family: var(--body); font-weight: 500; fill: var(--ink-3); }
"""


def css() -> str:
    """The stylesheet, ready for a <style> tag."""
    variables = (
        f":root {{ --bg: {BG}; --card: {CARD}; --line: {LINE}; --ink: {INK}; --ink-2: {INK_2};"
        f" --ink-3: {INK_3}; --accent: {ACCENT}; --cursor: {SERIES[1]}; --ok: #2E7D5B;"
        f" --warn: #A8650A; --bad: #C0392B; --grid: {GRID}; --line-2: #D8CEBC; --r: 22px;"
        f" --powder: {POWDER}; --mauve: {MAUVE}; --wine: {WINE}; --dots: {FONT_DOTS};"
        f" --dot-rest: {GRID};"
        f" --body: {FONT_BODY}; --display: {FONT_DISPLAY};"
        f" --fs-xs: 0.75rem; --fs-sm: 0.85rem; --fs-md: 1rem; --fs-lg: 1.25rem; --fs-xl: 1.75rem;"
        f" --fs-2xl: 2.5rem; --s1: 0.25rem; --s2: 0.5rem; --s3: 0.75rem; --s4: 1rem; --s5: 1.5rem;"
        f" --s6: 2rem; --d-jobs: {DOMAINS['jobs']}; --d-grow: {DOMAINS['grow']};"
        f" --d-market: {DOMAINS['market']}; --d-system: {DOMAINS['system']}; }}"
    )
    fonts = (
        "@import url('https://fonts.googleapis.com/css2?family=Doto:wght@700;900&display=swap');"
    )
    return f"<style>{fonts}{variables}{_STYLE}{_MOTION}{_BLOCKS}{_WORKSPACE}{_PHONE}{_CALM}</style>"


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


def tip(text: str) -> str:
    """A small "?" that shows ``text`` when pointed at or focused (keyboard and touch too).

    Pure CSS, so it needs no script; the text is also its accessible label.
    """
    return (
        f'<span class="dw-tip" tabindex="0" role="note" aria-label="{escape(text)}" '
        f'data-tip="{escape(text)}">?</span>'
    )


def card_title(title: str, note: str = "") -> str:
    """A card's heading; its explanation is a "?" next to it, not a line of grey text."""
    mark = tip(note) if note else ""
    return f'<div class="dw-card-title">{escape(title)}{mark}</div>'


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
