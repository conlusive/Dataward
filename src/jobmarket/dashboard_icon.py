"""The tab icon, in a form every browser takes.

Streamlit's page already carries ``<link rel="shortcut icon" href="./favicon.png">`` (its own
logo) and swaps it for ``page_icon`` with a script, after the page has loaded, as a JPEG. Chrome
follows that swap; Safari reads the icon when the page loads and keeps what it found. So the
container image replaces Streamlit's own ``favicon.png`` and writes our links into the head
(``Dockerfile.dashboard``, ``dashboard_head.py``); this script keeps them there, and does the same
for a local run: it takes foreign links away, keeps ours and adds what is missing, from the static
folder the app serves (``enableStaticServing`` in ``.streamlit/config.toml``), with an
``apple-touch-icon`` too.
"""

import hashlib
from pathlib import Path
from typing import Final

from jobmarket import dashboard_logo as logo

STATIC_URL: Final = "/app/static"  # where Streamlit serves ``dashboard/static``

_SCRIPT: Final = """
(() => {
  if (window.__dwIcon) return;  // once per page load
  window.__dwIcon = true;
  const add = (rel, file, size) => {
    const link = document.createElement('link');
    link.rel = rel; link.type = 'image/png'; link.href = '%(base)s/' + file + '?v=%(version)s';
    if (size) link.sizes = size;
    link.dataset.dwIcon = '1';
    document.head.appendChild(link);
  };
  // an icon that points into the static folder is ours, whoever wrote the link (the head of the
  // page, see dashboard_head.py, or this script): it stays, so the tab never swaps it for another
  const ours = (link) => link.dataset.dwIcon
    || (link.getAttribute('href') || '').includes('/app/static/');
  const apply = () => {
    // anything that is not ours (Streamlit's own, or the one it adds again after a rerun) goes
    const foreign = 'link[rel~="icon"], link[rel~="shortcut"], link[rel="apple-touch-icon"]';
    document.head.querySelectorAll(foreign)
      .forEach((link) => { if (!ours(link)) link.remove(); });
    if (!document.head.querySelector('link[rel~="icon"]')) {
      add('icon', 'favicon.png', '%(icon)dx%(icon)d');
    }
    if (!document.head.querySelector('link[rel="apple-touch-icon"]')) {
      add('apple-touch-icon', 'apple-touch-icon.png', '%(apple)dx%(apple)d');
    }
  };
  apply();
  new MutationObserver(apply).observe(document.head, { childList: true });
})();
"""


def version(directory: Path = logo.STATIC) -> str:
    """A short hash of the icon, so a changed icon is a new address (browsers keep icons hard)."""
    return hashlib.sha1((directory / "favicon.png").read_bytes()).hexdigest()[:8]  # noqa: S324


def script() -> str:
    """The code to inject once per page load."""
    values = {
        "base": STATIC_URL,
        "version": version(),
        "apple": logo.APPLE_TOUCH_SIZE,
        "icon": logo.FAVICON_SIZE,
    }
    return f"<script>{_SCRIPT % values}</script>"
