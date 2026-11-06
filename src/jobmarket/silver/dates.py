"""Dates as printed by jobs.dou.ua: "30 жовтня 2026" or "30 жовтня" (current year implied)."""

import re
from datetime import date

_MONTHS = {
    "січня": 1,
    "лютого": 2,
    "березня": 3,
    "квітня": 4,
    "травня": 5,
    "червня": 6,
    "липня": 7,
    "серпня": 8,
    "вересня": 9,
    "жовтня": 10,
    "листопада": 11,
    "грудня": 12,
}
_PATTERN = re.compile(r"(\d{1,2})\s+([а-яіїєґ]+)(?:\s+(\d{4}))?", re.IGNORECASE)


def parse_ua_date(text: str, *, today: date) -> date | None:
    """Parse a Ukrainian date; without a year take the latest such date not after ``today``."""
    match = _PATTERN.search(text.strip())
    if match is None:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    day = int(match.group(1))
    try:
        if match.group(3):
            return date(int(match.group(3)), month, day)
        candidate = date(today.year, month, day)
    except ValueError:
        return None
    return candidate if candidate <= today else date(today.year - 1, month, day)
