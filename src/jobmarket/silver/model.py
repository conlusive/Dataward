"""The parsed vacancy as it enters silver; one shape for every source."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date


class ParseError(Exception):
    """A bronze page that does not look like a vacancy page (markup changed or wrong page)."""


@dataclass(frozen=True)
class ParsedVacancy:
    id: str  # "{source}:{external_id}"
    source: str
    url: str
    title: str
    company: str
    category: str | None
    locations: list[str] = field(default_factory=list)
    remote: bool | None = None
    experience_years: float | None = None
    salary_raw: str | None = None
    published_at: date | None = None
    description_text: str = ""

    @property
    def content_hash(self) -> str:
        return text_hash(self.description_text)


def normalize_text(text: str) -> str:
    """Whitespace-collapsed, case-folded text: the same description hashes the same."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip().casefold()


def text_hash(text: str) -> str:
    return hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()
