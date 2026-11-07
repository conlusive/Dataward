from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.store import SilverStore
from jobmarket.silver.text_step import apply_text_signals


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    return SilverStore(tmp_path / "test.duckdb")


def _add(
    silver: SilverStore, vid: str, title: str, description: str, declared: float | None = None
) -> None:
    silver.upsert(
        ParsedVacancy(
            id=vid,
            source="dou",
            url=f"https://jobs.dou.ua/companies/x/vacancies/{vid.split(':')[1]}/",
            title=title,
            company="Acme",
            category=None,
            description_text=description,
            experience_years=declared,
        ),
        run_id="parse-1",
        loaded_at=datetime(2026, 11, 6),
        source_file="dou/f.html",
        fetched_at=datetime(2026, 11, 6),
    )


def _signals(silver: SilverStore, vid: str) -> tuple[object, ...]:
    return (
        silver._con.execute(
            "SELECT seniority, experience_years_text, english_level, experience_years "
            "FROM silver_vacancies WHERE id = ?",
            [vid],
        ).fetchone()
        or ()
    )


def test_all_three_signals_are_filled_and_declared_experience_is_untouched(
    silver: SilverStore,
) -> None:
    _add(
        silver,
        "dou:1",
        "Senior Python Developer",
        "5+ years of experience.\nEnglish: B2",
        declared=3.0,
    )

    stats = apply_text_signals(silver, "dou")

    assert _signals(silver, "dou:1") == ("senior", 5.0, "upper-intermediate", 3.0)
    assert (stats.vacancies, stats.seniority, stats.experience, stats.english) == (1, 1, 1, 1)


def test_signals_survive_a_reparse_and_follow_a_changed_description(silver: SilverStore) -> None:
    _add(silver, "dou:2", "Python Developer", "3+ years of experience. English C1")
    apply_text_signals(silver, "dou")
    first = _signals(silver, "dou:2")

    _add(silver, "dou:2", "Python Developer", "3+ years of experience. English C1")  # re-parse
    assert _signals(silver, "dou:2") == first  # not wiped by the parser upsert

    _add(silver, "dou:2", "Python Developer", "We will discuss the details.")  # description changed
    apply_text_signals(silver, "dou")

    assert _signals(silver, "dou:2") == (None, None, None, None)


def test_a_source_without_vacancies_is_a_no_op(silver: SilverStore) -> None:
    assert apply_text_signals(silver, "dou").vacancies == 0


def test_a_database_created_before_the_new_columns_is_migrated(tmp_path: Path) -> None:
    path = tmp_path / "old.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE silver_vacancies (id VARCHAR PRIMARY KEY, title VARCHAR)")
    con.execute("INSERT INTO silver_vacancies VALUES ('dou:9', 'Kept')")
    con.close()

    store = SilverStore(path)

    columns = {row[0] for row in store._con.execute("DESCRIBE silver_vacancies").fetchall()}
    assert {"experience_years_text", "seniority"} <= columns
    assert store._con.execute("SELECT title FROM silver_vacancies").fetchone() == ("Kept",)
