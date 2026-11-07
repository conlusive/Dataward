"""jobs.dou.ua vacancy page -> ParsedVacancy."""

import re
from datetime import date

from selectolax.lexbor import LexborHTMLParser

from jobmarket.silver.dates import parse_ua_date
from jobmarket.silver.model import ParsedVacancy, ParseError
from jobmarket.silver.text import html_to_text

SOURCE = "dou"
_EXTERNAL_ID = re.compile(r"/vacancies/(\d+)/")
_REMOTE_WORD = "віддалено"


def _text(node: object) -> str:
    return node.text(separator=" ", strip=True) if node is not None else ""  # type: ignore[attr-defined]


def parse_dou_vacancy(html: str, url: str, *, fetched_on: date) -> ParsedVacancy:
    match = _EXTERNAL_ID.search(url)
    if match is None:
        raise ParseError(f"not a DOU vacancy url: {url}")

    tree = LexborHTMLParser(html)
    title = _text(tree.css_first("h1.g-h2"))
    description = tree.css_first(".b-typo.vacancy-section")
    if not title or description is None:
        raise ParseError(f"title or description missing: {url}")

    company_link = tree.css_first(".b-compinfo .l-n a") or tree.css_first("a.company")
    company = _text(company_link)
    if not company:
        raise ParseError(f"company missing: {url}")

    category_link = tree.css_first('a[href*="category="]')
    place = _text(tree.css_first(".sh-info .place") or tree.css_first(".place"))
    cities = [part.strip() for part in place.split(",") if part.strip()]

    return ParsedVacancy(
        id=f"{SOURCE}:{match.group(1)}",
        source=SOURCE,
        url=url,
        title=title,
        company=company,
        category=_text(category_link) or None,
        locations=[city for city in cities if _REMOTE_WORD not in city.lower()],
        remote=_REMOTE_WORD in place.lower() if place else None,
        published_at=parse_ua_date(_text(tree.css_first(".l-vacancy .date")), today=fetched_on),
        description_text=html_to_text(description.html or ""),
    )
