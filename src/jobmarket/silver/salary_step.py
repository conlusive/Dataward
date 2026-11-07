"""Fills salary_min/max/currency in silver_vacancies from the declared range or the description."""

from dataclasses import dataclass

from jobmarket.silver.salary import parse_salary
from jobmarket.silver.store import SilverStore


@dataclass
class SalaryStats:
    vacancies: int = 0
    declared: int = 0  # salary_raw came from the page's structured data
    from_text: int = 0  # found in the title or description next to a pay word
    without: int = 0


def apply_salaries(silver: SilverStore, source: str) -> SalaryStats:
    """Recompute the salary columns for every vacancy of ``source`` (deterministic, idempotent)."""
    stats = SalaryStats()
    updates: list[tuple[str, str | None, float | None, float | None, str | None]] = []
    for vacancy_id, title, description, raw in silver.salary_inputs(source):
        stats.vacancies += 1
        if raw:
            found = parse_salary(raw)
            stats.declared += found is not None
        else:
            found = parse_salary(f"{title}\n{description}", require_context=True)
            stats.from_text += found is not None
            raw = found.matched if found else None
        if found is None:
            stats.without += 1
        updates.append(
            (
                vacancy_id,
                raw,
                found.min if found else None,
                found.max if found else None,
                found.currency if found else None,
            )
        )
    silver.set_salaries(updates)
    return stats
