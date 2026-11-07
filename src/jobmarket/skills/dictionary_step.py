"""Method A over silver: writes dictionary skills into silver_vacancy_skills."""

from dataclasses import dataclass
from datetime import UTC, datetime

from jobmarket.silver.store import SilverStore
from jobmarket.skills.dictionary import DictionaryExtractor
from jobmarket.skills.taxonomy import Taxonomy

METHOD = "dictionary"


@dataclass
class SkillStats:
    vacancies: int = 0
    with_skills: int = 0
    skills: int = 0


def load_taxonomy_into_silver(silver: SilverStore, taxonomy: Taxonomy) -> None:
    silver.replace_skills([(s.id, s.name, s.category, s.parent) for s in taxonomy.skills.values()])


def apply_dictionary_skills(
    silver: SilverStore, extractor: DictionaryExtractor, source: str, *, run_id: str
) -> SkillStats:
    """Recompute dictionary skills for every vacancy of ``source`` (deterministic, idempotent)."""
    stats = SkillStats()
    rows: list[tuple[str, str, str, float]] = []
    for vacancy_id, title, description in silver.text_inputs(source):
        found = extractor.extract(title, description)
        stats.vacancies += 1
        stats.with_skills += bool(found)
        stats.skills += len(found)
        rows.extend((vacancy_id, f.skill_id, f.importance, f.confidence) for f in found.values())
    silver.replace_vacancy_skills(
        source, METHOD, rows, run_id=run_id, loaded_at=datetime.now(UTC).replace(tzinfo=None)
    )
    return stats
