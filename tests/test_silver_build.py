import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.ops import OpsStore
from jobmarket.silver.build import parse_source
from jobmarket.silver.store import SilverStore
from tests.helpers import sample

RUN_DATE = date(2026, 11, 6)
VACANCY = "https://jobs.dou.ua/companies/solid-software/vacancies/359220/"
OTHER = "https://jobs.dou.ua/companies/eleks/vacancies/378180/"


def _put(
    store: BronzeStore,
    url: str,
    content: bytes,
    *,
    status: int = 200,
    redirected: bool = False,
    fetched_at: datetime = datetime(2026, 11, 6, 8, tzinfo=UTC),
    run_date: date = RUN_DATE,
) -> None:
    store.write(
        source="dou",
        run_date=run_date,
        url=url,
        content=content,
        status=status,
        run_id="r1",
        fetched_at=fetched_at,
        redirected=redirected,
    )


@pytest.fixture
def bronze(tmp_path: Path) -> BronzeStore:
    return BronzeStore(tmp_path / "bronze")


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    return SilverStore(tmp_path / "test.duckdb")


def _rows(tmp_path: Path, sql: str) -> list[tuple[object, ...]]:
    con = duckdb.connect(str(tmp_path / "test.duckdb"), read_only=False)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_only_usable_vacancy_pages_become_rows(
    tmp_path: Path, bronze: BronzeStore, silver: SilverStore
) -> None:
    _put(bronze, VACANCY, sample("dou/detail.html"))
    _put(bronze, OTHER, sample("dou/detail_cities.html"))
    _put(bronze, "https://jobs.dou.ua/vacancies/?category=Python", sample("dou/list_python.html"))
    _put(bronze, "https://jobs.dou.ua/companies/a/vacancies/1/", b"x", status=403)
    _put(bronze, "https://jobs.dou.ua/companies/a/vacancies/2/", b"x", redirected=True)
    _put(bronze, "https://jobs.dou.ua/companies/a/vacancies/3/", b"<html>new markup</html>")

    stats = parse_source("dou", RUN_DATE, bronze=bronze, silver=silver, run_id="parse-1")

    assert (stats.pages, stats.parsed, stats.failed, stats.unusable) == (5, 2, 1, 2)
    silver.close()
    assert _rows(tmp_path, "SELECT id FROM silver_vacancies ORDER BY id") == [
        ("dou:359220",),
        ("dou:378180",),
    ]


def test_service_columns_trace_back_to_bronze(
    tmp_path: Path, bronze: BronzeStore, silver: SilverStore
) -> None:
    _put(bronze, VACANCY, sample("dou/detail.html"))

    parse_source("dou", RUN_DATE, bronze=bronze, silver=silver, run_id="parse-1")

    silver.close()
    run_id, source_file, fetched_at, content_hash = _rows(
        tmp_path,
        "SELECT _run_id, _source_file, _fetched_at, content_hash FROM silver_vacancies",
    )[0]
    assert run_id == "parse-1"
    meta = json.loads(
        next((tmp_path / "bronze" / "dou" / "dt=2026-11-06").glob("*.meta.json")).read_text()
    )
    assert source_file == f"dou/dt=2026-11-06/{meta['file']}"
    assert fetched_at == datetime(2026, 11, 6, 8)
    assert isinstance(content_hash, str) and len(content_hash) == 40


def test_parsing_twice_gives_the_same_table(
    tmp_path: Path, bronze: BronzeStore, silver: SilverStore
) -> None:
    _put(bronze, VACANCY, sample("dou/detail.html"))
    _put(bronze, OTHER, sample("dou/detail_cities.html"))

    parse_source("dou", RUN_DATE, bronze=bronze, silver=silver, run_id="parse-1")
    first = silver._con.execute(
        "SELECT * EXCLUDE (_run_id, _loaded_at) FROM silver_vacancies ORDER BY id"
    ).fetchall()
    parse_source("dou", RUN_DATE, bronze=bronze, silver=silver, run_id="parse-2")
    second = silver._con.execute(
        "SELECT * EXCLUDE (_run_id, _loaded_at) FROM silver_vacancies ORDER BY id"
    ).fetchall()

    assert first == second and len(first) == 2


def test_backfill_of_an_older_date_does_not_overwrite_newer_data(
    tmp_path: Path, bronze: BronzeStore, silver: SilverStore
) -> None:
    newer, older = date(2026, 11, 7), date(2026, 11, 5)
    changed = sample("dou/detail.html").replace(
        b"Senior Python Developer", b"Principal Python Developer"
    )
    _put(bronze, VACANCY, changed, run_date=newer, fetched_at=datetime(2026, 11, 7, 8, tzinfo=UTC))
    _put(
        bronze,
        VACANCY,
        sample("dou/detail.html"),
        run_date=older,
        fetched_at=datetime(2026, 11, 5, 8, tzinfo=UTC),
    )

    parse_source("dou", newer, bronze=bronze, silver=silver, run_id="parse-new")
    parse_source("dou", older, bronze=bronze, silver=silver, run_id="parse-old")

    title = silver._con.execute("SELECT title FROM silver_vacancies").fetchone()
    assert title is not None and title[0].startswith("Principal")


def test_columns_owned_by_later_steps_survive_a_reparse(
    bronze: BronzeStore, silver: SilverStore
) -> None:
    _put(bronze, VACANCY, sample("dou/detail.html"))
    parse_source("dou", RUN_DATE, bronze=bronze, silver=silver, run_id="parse-1")
    silver._con.execute("UPDATE silver_vacancies SET salary_min = 1000, dedup_group_id = 'g1'")

    parse_source("dou", RUN_DATE, bronze=bronze, silver=silver, run_id="parse-2")

    assert silver._con.execute(
        "SELECT salary_min, dedup_group_id FROM silver_vacancies"
    ).fetchone() == (1000.0, "g1")


def test_task_runs_count_attempts(tmp_path: Path) -> None:
    ops = OpsStore(tmp_path / "ops.duckdb")

    first = ops.start_task("parse", "dou", RUN_DATE)
    ops.finish_task(first, "success", rows_in=3, rows_out=3, rows_failed=0)
    second = ops.start_task("parse", "dou", RUN_DATE)

    assert (first, second) == ("parse-dou-2026-11-06-1", "parse-dou-2026-11-06-2")
    ops.close()
