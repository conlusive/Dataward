"""Keep the text of a "?" tip on the screen.

A tip (``dashboard_theme.tip``) opens to the right of its mark. Next to the right edge that ran past
the screen and made the whole page scroll sideways. This script measures the mark when it is
pointed at or focused and sets ``--dx`` (how far to shift the text to the left); the style reads it.
The text is at most 21 rem or 78% of the width wide, so that is what is measured: a little more
room than a short text needs, never less.
"""

from typing import Final

_SCRIPT: Final = """
() => {
  if (window.__dwTips) window.__dwTips();
  const place = (e) => {
    const tip = e.target.closest && e.target.closest('.dw-tip');
    if (!tip) return;
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const wide = Math.min(21 * rem, 0.78 * innerWidth);
    const left = tip.getBoundingClientRect().left;
    const over = left + wide - (innerWidth - 12);
    const shift = over > 0 ? -Math.min(over, left - 8) : 0;  // never past the left edge either
    tip.style.setProperty('--dx', `${shift}px`);
  };
  document.addEventListener('mouseover', place, true);
  document.addEventListener('focusin', place, true);
  window.__dwTips = () => {
    document.removeEventListener('mouseover', place, true);
    document.removeEventListener('focusin', place, true);
  };
}
"""


def script() -> str:
    """The code to inject once per page load; running it again replaces the earlier listeners."""
    return f"<script>({_SCRIPT})();</script>"
