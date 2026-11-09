"""Running the same date twice gives the same data (silver and gold), not twice the data."""

import hashlib
from datetime import date
from pathlib import Path

import duckdb
import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.silver.pipeline import run_parse
from tests.helpers import sample
from tests.test_dbt_lifecycle import DBT, _dbt
from tests.test_pipeline import (
    DJINNI_LIST,
    DJINNI_VACANCY,
    _dou_day,
    _put,
)

DAY = date(2026, 11, 2)
MARTS = (
    "fct_vacancy_daily",
    "dim_skill",
    "fct_skill_demand_monthly",
    "fct_skill_pairs",
    "fct_salary_by_skill",
    "fct_salary_survey",
    "fct_vacancy_lifetime",
    "fct_market_daily",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    store = BronzeStore(tmp_path / "bronze")
    for day in (date(2026, 11, 1), DAY):
        _dou_day(store, day)
        _put(store, "djinni", day, DJINNI_LIST, sample("djinni/list_python.html"))
        _put(store, "djinni", day, DJINNI_VACANCY, sample("djinni/detail.html"))
    return Settings(bronze_dir=tmp_path / "bronze", duckdb_path=tmp_path / "test.duckdb")


def _fingerprints(db: Path, tables: tuple[str, ...] | None = None) -> dict[str, tuple[int, str]]:
    """(row count, hash of the content) per table, ignoring run bookkeeping columns (`_*`)."""
    con = duckdb.connect(str(db), read_only=True)
    try:
        if tables is None:
            tables = tuple(
                r[0]
                for r in con.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main' AND table_name LIKE 'silver_%' "
                    "AND table_name <> 'silver_vacancies_history' ORDER BY 1"
                ).fetchall()
            )
        result: dict[str, tuple[int, str]] = {}
        for table in tables:
            columns = [
                r[0]
                for r in con.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'main' AND table_name = ? "
                    "AND column_name NOT LIKE '\\_%' ESCAPE '\\' ORDER BY ordinal_position",
                    [table],
                ).fetchall()
            ]
            listed = ", ".join(f'"{c}"' for c in columns)
            rows = con.execute(f"SELECT {listed} FROM {table} ORDER BY {listed}").fetchall()
            digest = hashlib.sha256(repr(rows).encode()).hexdigest()
            result[table] = (len(rows), digest)
        return result
    finally:
        con.close()


def test_parsing_the_same_date_twice_leaves_silver_unchanged(settings: Settings) -> None:
    run_parse(settings, ["dou", "djinni"], DAY)
    first = _fingerprints(settings.duckdb_path)

    run_parse(settings, ["dou", "djinni"], DAY)
    second = _fingerprints(settings.duckdb_path)

    assert first["silver_vacancies"][0] >= 2  # something real was compared, not empty tables
    assert first["silver_vacancy_sightings"][0] > 0
    assert second == first


def test_parsing_all_stored_days_twice_leaves_silver_unchanged(settings: Settings) -> None:
    run_parse(settings, ["dou", "djinni"], DAY, missing=True)
    first = _fingerprints(settings.duckdb_path)

    run_parse(settings, ["dou", "djinni"], DAY)  # the newest day again, outside the catch-up
    run_parse(settings, ["dou", "djinni"], date(2026, 11, 1))  # and the oldest, out of order

    assert _fingerprints(settings.duckdb_path) == first


@pytest.mark.skipif(not DBT.exists(), reason="dbt is not installed")
def test_building_gold_twice_gives_the_same_marts_and_no_new_history(settings: Settings) -> None:
    run_parse(settings, ["dou", "djinni"], DAY, missing=True)
    db = settings.duckdb_path

    _dbt(db, "snapshot")
    _dbt(db, "build")
    marts = _fingerprints(db, MARTS)
    history = _fingerprints(db, ("silver_vacancies_history",))

    run_parse(settings, ["dou", "djinni"], DAY)  # the same date again, then the dbt layer again
    _dbt(db, "snapshot")
    _dbt(db, "build")

    assert marts["fct_vacancy_daily"][0] > 0
    assert _fingerprints(db, MARTS) == marts
    assert _fingerprints(db, ("silver_vacancies_history",)) == history


def test_the_fingerprint_notices_a_changed_value_and_a_rerun_repairs_it(settings: Settings) -> None:
    run_parse(settings, ["dou", "djinni"], DAY)
    clean = _fingerprints(settings.duckdb_path)
    con = duckdb.connect(str(settings.duckdb_path))
    con.execute("UPDATE silver_vacancies SET title = 'tampered' WHERE id = 'dou:359220'")
    con.close()

    assert _fingerprints(settings.duckdb_path) != clean

    run_parse(settings, ["dou", "djinni"], DAY)

    assert _fingerprints(settings.duckdb_path) == clean
