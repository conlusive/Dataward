from datetime import date
from pathlib import Path

from jobmarket.ops import OpsStore, ScrapeStats

RUN_DATE = date(2026, 11, 6)


def test_rerun_creates_new_attempt_and_keeps_old_row(tmp_path: Path) -> None:
    ops = OpsStore(tmp_path / "ops.duckdb")

    first = ops.start_run("dou", RUN_DATE)
    ops.finish_run(first, "success", ScrapeStats(pages=3, new=3))
    second = ops.start_run("dou", RUN_DATE)
    ops.finish_run(second, "failed", ScrapeStats(errors=1))

    assert first == "scrape-dou-2026-11-06-1"
    assert second == "scrape-dou-2026-11-06-2"
    rows = ops._con.execute(
        "SELECT run_id, status, pages FROM ops_scrape_runs ORDER BY attempt"
    ).fetchall()
    assert rows == [(first, "success", 3), (second, "failed", 0)]
    ops.close()


def test_attempts_are_counted_per_source_and_date(tmp_path: Path) -> None:
    ops = OpsStore(tmp_path / "ops.duckdb")

    ops.start_run("dou", RUN_DATE)

    assert ops.start_run("djinni", RUN_DATE).endswith("-1")
    assert ops.start_run("dou", date(2026, 11, 7)).endswith("-1")
    ops.close()
