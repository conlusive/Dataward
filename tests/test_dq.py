from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from jobmarket.cli import main
from jobmarket.dq import CheckResult, run_checks
from jobmarket.ops import OpsStore
from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.store import SilverStore

NOW = datetime(2026, 11, 9, 12, 0)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.duckdb"
    SilverStore(path).close()
    OpsStore(path).close()
    return path


def _add(
    db: Path,
    vid: str,
    *,
    fetched: datetime = NOW - timedelta(hours=1),
    salary_raw: str | None = None,
) -> None:
    store = SilverStore(db)
    store.upsert(
        ParsedVacancy(
            id=vid, source=vid.split(":")[0], url=f"https://example.com/{vid}", title="Dev",
            company="Acme", category=None, salary_raw=salary_raw, description_text=f"t {vid}",
        ),
        run_id="r", loaded_at=NOW, source_file="f", fetched_at=fetched,
    )  # fmt: skip
    store.close()


def _sql(db: Path, sql: str, params: list[object] | None = None) -> None:
    con = duckdb.connect(str(db))
    con.execute(sql, params or [])
    con.close()


def _check(db: Path, name: str) -> CheckResult:
    return {r.name: r for r in run_checks(db, now=NOW)}[name]


def _skills(db: Path, with_skill: int, total: int) -> None:
    _sql(db, "INSERT INTO silver_skills VALUES ('python', 'Python', 'language', NULL)")
    for i in range(total):
        _add(db, f"dou:{i}")
    for i in range(with_skill):
        _sql(
            db,
            "INSERT INTO silver_vacancy_skills VALUES (?, 'python', 'required', 'dictionary', "
            "1.0, NULL, NULL, 'r', ?)",
            [f"dou:{i}", NOW],
        )


# ---- freshness -------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("age_hours", "status"),
    [(1, "pass"), (29.9, "pass"), (30, "warn"), (35.9, "warn"), (36, "error")],
)
def test_data_older_than_the_limits_warns_then_fails(
    db: Path, age_hours: float, status: str
) -> None:
    _add(db, "dou:1", fetched=NOW - timedelta(hours=age_hours))

    assert _check(db, "fresh_data").status == status


def test_an_empty_silver_is_an_error_not_a_pass(db: Path) -> None:
    assert _check(db, "fresh_data").status == "error"


# ---- listing volume --------------------------------------------------------------------------
def _listings(db: Path, per_day: list[int]) -> None:
    store = SilverStore(db)
    for day, count in enumerate(per_day, start=1):
        store.add_sightings([f"dou:{i}" for i in range(count)], date(2026, 11, day))
    store.close()


@pytest.mark.parametrize(
    ("latest", "status"), [(100, "pass"), (61, "pass"), (60, "warn"), (31, "warn"), (30, "error")]
)
def test_a_drop_in_listed_vacancies_is_measured_against_the_days_before(
    db: Path, latest: int, status: str
) -> None:
    _listings(db, [100, 100, 100, 100, latest])

    assert _check(db, "listing_volume").status == status


def test_too_little_history_skips_the_volume_check(db: Path) -> None:
    _listings(db, [100, 100, 5])

    assert _check(db, "listing_volume").status == "skipped"


# ---- completeness and keys -------------------------------------------------------------------
@pytest.mark.parametrize(
    ("with_skill", "status"), [(10, "pass"), (9, "pass"), (8, "warn"), (6, "error")]
)
def test_the_share_of_vacancies_without_any_skill_has_two_levels(
    db: Path, with_skill: int, status: str
) -> None:
    _skills(db, with_skill, 10)

    assert _check(db, "vacancies_without_skills").status == status


def test_an_empty_title_is_an_error(db: Path) -> None:
    _add(db, "dou:1")
    assert _check(db, "empty_key_fields").status == "pass"

    _sql(db, "UPDATE silver_vacancies SET title = '  '")

    assert _check(db, "empty_key_fields").status == "error"


# ---- salaries --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("usd_min", "usd_max", "status"),
    [(1000.0, 2000.0, "pass"), (50.0, 90.0, "error"), (1000.0, 40000.0, "error")],
)
def test_a_salary_outside_the_plausible_range_is_reported(
    db: Path, usd_min: float, usd_max: float, status: str
) -> None:
    _add(db, "dou:1")
    _sql(
        db, "UPDATE silver_vacancies SET salary_usd_min = ?, salary_usd_max = ?", [usd_min, usd_max]
    )

    assert _check(db, "salary_in_range").status == status


def test_a_fall_in_parsed_salaries_is_found_by_comparing_recent_and_earlier_pages(db: Path) -> None:
    for i in range(25):  # earlier pages: all salaries parsed
        _add(db, f"dou:old{i}", fetched=NOW - timedelta(days=30), salary_raw="1000 USD")
    for i in range(25):  # the last week: the format changed and half are no longer read
        _add(db, f"dou:new{i}", fetched=NOW - timedelta(hours=2), salary_raw="1000 USD")
    _sql(db, "UPDATE silver_vacancies SET salary_min = 1000.0 WHERE id LIKE 'dou:old%'")
    _sql(db, "UPDATE silver_vacancies SET salary_min = 1000.0 WHERE id IN "
             "(SELECT id FROM silver_vacancies WHERE id LIKE 'dou:new%' LIMIT 12)")  # fmt: skip

    result = _check(db, "salary_parse_rate")

    assert result.status == "error" and result.observed == pytest.approx(1 - 12 / 25)


# ---- drift -----------------------------------------------------------------------------------
def _two_windows(db: Path, earlier_salary: bool, newest_salary: bool, n: int = 25) -> None:
    for i in range(n):
        _add(db, f"dou:old{i}", fetched=NOW - timedelta(days=30),
             salary_raw="1000 USD" if earlier_salary else None)  # fmt: skip
        _add(db, f"dou:new{i}", fetched=NOW - timedelta(hours=2),
             salary_raw="1000 USD" if newest_salary else None)  # fmt: skip


