"""djinni.co vacancy page -> ParsedVacancy (structured fields come from the JobPosting JSON-LD)."""

import json
import re
from datetime import date
from typing import Any

from selectolax.lexbor import LexborHTMLParser

from jobmarket.silver.model import ParsedVacancy, ParseError
from jobmarket.silver.text import html_to_text

SOURCE = "djinni"
_EXTERNAL_ID = re.compile(r"/jobs/(\d+)-")


def vacancy_id(url: str) -> str | None:
    """ "djinni:857083" for a vacancy URL, None for any other URL."""
    match = _EXTERNAL_ID.search(url)
    return f"{SOURCE}:{match.group(1)}" if match else None


def _job_posting(tree: LexborHTMLParser) -> dict[str, Any] | None:
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def _salary_raw(base_salary: Any) -> str | None:
    """ "1700-1800 USD/MONTH": the employer-declared range in a form the salary parser can read."""
    if not isinstance(base_salary, dict):
        return None
    value = base_salary.get("value") or {}
    low, high = value.get("minValue"), value.get("maxValue")
    if low is None and high is None:
        return None
    amount = (
        f"{low}-{high}"
        if low is not None and high is not None
        else str(low if high is None else high)
    )
    unit = value.get("unitText")
    currency = base_salary.get("currency")
    return f"{amount} {currency}" + (f"/{unit}" if unit else "")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if isinstance(v, str)]
    return []


def _locations(posting: dict[str, Any]) -> list[str]:
    """Cities named in the vacancy, or its country when no city is given."""
    raw = posting.get("jobLocation") or []
    places = raw if isinstance(raw, list) else [raw]
    found: list[str] = []
    for place in places:
        address = place.get("address") if isinstance(place, dict) else None
        if not isinstance(address, dict):
            continue
        names = _as_list(address.get("addressLocality")) or _as_list(address.get("addressCountry"))
        found.extend(name for name in names if name not in found)
    return found


def parse_djinni_vacancy(html: str, url: str, *, fetched_on: date) -> ParsedVacancy:
    del fetched_on  # Djinni dates carry the year
    match = _EXTERNAL_ID.search(url)
    if match is None:
        raise ParseError(f"not a Djinni vacancy url: {url}")

    tree = LexborHTMLParser(html)
    posting = _job_posting(tree)
    description = tree.css_first(".job-post__description")
    if posting is None or description is None:
        raise ParseError(f"JobPosting or description missing: {url}")

    title = str(posting.get("title") or "").strip()
    organization = posting.get("hiringOrganization")
    if isinstance(organization, dict):
        company = str(organization.get("name") or "").strip()
    else:  # an employer who hides the name is the bare string "confidential"
        company = str(organization or "").strip()
    if not title or not company:
        raise ParseError(f"title or company missing: {url}")

    months = (posting.get("experienceRequirements") or {}).get("monthsOfExperience")
    posted = str(posting.get("datePosted") or "")[:10]
    if posting.get("jobLocationType") == "TELECOMMUTE":
        remote: bool | None = True
    else:
        remote = False if posting.get("jobLocation") else None

    return ParsedVacancy(
        id=f"{SOURCE}:{match.group(1)}",
        source=SOURCE,
        url=url,
        title=title,
        company=company,
        category=str(posting["category"]) if posting.get("category") else None,
        locations=_locations(posting),
        remote=remote,
        experience_years=round(float(months) / 12, 1) if months is not None else None,
        salary_raw=_salary_raw(posting.get("baseSalary")),
        published_at=date.fromisoformat(posted)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", posted)
        else None,
        description_text=html_to_text(description.html or ""),
    )
