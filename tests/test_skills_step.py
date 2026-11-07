from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.store import SilverStore
from jobmarket.skills.dictionary import DictionaryExtractor
from jobmarket.skills.dictionary_step import apply_dictionary_skills, load_taxonomy_into_silver
from jobmarket.skills.taxonomy import load_taxonomy

TAXONOMY = load_taxonomy()
EXTRACTOR = DictionaryExtractor(TAXONOMY)


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    return SilverStore(tmp_path / "test.duckdb")


def _add(silver: SilverStore, vid: str, title: str, description: str, source: str = "dou") -> None:
    silver.upsert(
        ParsedVacancy(
            id=vid,
            source=source,
            url=f"https://example.com/{vid.replace(':', '/')}",
            title=title,
            company="Acme",
            category=None,
            description_text=description,
        ),
        run_id="parse-1",
        loaded_at=datetime(2026, 11, 6),
        source_file="x.html",
        fetched_at=datetime(2026, 11, 6),
    )


def _skills(silver: SilverStore, vid: str) -> list[tuple[Any, ...]]:
    return silver._con.execute(
        "SELECT skill_id, importance, method, confidence FROM silver_vacancy_skills "
        "WHERE vacancy_id = ? ORDER BY skill_id",
        [vid],
    ).fetchall()


def test_taxonomy_is_copied_into_silver(silver: SilverStore) -> None:
    load_taxonomy_into_silver(silver, TAXONOMY)
    load_taxonomy_into_silver(silver, TAXONOMY)  # reloading replaces, never duplicates

    count = silver._con.execute("SELECT count(*) FROM silver_skills").fetchone()
    assert count == (len(TAXONOMY.skills),)
    parent = silver._con.execute(
        "SELECT parent_id FROM silver_skills WHERE skill_id = 'spring-boot'"
    ).fetchone()
    assert parent == ("spring",)


def test_skills_are_written_with_method_importance_and_confidence(silver: SilverStore) -> None:
    _add(silver, "dou:1", "Python Developer", "Requirements:\n- Django\nNice to have:\n- Kafka")

    stats = apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-1")

    assert _skills(silver, "dou:1") == [
        ("django", "required", "dictionary", 1.0),
        ("kafka", "nice", "dictionary", 1.0),
        ("python", "required", "dictionary", 1.0),
    ]
    assert (stats.vacancies, stats.with_skills, stats.skills) == (1, 1, 3)


def test_recomputing_is_stable_and_follows_a_changed_description(silver: SilverStore) -> None:
    _add(silver, "dou:2", "Dev", "Python and Docker")
    apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-1")
    first = _skills(silver, "dou:2")
    apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-2")
    assert _skills(silver, "dou:2") == first

    _add(silver, "dou:2", "Dev", "Only Kubernetes now")
    apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-3")

    assert [row[0] for row in _skills(silver, "dou:2")] == ["kubernetes"]


def test_one_source_does_not_touch_another_sources_skills(silver: SilverStore) -> None:
    _add(silver, "dou:3", "Dev", "Python")
    _add(silver, "djinni:3", "Dev", "Python", source="djinni")
    apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-1")
    apply_dictionary_skills(silver, EXTRACTOR, "djinni", run_id="parse-1")

    _add(silver, "dou:3", "Dev", "Java")
    apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-2")

    assert [row[0] for row in _skills(silver, "dou:3")] == ["java"]
    assert [row[0] for row in _skills(silver, "djinni:3")] == ["python"]


def test_a_vacancy_without_skills_is_counted_but_has_no_rows(silver: SilverStore) -> None:
    _add(silver, "dou:4", "Manager", "Be nice to people.")

    stats = apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-1")

    assert (stats.vacancies, stats.with_skills) == (1, 0) and _skills(silver, "dou:4") == []


def test_a_failing_insert_keeps_the_previous_skills(silver: SilverStore) -> None:
    _add(silver, "dou:5", "Dev", "Python")
    apply_dictionary_skills(silver, EXTRACTOR, "dou", run_id="parse-1")
    bad: list[Any] = [("dou:5", "java", None, 1.0)]  # importance is NOT NULL

    with pytest.raises(duckdb.Error):
        silver.replace_vacancy_skills(
            "dou", "dictionary", bad, run_id="parse-2", loaded_at=datetime(2026, 11, 7)
        )

    assert [row[0] for row in _skills(silver, "dou:5")] == ["python"]
