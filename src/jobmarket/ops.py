"""Operational metrics in DuckDB. A re-run of the same date is a new attempt, not an edit."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
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
