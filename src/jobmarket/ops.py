"""Operational metrics in DuckDB. A re-run of the same date is a new attempt, not an edit."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

_DDL = """
CREATE TABLE IF NOT EXISTS ops_scrape_runs (
    run_id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,
    run_date DATE NOT NULL,
    attempt INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status VARCHAR NOT NULL,
    pages INTEGER,
    new_pages INTEGER,
    updated_pages INTEGER,
    unchanged_pages INTEGER,
    skipped_pages INTEGER,
    errors INTEGER,
    http_429 INTEGER,
    http_403 INTEGER,
    UNIQUE (source, run_date, attempt)
)
"""

_TASK_DDL = """
CREATE TABLE IF NOT EXISTS ops_task_runs (
    run_id VARCHAR PRIMARY KEY,
    task VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    run_date DATE NOT NULL,
    attempt INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status VARCHAR NOT NULL,
    rows_in INTEGER,
    rows_out INTEGER,
    rows_failed INTEGER,
    error VARCHAR,
    UNIQUE (task, source, run_date, attempt)
)
"""

_LLM_USAGE_DDL = """
CREATE TABLE IF NOT EXISTS ops_llm_usage (
    run_id VARCHAR PRIMARY KEY,
    model VARCHAR NOT NULL,
    prompt_version VARCHAR NOT NULL,
    vacancies INTEGER NOT NULL,
    calls INTEGER NOT NULL,
    cache_hits INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd DOUBLE NOT NULL,
    created_at TIMESTAMP NOT NULL
)
"""

_DQ_DDL = """
CREATE TABLE IF NOT EXISTS ops_dq_results (
    run_id VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    layer VARCHAR NOT NULL,
    observed DOUBLE,
    warn_threshold DOUBLE,
    error_threshold DOUBLE,
    status VARCHAR NOT NULL,  -- pass | warn | error | skipped
    detail VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    PRIMARY KEY (run_id, check_name)
)
"""

_PIPELINE_DDL = """
CREATE TABLE IF NOT EXISTS ops_pipeline_runs (
    run_id VARCHAR PRIMARY KEY,  -- flow-daily-2026-11-09-1
    flow VARCHAR NOT NULL,  -- daily | backfill
    run_date DATE NOT NULL,
    attempt INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status VARCHAR NOT NULL,  -- running | success | failed
    trigger VARCHAR NOT NULL,  -- cron | manual | backfill
    run_url VARCHAR,  -- the GitHub Actions run, when there is one
    failed_steps VARCHAR,  -- comma-separated step names, NULL when none
    UNIQUE (flow, run_date, attempt)
)
"""


@dataclass
class ScrapeStats:
    pages: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    http_429: int = 0
    http_403: int = 0


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class OpsStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(db_path))
        self._con.execute(_DDL)
        self._con.execute(_TASK_DDL)
        self._con.execute(_LLM_USAGE_DDL)
        self._con.execute(_DQ_DDL)
        self._con.execute(_PIPELINE_DDL)

    def close(self) -> None:
        self._con.close()

    def start_run(self, source: str, run_date: date) -> str:
        row = self._con.execute(
            "SELECT coalesce(max(attempt), 0) + 1 FROM ops_scrape_runs "
            "WHERE source = ? AND run_date = ?",
            [source, run_date],
        ).fetchone()
        attempt = int(row[0]) if row else 1
        run_id = f"scrape-{source}-{run_date.isoformat()}-{attempt}"
        self._con.execute(
            "INSERT INTO ops_scrape_runs (run_id, source, run_date, attempt, started_at, status) "
            "VALUES (?, ?, ?, ?, ?, 'running')",
            [run_id, source, run_date, attempt, _utc_now()],
        )
        return run_id

    def finish_run(self, run_id: str, status: str, stats: ScrapeStats) -> None:
        self._con.execute(
            "UPDATE ops_scrape_runs SET finished_at = ?, status = ?, pages = ?, new_pages = ?, "
            "updated_pages = ?, unchanged_pages = ?, skipped_pages = ?, errors = ?, "
            "http_429 = ?, http_403 = ? WHERE run_id = ?",
            [
                _utc_now(),
                status,
                stats.pages,
                stats.new,
                stats.updated,
                stats.unchanged,
                stats.skipped,
                stats.errors,
                stats.http_429,
                stats.http_403,
                run_id,
            ],
        )

    def start_task(self, task: str, source: str, run_date: date) -> str:
        row = self._con.execute(
            "SELECT coalesce(max(attempt), 0) + 1 FROM ops_task_runs "
            "WHERE task = ? AND source = ? AND run_date = ?",
            [task, source, run_date],
        ).fetchone()
        attempt = int(row[0]) if row else 1
        run_id = f"{task}-{source}-{run_date.isoformat()}-{attempt}"
        self._con.execute(
            "INSERT INTO ops_task_runs "
            "(run_id, task, source, run_date, attempt, started_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'running')",
            [run_id, task, source, run_date, attempt, _utc_now()],
        )
        return run_id

    def finish_task(
        self,
        run_id: str,
        status: str,
        *,
        rows_in: int,
        rows_out: int,
        rows_failed: int,
        error: str | None = None,
    ) -> None:
        self._con.execute(
            "UPDATE ops_task_runs SET finished_at = ?, status = ?, rows_in = ?, rows_out = ?, "
            "rows_failed = ?, error = ? WHERE run_id = ?",
            [_utc_now(), status, rows_in, rows_out, rows_failed, error, run_id],
        )

    def start_pipeline(
        self, flow: str, run_date: date, *, trigger: str, run_url: str | None
    ) -> str:
        row = self._con.execute(
            "SELECT coalesce(max(attempt), 0) + 1 FROM ops_pipeline_runs "
            "WHERE flow = ? AND run_date = ?",
            [flow, run_date],
        ).fetchone()
        attempt = int(row[0]) if row else 1
        run_id = f"flow-{flow}-{run_date.isoformat()}-{attempt}"
        self._con.execute(
            "INSERT INTO ops_pipeline_runs (run_id, flow, run_date, attempt, started_at, status, "
            "trigger, run_url) VALUES (?, ?, ?, ?, ?, 'running', ?, ?)",
            [run_id, flow, run_date, attempt, _utc_now(), trigger, run_url],
        )
        return run_id

    def finish_pipeline(self, run_id: str, status: str, failed_steps: list[str]) -> None:
        self._con.execute(
            "UPDATE ops_pipeline_runs SET finished_at = ?, status = ?, failed_steps = ? "
            "WHERE run_id = ?",
            [_utc_now(), status, ",".join(failed_steps) or None, run_id],
        )

    def add_dq_results(
        self,
        run_id: str,
        results: list[tuple[str, str, float | None, float | None, float | None, str, str]],
    ) -> None:
        """results: (check, layer, observed, warn_threshold, error_threshold, status, detail)."""
        now = _utc_now()
        for check, layer, observed, warn, error, status, detail in results:
            self._con.execute(
                "INSERT INTO ops_dq_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [run_id, check, layer, observed, warn, error, status, detail, now],
            )

    def parsed_dates(
        self, source: str, *, today: date | None = None, retry_partial_days: int = 3
    ) -> set[date]:
        """Dates of ``source`` whose parse needs no repeating.

        A successful parse is final. A partial one (some pages did not match the parser) is final
        only once it is older than ``retry_partial_days``: a recent one is tried again after a
        parser fix, while pages that stay unreadable do not make every nightly run re-parse the
        whole history. A crashed or unfinished parse is never final.
        """
        rows = self._con.execute(
            "SELECT DISTINCT run_date FROM ops_task_runs WHERE task = 'parse' AND source = ? AND "
            "(status = 'success' OR (status = 'partial' AND run_date < ?))",
            [source, (today or _utc_now().date()) - timedelta(days=retry_partial_days)],
        ).fetchall()
        return {row[0] for row in rows}

    def add_llm_usage(
        self,
        run_id: str,
        model: str,
        prompt_version: str,
        *,
        vacancies: int,
        calls: int,
        cache_hits: int,
        failed: int,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        self._con.execute(
            "INSERT INTO ops_llm_usage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                model,
                prompt_version,
                vacancies,
                calls,
                cache_hits,
                failed,
                prompt_tokens,
                completion_tokens,
                cost_usd,
                _utc_now(),
            ],
        )
