"""The sidebar on a phone: a drawer that starts closed.

The app asks for an open sidebar (``initial_sidebar_state="expanded"``) because on a desktop the
menu is part of the layout. On a phone Streamlit shows it as a drawer over the page, and an open
drawer covers most of the screen. This script closes it once when the page loads on a narrow
screen; the menu button in the header opens it again (the stylesheet shows that button only on a
narrow screen).
"""

from typing import Final

# Streamlit's own breakpoint between a drawer and a fixed sidebar (theme.breakpoints.md)
PHONE_MAX_PX: Final = 768

_SCRIPT: Final = """
(() => {
  if (window.__dwDrawer) return;  // once per page load, not at every rerun
  window.__dwDrawer = true;
  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    const phone = matchMedia('(max-width: %(px)dpx)').matches;
    const close = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
    if (phone && close) { close.click(); clearInterval(timer); }
    else if (!phone || tries > 50) clearInterval(timer);  // wide screen, or the menu never came
  }, 100);
})();
"""


def script() -> str:
    """The code to inject once per page load."""
    return f"<script>{_SCRIPT % {'px': PHONE_MAX_PX}}</script>"
