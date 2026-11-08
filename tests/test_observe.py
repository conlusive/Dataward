import json
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from jobmarket import cli
from jobmarket.flow import Step, StepResult, run_flow
from jobmarket.observe import (
    render_message,
    render_status,
    run_report,
    slo_results,
    status_document,
    write_status,
)
from jobmarket.ops import OpsStore, ScrapeStats
from jobmarket.silver.store import SilverStore
from tests.test_dq import _skills, _sql

NOW = datetime(2026, 11, 9, 12, 0)
DAY = date(2026, 11, 9)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.duckdb"
    SilverStore(path).close()
    OpsStore(path).close()
    return path


def _con(db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db), read_only=True)


def _slo(db: Path, name: str) -> tuple[bool | None, str]:
    con = _con(db)
    try:
        result = {s.name: s for s in slo_results(con, NOW)}[name]
    finally:
        con.close()
    return result.ok, result.observed


# ---- ops_pipeline_runs -----------------------------------------------------------------------
def _run(db: Path, codes: dict[str, int], flow: str = "daily", day: date = DAY) -> None:
    steps = [Step("a", ("true",)), Step("b", ("true",), needs=("a",)), Step("c", ("true",))]
    run_flow(
        steps, day, db, flow=flow, sleep=lambda _s: None,
        runner=lambda step, env: codes.get(step.name, 0),
    )  # fmt: skip


def _pipeline_rows(db: Path) -> list[tuple]:  # type: ignore[type-arg]
    con = _con(db)
    try:
        return con.execute(
            "SELECT run_id, flow, attempt, status, trigger, run_url, failed_steps "
            "FROM ops_pipeline_runs ORDER BY started_at, attempt"
        ).fetchall()
    finally:
        con.close()


