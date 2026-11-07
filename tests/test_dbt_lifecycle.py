"""Runs the real dbt project (warehouse/) on a small made-up history and checks every day."""

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.store import SilverStore

WAREHOUSE = Path(__file__).parent.parent / "warehouse"
DBT = Path(sys.executable).parent / "dbt"

pytestmark = pytest.mark.skipif(not DBT.exists(), reason="dbt is not installed")


def _dbt(db: Path, *args: str) -> None:
    result = subprocess.run(
        [str(DBT), *args, "--project-dir", str(WAREHOUSE), "--profiles-dir", str(WAREHOUSE)],
        capture_output=True,
        text=True,
        env={
            "DUCKDB_PATH": str(db),
            "PATH": str(DBT.parent),
            "DBT_TARGET_PATH": str(db.parent / "target"),
        },
        cwd=str(db.parent),
    )
    assert result.returncode == 0, result.stdout[-2500:] + result.stderr[-1000:]


def _vacancy(store: SilverStore, vid: str, title: str = "Python Developer") -> None:
    store.upsert(
        ParsedVacancy(
            id=vid,
            source=vid.split(":")[0],
            url=f"https://example.com/{vid.replace(':', '/')}",
            title=title,
            company="Acme",
            category=None,
            description_text="Same text",
        ),
        run_id="r1",
        loaded_at=datetime(2026, 11, 1),
        source_file="x",
        fetched_at=datetime(2026, 11, 1),
    )


def _days(*days: int) -> list[date]:
    return [date(2026, 11, d) for d in days]


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.duckdb"
    store = SilverStore(path)
    listed = {
        "dou:1": _days(1, 2, 3, 4, 5, 6, 7),  # listed every day
        "dou:2": _days(2, 3),  # listed twice, then gone
        "dou:3": _days(1, 2, 4, 5),  # misses one day, comes back
        "dou:4": _days(2, 6),  # gone for a few days, then listed again
        "djinni:5": _days(7),  # first seen on the last day
    }
    for vid, days in listed.items():
        _vacancy(store, vid)
        for day in days:
            store.add_sightings([vid], day)
    store.close()
    return path


def _fact(db: Path) -> dict[str, list[tuple[int, str, int, bool]]]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute(
            "SELECT vacancy_id, date, status, lifetime_days, left_censored FROM fct_vacancy_daily "
            "ORDER BY vacancy_id, date"
        ).fetchall()
    finally:
        con.close()
    result: dict[str, list[tuple[int, str, int, bool]]] = {}
    for vacancy_id, day, status, lifetime, censored in rows:
        result.setdefault(vacancy_id, []).append((day.day, status, lifetime, censored))
    return result


def test_each_vacancy_follows_the_lifecycle_rules(db: Path) -> None:
    _dbt(db, "build")

    fact = _fact(db)
    # listed all week: new, then active, lifetime grows; first seen on day one, so left-censored
    assert fact["dou:1"] == [(d, "new" if d == 1 else "active", d, True) for d in range(1, 8)]
    # listed on days 2-3: one missed day is tolerated, the second one closes it, nothing after
    assert fact["dou:2"] == [
        (2, "new", 1, False),
        (3, "active", 2, False),
        (4, "active", 2, False),
        (5, "closed", 2, False),
    ]
    # a single missed day (day 3) never closes the vacancy
    assert fact["dou:3"] == [
        (1, "new", 1, True),
        (2, "active", 2, True),
        (3, "active", 2, True),
        (4, "active", 4, True),
        (5, "active", 5, True),
        (6, "active", 5, True),
        (7, "closed", 5, True),
    ]
    # closed on day 4, silent on day 5, listed again on day 6: active again, lifetime spans the gap
    assert fact["dou:4"] == [
        (2, "new", 1, False),
        (3, "active", 1, False),
        (4, "closed", 1, False),
        (6, "active", 5, False),
        (7, "active", 5, False),
    ]
    # first seen on the last day: new, and not left-censored
    assert fact["djinni:5"] == [(7, "new", 1, False)]


def test_a_changed_vacancy_gets_a_new_version_and_an_unchanged_one_does_not(db: Path) -> None:
    _dbt(db, "snapshot")
    store = SilverStore(db)
    _vacancy(store, "dou:1", title="Senior Python Developer")  # the title changed
    store.close()

    _dbt(db, "snapshot")
    _dbt(db, "snapshot")  # a third run with no change adds nothing

    con = duckdb.connect(str(db), read_only=True)
    try:
        history = con.execute(
            "SELECT id, title, dbt_valid_to IS NULL AS is_current FROM silver_vacancies_history "
            "ORDER BY id, dbt_valid_from"
        ).fetchall()
    finally:
        con.close()
    changed = [row for row in history if row[0] == "dou:1"]
    assert [(title, current) for _, title, current in changed] == [
        ("Python Developer", False),
        ("Senior Python Developer", True),
    ]
    assert len([row for row in history if row[0] == "dou:2"]) == 1
