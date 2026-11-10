"""Page-enter motion: a page is hidden while it is built and shown at once, with one soft fade.

Streamlit streams a page element by element and keeps the old one on screen until the new script
has run. Animating each element (rising, staggered) made that building visible and read as jumping.
The stylesheet therefore hides the page body from the start, until ``html.dw-go`` is set. This
script takes ``dw-go`` away when the address changes, waits until the run has finished (the app's
own script state), then sets it again: the body is shown with a single opacity fade and the small
one-off animations start (``html.dw-enter``: the typed line, the growing meters). A rerun on the
same page changes nothing: no hold, no replay.
"""

import json
from typing import Final

ENTER_MS: Final = (
    2800  # long enough for the slowest arrival (the typed line), short enough to be over
)
MIN_HOLD_MS: Final = 250  # the run has not even been marked busy yet before this
MAX_HOLD_MS: Final = 1600  # never keep the page hidden longer, whatever the run is doing

_SCRIPT: Final = """
(cfg) => {
  if (window.__dwMotion) window.__dwMotion();
  const root = document.documentElement;
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let poll = null;
  // the app says itself whether a script is running; stale elements and the "running" widget are
  // a second opinion (the old page can be gone and the widget not shown while the new one builds)
  const busy = () => {
    const app = document.querySelector('[data-testid="stApp"]');
    const state = app ? app.getAttribute('data-test-script-state') : null;
    if (state && state !== 'notRunning') return true;
    return !!document.querySelector('[data-stale="true"], [data-testid="stStatusWidget"]');
  };
  const reveal = () => {
    clearInterval(poll);
    root.classList.add('dw-go');
    root.classList.add('dw-enter');
    clearTimeout(window.__dwEnter);
    window.__dwEnter = setTimeout(() => root.classList.remove('dw-enter'), cfg.ms);
  };
  // show the page once the run is over (nothing stale, no "running" widget) on two checks in a row
  const settle = () => {
    clearInterval(poll);
    const started = Date.now();
    let still = 0;
    poll = setInterval(() => {
      const age = Date.now() - started;
      still = busy() ? 0 : still + 1;
      if (age > cfg.cap || (age >= cfg.min && still >= 2)) reveal();
    }, 100);
  };
  // a second run of this script on the same page (a rerun) must not start the arrival again
  const begin = () => {
    if (window.__dwPath === location.pathname) return;
    window.__dwPath = location.pathname;
    if (!calm) root.classList.remove('dw-go');
    settle();
  };
  // Streamlit changes the address with pushState: catch it at once, before the new page arrives
  if (!history.__dwWrapped) {
    const original = history.pushState;
    history.pushState = function () {
      const result = original.apply(this, arguments);
      if (window.__dwNav) window.__dwNav();
      return result;
    };
    history.__dwWrapped = true;
  }
  window.__dwNav = begin;
  begin();
  if (!root.classList.contains('dw-go') && !poll) settle();  // a rerun in the middle of a hold
  const watch = setInterval(begin, 200);  // back and forward buttons, links the wrapper missed
  window.__dwMotion = () => { clearInterval(poll); clearInterval(watch); window.__dwNav = null; };
}
"""


def script() -> str:
    """The code to inject once per page load."""
    data = json.dumps({"ms": ENTER_MS, "min": MIN_HOLD_MS, "cap": MAX_HOLD_MS})
    return f"<script>({_SCRIPT})({data});</script>"
