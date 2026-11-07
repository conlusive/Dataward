"""Fills seniority, experience_years_text and english_level from the title and description."""

from dataclasses import dataclass

from jobmarket.silver.store import SilverStore
from jobmarket.silver.text_signals import (
    parse_english_level,
    parse_required_experience,
    parse_seniority,
)


@dataclass
class TextStats:
    vacancies: int = 0
    seniority: int = 0
    experience: int = 0
    english: int = 0


def apply_text_signals(silver: SilverStore, source: str) -> TextStats:
    """Recompute the three columns for every vacancy of ``source`` (deterministic, idempotent)."""
    stats = TextStats()
    updates: list[tuple[str, str | None, float | None, str | None]] = []
    for vacancy_id, title, description in silver.text_inputs(source):
        seniority = parse_seniority(title)
        experience = parse_required_experience(description)
        english = parse_english_level(description)
        stats.vacancies += 1
        stats.seniority += seniority is not None
        stats.experience += experience is not None
        stats.english += english is not None
        updates.append((vacancy_id, seniority, experience, english))
    silver.set_text_signals(updates)
    return stats
