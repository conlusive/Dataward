"""Page-enter motion: things arrive once when a page opens, and never again until the next page.

Streamlit redraws the page after every click, so an animation tied to an element would replay each
time and read as lag. Instead the stylesheet animates only under ``html.dw-enter``, and this small
script switches that class on for a moment whenever the address changes (and on the first load).
"""

import json
from typing import Final

ENTER_MS: Final = (
    2800  # long enough for the slowest arrival (the typed line), short enough to be over
)

_SCRIPT: Final = """
(cfg) => {
  if (window.__dwMotion) window.__dwMotion();
  const root = document.documentElement;
  let timer = null;
  const enter = () => {
    root.classList.add('dw-enter');
    clearTimeout(timer);
    timer = setTimeout(() => root.classList.remove('dw-enter'), cfg.ms);
  };
  // a second run of this script on the same page (a rerun) must not start the arrival again
  const watch = () => {
    if (window.__dwPath !== location.pathname) { window.__dwPath = location.pathname; enter(); }
  };
  watch();
  const id = setInterval(watch, 150);
  window.__dwMotion = () => { clearInterval(id); clearTimeout(timer); };
}
"""


def script() -> str:
    """The code to inject once per page load."""
    data = json.dumps({"ms": ENTER_MS})
    return f"<script>({_SCRIPT})({data});</script>"
