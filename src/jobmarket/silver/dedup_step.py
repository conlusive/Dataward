"""Groups duplicate vacancies in silver and records the groups."""

from dataclasses import dataclass
from datetime import UTC, datetime

from jobmarket.silver.dedup import group_vacancies
from jobmarket.silver.store import SilverStore


@dataclass
class DedupStats:
    vacancies: int = 0
    groups: int = 0
    merged_groups: int = 0  # groups of two or more vacancies
    duplicates: int = 0  # vacancies that are not the canonical member of their group
    largest_group: int = 0


def apply_dedup(silver: SilverStore, *, run_id: str) -> DedupStats:
    """Recompute all groups over every vacancy of every source (deterministic, idempotent)."""
    vacancies = silver.dedup_inputs()
    groups = group_vacancies(vacancies)
    silver.replace_groups(groups, run_id=run_id, loaded_at=datetime.now(UTC).replace(tzinfo=None))
    sizes = [len(g.members) for g in groups]
    return DedupStats(
        vacancies=len(vacancies),
        groups=len(groups),
        merged_groups=sum(size > 1 for size in sizes),
        duplicates=len(vacancies) - len(groups),
        largest_group=max(sizes, default=0),
    )
