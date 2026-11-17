"""The head of the page, written into Streamlit's ``index.html`` when the image is built.

Streamlit serves one static page for every address and fills it in with JavaScript, so what a
browser tab, a search crawler or a link preview (Telegram, Slack) reads before any script runs is
Streamlit's own: the title "Streamlit", its crown as the icon, ``lang="en"``, no description.
This module writes ours into that file once, at ``docker build`` (``python -m
jobmarket.dashboard_head``): the title, the description, the language, the canonical address,
Open Graph and Twitter tags, a small JSON-LD description of the site, a ``<noscript>`` text for a
reader without JavaScript, and the icons at an address that carries a hash of the icon.

The icon matters most: Streamlit serves ``favicon.png`` as ``immutable`` for a year, so a browser
that once saw the crown at that address keeps it whatever the file now holds (Safari above all).
A new address is the only way to make it look again.
"""

import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Final

from jobmarket import dashboard_logo as logo

TITLE: Final = "Dataward · ринок праці в ІТ України"
DESCRIPTION: Final = (
    "Відкрита аналітика ринку праці в ІТ України: вакансії з DOU і Djinni, навички, стеки та "
    "зарплати. Дані оновлюються регулярно, кожна цифра має джерело."
)
DEFAULT_SITE_URL: Final = "https://dataward.onrender.com"
SITE_URL_ENV: Final = "DASHBOARD_SITE_URL"
STATIC_URL: Final = (
    "app/static"  # where Streamlit serves ``dashboard/static`` (relative to the page)
)
MARKER: Final = "<!-- dataward-head -->"
THEME_COLOUR: Final = "#0D1117"
PAGES: Final[tuple[tuple[str, str], ...]] = (
    ("Каталог вакансій", "catalog"),
    ("Ринок: скільки вакансій і куди", "market"),
    ("Навички: що вимагають", "skills"),
    ("Зарплати за ролями і рівнями", "salary"),
    ("Стан системи: свіжість і якість даних", "system"),
)


def icon_version(directory: Path = logo.STATIC) -> str:
    """A short hash of the icon: a changed icon is a new address, which a browser fetches again."""
    return hashlib.sha1((directory / "favicon.png").read_bytes()).hexdigest()[:8]  # noqa: S324


def _attr(value: str) -> str:
    return html.escape(value, quote=True)


def _head_tags(site_url: str, version: str) -> str:
    base = site_url.rstrip("/")
    icon = f"./{STATIC_URL}/favicon.png?v={version}"
    touch = f"./{STATIC_URL}/apple-touch-icon.png?v={version}"
    image = f"{base}/{STATIC_URL}/favicon.png?v={version}"
    site = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "Dataward",
        "url": base + "/",
        "description": DESCRIPTION,
        "inLanguage": "uk",
        "applicationCategory": "BusinessApplication",
        "isAccessibleForFree": True,
    }
    # "</" inside a script would end it: JSON never needs it, but be sure
    ld = json.dumps(site, ensure_ascii=False).replace("</", "<\\/")
    tags = [
        MARKER,
        f'<meta name="description" content="{_attr(DESCRIPTION)}" />',
        f'<meta name="theme-color" content="{THEME_COLOUR}" />',
        f'<link rel="canonical" href="{_attr(base)}/" />',
        f'<link rel="icon" type="image/png" sizes="{logo.FAVICON_SIZE}x{logo.FAVICON_SIZE}" '
        f'href="{icon}" />',
        f'<link rel="apple-touch-icon" sizes="{logo.APPLE_TOUCH_SIZE}x{logo.APPLE_TOUCH_SIZE}" '
        f'href="{touch}" />',
        '<meta property="og:type" content="website" />',
        '<meta property="og:locale" content="uk_UA" />',
        '<meta property="og:site_name" content="Dataward" />',
        f'<meta property="og:title" content="{_attr(TITLE)}" />',
        f'<meta property="og:description" content="{_attr(DESCRIPTION)}" />',
        f'<meta property="og:url" content="{_attr(base)}/" />',
        f'<meta property="og:image" content="{_attr(image)}" />',
        '<meta name="twitter:card" content="summary" />',
        f'<meta name="twitter:title" content="{_attr(TITLE)}" />',
        f'<meta name="twitter:description" content="{_attr(DESCRIPTION)}" />',
        f'<script type="application/ld+json">{ld}</script>',
    ]
    return "\n    ".join(tags)


def _noscript(site_url: str) -> str:
    base = site_url.rstrip("/")
    items = "".join(
        f'<li><a href="{_attr(base)}/{path}">{html.escape(label)}</a></li>' for label, path in PAGES
    )
    return (
        "<noscript><h1>Dataward</h1>"
        f"<p>{html.escape(DESCRIPTION)}</p>"
        f"<ul>{items}</ul>"
        "<p>Щоб побачити графіки й таблиці, увімкніть JavaScript.</p></noscript>"
    )


def patch(page: str, *, site_url: str = DEFAULT_SITE_URL, version: str | None = None) -> str:
    """Streamlit's ``index.html`` with our head; a page that already has it is returned as is."""
    if MARKER in page:
        return page
    version = version or icon_version()
    out = re.sub(r'<html lang="[^"]*"', '<html lang="uk"', page, count=1)
    # Streamlit's own icon link goes: ours is added below, at an address with a hash
    out = re.sub(r'\s*<link rel="shortcut icon"[^>]*/>', "", out, count=1)
    out = re.sub(
        r"<title>.*?</title>", f"<title>{html.escape(TITLE)}</title>", out, count=1, flags=re.S
    )
    out = re.sub(
        r"<noscript>.*?</noscript>", lambda _: _noscript(site_url), out, count=1, flags=re.S
    )
    return out.replace("</title>", "</title>\n    " + _head_tags(site_url, version), 1)


def streamlit_index() -> Path:
    import streamlit

    return Path(streamlit.__file__).parent / "static" / "index.html"


def main() -> int:
    """Rewrite Streamlit's ``index.html`` in place (the image build runs this once)."""
    path = streamlit_index()
    page = path.read_text(encoding="utf-8")
    patched = patch(page, site_url=os.environ.get(SITE_URL_ENV) or DEFAULT_SITE_URL)
    if patched == page:
        print(f"{path}: already patched")
        return 0
    path.write_text(patched, encoding="utf-8")
    print(f"{path}: patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