def test_a_run_is_recorded_with_its_trigger_link_and_failed_steps(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")

    _run(db, {"a": 1})

    assert _pipeline_rows(db) == [
        (
            "flow-daily-2026-11-09-1",
            "daily",
            1,
            "failed",
            "cron",
            "https://github.com/owner/repo/actions/runs/123",
            "a",
        )  # fmt: skip
    ]  # `b` was skipped, not failed: only `a` is named


def test_manual_and_backfill_runs_are_told_apart_and_a_rerun_is_a_new_attempt(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)

    _run(db, {})
    _run(db, {})
    _run(db, {}, flow="backfill")

    rows = _pipeline_rows(db)
    assert [(r[1], r[2], r[3], r[4], r[5]) for r in rows] == [
        ("daily", 1, "success", "manual", None),
        ("daily", 2, "success", "manual", None),
        ("backfill", 1, "success", "backfill", None),
    ]


# ---- SLOs ------------------------------------------------------------------------------------
def _scrape_run(db: Path, hours_ago: float, status: str = "success") -> None:
    ops = OpsStore(db)
    run = ops.start_run("dou", DAY)
    ops.finish_run(run, status, ScrapeStats(pages=1))
    ops.close()
    _sql(db, "UPDATE ops_scrape_runs SET finished_at = ?", [NOW - timedelta(hours=hours_ago)])


@pytest.mark.parametrize(("hours", "ok"), [(5, True), (36, True), (37, False)])
def test_freshness_is_the_age_of_the_last_successful_scrape(
    db: Path, hours: float, ok: bool
) -> None:
    _scrape_run(db, hours)

    assert _slo(db, "data_freshness")[0] is ok


def test_without_any_scrape_freshness_is_unknown_not_failed(db: Path) -> None:
    assert _slo(db, "data_freshness")[0] is None


def test_a_failed_scrape_does_not_count_as_fresh(db: Path) -> None:
    _scrape_run(db, 1, status="failed")

    assert _slo(db, "data_freshness")[0] is None


def _runs(db: Path, succeeded: int, failed: int) -> None:
    for i in range(succeeded + failed):
        day = DAY - timedelta(days=i)
        _run(db, {"a": 1} if i < failed else {}, day=day)
    _sql(
        db,
        "UPDATE ops_pipeline_runs "
        "SET started_at = ? - INTERVAL (date_diff('day', run_date, ?)) DAY",
        [NOW, DAY],
    )


@pytest.mark.parametrize(
    ("succeeded", "failed", "ok"), [(19, 1, True), (18, 2, False), (20, 0, True)]
)
def test_the_success_rate_of_30_days_needs_95_percent(
    db: Path, succeeded: int, failed: int, ok: bool
) -> None:
    _runs(db, succeeded, failed)

    assert _slo(db, "success_rate")[0] is ok


def test_with_too_few_runs_the_success_rate_is_unknown(db: Path) -> None:
    _runs(db, 2, 1)

    assert _slo(db, "success_rate") == (None, "2/3")


@pytest.mark.parametrize(("with_skill", "ok"), [(10, True), (9, False)])
def test_skill_coverage_wants_fewer_than_ten_percent_of_vacancies_without_skills(
    db: Path, with_skill: int, ok: bool
) -> None:
    _skills(db, with_skill, 10)  # 10 vacancies: 0 or 1 without a skill

    assert _slo(db, "skill_coverage")[0] is ok


# ---- the report of a run ---------------------------------------------------------------------
def test_new_vacancies_are_those_first_listed_on_the_run_date(db: Path) -> None:
    store = SilverStore(db)
    store.add_sightings(["dou:1", "dou:2"], date(2026, 11, 8))
    store.add_sightings(["dou:1", "dou:2", "dou:3", "dou:4"], DAY)
    store.close()

    con = _con(db)
    assert run_report(con, DAY).new_vacancies == 2
    assert run_report(con, date(2026, 11, 8)).new_vacancies == 2  # two days of data now


def test_on_the_first_day_of_data_nothing_is_called_new(db: Path) -> None:
    store = SilverStore(db)
    store.add_sightings(["dou:1", "dou:2"], DAY)
    store.close()

    assert run_report(_con(db), DAY).new_vacancies is None


def test_closed_vacancies_come_from_gold_and_are_unknown_before_it_exists(db: Path) -> None:
    assert run_report(_con(db), DAY).closed_vacancies is None

    _sql(
        db,
        "CREATE TABLE fct_vacancy_daily AS "
        "SELECT DATE '2026-11-09' AS date, 'closed' AS status "
        "UNION ALL SELECT DATE '2026-11-09', 'closed' "
        "UNION ALL SELECT DATE '2026-11-09', 'new'",
    )

    assert run_report(_con(db), DAY).closed_vacancies == 2


def test_the_report_counts_the_latest_checks_of_the_day_and_the_llm_cost(db: Path) -> None:
    ops = OpsStore(db)
    old = ops.start_task("dq", "silver", DAY)
    ops.add_dq_results(old, [("fresh_data", "silver", 1.0, 30, 36, "error", "stale")])
    ops.finish_task(old, "failed", rows_in=1, rows_out=0, rows_failed=1)
    latest = ops.start_task("dq", "silver", DAY)  # a re-run replaces the earlier attempt
    ops.add_dq_results(
        latest,
        [
            ("fresh_data", "silver", 1.0, 30, 36, "pass", "fine"),
            ("references", "silver", 0, 1, 1, "warn", "2 orphans"),
            ("listing_volume", "silver", None, None, None, "skipped", "no history"),
        ],
    )
    ops.finish_task(latest, "success", rows_in=3, rows_out=1, rows_failed=0)
    ops.add_llm_usage(
        "llm-1", "m", "v1", vacancies=10, calls=10, cache_hits=0, failed=0,
        prompt_tokens=100, completion_tokens=50, cost_usd=0.25,
    )  # fmt: skip
    ops.close()
    _sql(db, "UPDATE ops_llm_usage SET created_at = ?", [NOW])  # the run's own day

    report = run_report(_con(db), DAY)

    assert report.dq_counts == {"pass": 1, "warn": 1, "error": 0, "skipped": 1}
    assert report.dq_problems == [("warn", "references", "2 orphans")]
    assert report.llm_cost_usd == pytest.approx(0.25)


def test_the_message_for_a_good_run_has_the_numbers_and_the_link() -> None:
    from jobmarket.observe import RunReport

    report = RunReport(120, 45, 130, 30, {"pass": 11, "warn": 0, "error": 0, "skipped": 2}, [], 0.0)
    ok = [StepResult("scrape", "success", 1, 5.0)]

    text = render_message("daily", DAY, ok, report, "https://example.com/run/1")

    assert text.splitlines()[0] == "OK: daily 2026-11-09"
    assert "120 new, 45 closed" in text and "pages: 130 new, 30 updated" in text
    assert "11 pass, 0 warn, 0 error, 2 skipped" in text
    assert text.splitlines()[-1] == "Run: https://example.com/run/1"


def test_the_message_for_a_failed_run_names_the_step_and_the_check_that_said_why() -> None:
    from jobmarket.observe import RunReport

    report = RunReport(
        None, None, 0, 0, {"pass": 3, "warn": 0, "error": 1, "skipped": 0},
        [("error", "fresh_data", "newest page fetched 40.0 h ago")], 0.0,
    )  # fmt: skip
    results = [
        StepResult("dq_silver", "failed", 1, 1.0, "exit code 2"),
        StepResult("dbt", "skipped", 0, 0.0, "needs dq_silver"),
    ]

    text = render_message("daily", DAY, results, report, None)

    assert text.startswith("FAILED: daily 2026-11-09")
    assert "failed dq_silver (exit code 2)" in text and "skipped dbt (needs dq_silver)" in text
    assert "ERROR fresh_data: newest page fetched 40.0 h ago" in text
    assert "Run:" not in text


def test_a_message_without_a_report_still_says_what_happened() -> None:
    text = render_message(
        "daily", DAY, [StepResult("scrape", "failed", 2, 9.0, "exit code 1")], None, None
    )

    assert "FAILED" in text and "scrape" in text


# ---- the status document ---------------------------------------------------------------------
def test_the_status_document_lists_runs_slos_and_checks_and_is_valid_json(
    db: Path, tmp_path: Path
) -> None:
    _run(db, {"a": 1})
    _scrape_run(db, 2)
    ops = OpsStore(db)
    run = ops.start_task("dq", "silver", DAY)
    ops.add_dq_results(run, [("references", "silver", 3, 1, 1, "error", "3 orphans")])
    ops.close()

    target = tmp_path / "out" / "status.json"
    write_status(db, target, NOW)
    document = json.loads(target.read_text(encoding="utf-8"))

    assert document["runs"][0]["status"] == "failed" and document["runs"][0]["failed_steps"] == "a"
    assert {s["name"] for s in document["slo"]} >= {"data_freshness", "success_rate"}
    assert document["dq_latest"][0]["status"] == "error"
    assert set(document["volumes"]) == {
        "silver_vacancies", "silver_vacancy_skills", "silver_vacancy_sightings",
    }  # fmt: skip


def test_the_terminal_view_shows_a_failing_slo_and_the_failed_step(db: Path) -> None:
    _run(db, {"a": 1})
    _scrape_run(db, 50)

    text = render_status(status_document(db, NOW))

    assert "FAIL data_freshness" in text and "failed: a" in text


def test_an_empty_database_gives_a_readable_status(db: Path) -> None:
    text = render_status(status_document(db, NOW))

    assert "no pipeline runs recorded yet" in text


# ---- publishing never fails a run ------------------------------------------------------------
def test_a_broken_database_does_not_stop_the_message_from_being_sent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []

    def fake_send(text: str) -> bool:
        sent.append(text)
        return True

    monkeypatch.setattr(cli, "send_telegram", fake_send)
    monkeypatch.chdir(tmp_path)
    empty = tmp_path / "empty.duckdb"
    duckdb.connect(str(empty)).close()  # a database without any of the tables

    cli._publish_run("daily", DAY, [StepResult("scrape", "failed", 1, 1.0, "exit code 1")], empty)

    assert len(sent) == 1 and sent[0].startswith("FAILED: daily")


def test_the_run_writes_status_json_next_to_the_export(
    db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "send_telegram", lambda text: True)
    monkeypatch.chdir(tmp_path)
    _run(db, {})

    cli._publish_run("daily", DAY, [StepResult("a", "success", 1, 1.0)], db)

    assert (tmp_path / "data" / "export" / "status.json").exists()


def test_the_status_command_prints_and_can_write_json(
    db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DUCKDB_PATH", str(db))
    out = tmp_path / "s.json"

    assert cli.main(["status", "--json", str(out)]) == 0

    assert "Pipeline status" in capsys.readouterr().out and json.loads(out.read_text())["slo"]