@pytest.mark.parametrize(("newest_salary", "status"), [(True, "pass"), (False, "warn")])
def test_a_jump_in_the_share_of_vacancies_with_a_salary_warns_but_never_fails(
    db: Path, newest_salary: bool, status: str
) -> None:
    _two_windows(db, earlier_salary=True, newest_salary=newest_salary)

    result = _check(db, "salary_share_drift")

    assert result.status == status and result.error is None


@pytest.mark.parametrize(("newest_length", "status"), [(105, "pass"), (400, "warn"), (20, "warn")])
def test_a_change_in_the_mean_description_length_warns(
    db: Path, newest_length: int, status: str
) -> None:
    _two_windows(db, earlier_salary=False, newest_salary=False)
    _sql(
        db,
        "UPDATE silver_vacancies SET description_text = repeat('x', 100) WHERE id LIKE 'dou:old%'",
    )
    _sql(
        db,
        "UPDATE silver_vacancies SET description_text = repeat('x', ?) WHERE id LIKE 'dou:new%'",
        [newest_length],
    )

    assert _check(db, "description_length_drift").status == status


def test_drift_is_not_judged_on_a_handful_of_vacancies(db: Path) -> None:
    _two_windows(db, earlier_salary=True, newest_salary=False, n=5)

    assert _check(db, "salary_share_drift").status == "skipped"
    assert _check(db, "description_length_drift").status == "skipped"


# ---- references ------------------------------------------------------------------------------
def test_rows_pointing_at_missing_parents_are_an_error(db: Path) -> None:
    _add(db, "dou:1")
    assert _check(db, "references").status == "pass"

    _sql(db, "UPDATE silver_vacancies SET dedup_group_id = 'dou:gone'")

    result = _check(db, "references")
    assert result.status == "error" and "missing group" in result.detail


def test_listed_vacancies_without_a_parsed_page_are_measured_on_the_latest_day(db: Path) -> None:
    for i in range(5):
        _add(db, f"dou:{i}")
    _listings(db, [5])  # all five listed and parsed
    assert _check(db, "sightings_have_pages").status == "pass"

    store = SilverStore(db)
    store.add_sightings([f"dou:{i}" for i in range(10)], date(2026, 11, 2))  # five have no page
    store.close()

    assert _check(db, "sightings_have_pages").status == "error"


# ---- parse failures --------------------------------------------------------------------------
def _parse_run(db: Path, source: str, pages: int, failed: int) -> None:
    ops = OpsStore(db)
    run = ops.start_task("parse", source, date(2026, 11, 9))
    ops.finish_task(run, "partial", rows_in=pages, rows_out=pages - failed, rows_failed=failed)
    ops.close()


def test_unparsed_pages_are_counted_for_vacancy_sources_only(db: Path) -> None:
    _parse_run(db, "dou", 1000, 5)  # 0.5%: fine
    _parse_run(db, "dou_salaries", 300_000, 0)  # the survey loader logs rows, not pages
    assert _check(db, "parse_failures").status == "pass"

    _parse_run(db, "djinni", 1000, 100)

    result = _check(db, "parse_failures")
    assert result.status == "error" and result.observed == pytest.approx(105 / 2000)


# ---- gold and schema -------------------------------------------------------------------------
def test_gold_must_exist_and_have_rows_once_silver_has_skills(db: Path) -> None:
    assert _check(db, "gold_built").status == "error"  # dbt has not run at all

    _sql(db, "CREATE TABLE fct_skill_demand_monthly (x INTEGER)")
    assert _check(db, "gold_built").status == "skipped"  # built, but silver has no skills yet

    _skills(db, 1, 1)
    assert _check(db, "gold_built").status == "error"  # skills exist, the mart is empty

    _sql(db, "INSERT INTO fct_skill_demand_monthly VALUES (1)")
    assert _check(db, "gold_built").status == "pass"


def test_a_changed_silver_column_is_a_schema_error(db: Path) -> None:
    assert _check(db, "schema_contract").status == "pass"

    _sql(db, "ALTER TABLE silver_vacancies DROP COLUMN seniority")

    result = _check(db, "schema_contract")
    assert result.status == "error" and "seniority" in result.detail


# ---- the command -----------------------------------------------------------------------------
def _results(db: Path) -> dict[str, str]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return dict(con.execute("SELECT check_name, status FROM ops_dq_results").fetchall())
    finally:
        con.close()


def test_the_command_stores_every_result_and_exits_1_only_for_an_error(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DUCKDB_PATH", str(db))
    _add(db, "dou:1", fetched=datetime(2026, 1, 1))  # years old: fresh_data is an error

    assert main(["dq"]) == 1

    stored = _results(db)
    assert stored["fresh_data"] == "error" and stored["schema_contract"] == "pass"
    assert len(stored) == 13


def test_warnings_alone_do_not_stop_the_run(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUCKDB_PATH", str(db))
    fresh = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=31)  # warn, not error
    _add(db, "dou:1", fetched=fresh)
    _sql(db, "INSERT INTO silver_skills VALUES ('python', 'Python', 'language', NULL)")
    _sql(db, "INSERT INTO silver_vacancy_skills VALUES ('dou:1','python','required','dictionary',"
             "1.0,NULL,NULL,'r',now())")  # fmt: skip
    _sql(db, "CREATE TABLE fct_skill_demand_monthly (x INTEGER)")
    _sql(db, "INSERT INTO fct_skill_demand_monthly VALUES (1)")

    assert main(["dq"]) == 0
    assert _results(db)["fresh_data"] == "warn"
