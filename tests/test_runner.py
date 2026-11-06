from datetime import date
from pathlib import Path
from typing import ClassVar

import pytest

from jobmarket.config import Settings
from jobmarket.ops import OpsStore
from jobmarket.registry import SOURCES
from jobmarket.runner import run_source
from jobmarket.scrapers.base import BaseScraper

RUN_DATE = date(2026, 11, 6)


class _OkScraper(BaseScraper):
    source: ClassVar[str] = "fake_ok"

    async def run(self, *, refetch: bool = False) -> None:
        self.stats.pages = 2
        self.stats.new = 2


class _PartialScraper(BaseScraper):
    source: ClassVar[str] = "fake_partial"

    async def run(self, *, refetch: bool = False) -> None:
        self.stats.pages = 1
        self.stats.errors = 1


class _CrashScraper(BaseScraper):
    source: ClassVar[str] = "fake_crash"

    async def run(self, *, refetch: bool = False) -> None:
        raise RuntimeError("boom")


@pytest.fixture
def ops(tmp_path: Path) -> OpsStore:
    return OpsStore(tmp_path / "ops.duckdb")


def _statuses(ops: OpsStore) -> dict[str, str]:
    rows = ops._con.execute("SELECT source, status FROM ops_scrape_runs").fetchall()
    return dict(rows)


async def test_status_is_recorded_for_success_partial_and_crash(
    tmp_path: Path, ops: OpsStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    for scraper in (_OkScraper, _PartialScraper, _CrashScraper):
        monkeypatch.setitem(SOURCES, scraper.source, scraper)
    settings = Settings(bronze_dir=tmp_path / "bronze")

    await run_source("fake_ok", RUN_DATE, settings=settings, ops=ops)
    await run_source("fake_partial", RUN_DATE, settings=settings, ops=ops)
    with pytest.raises(RuntimeError):
        await run_source("fake_crash", RUN_DATE, settings=settings, ops=ops)

    assert _statuses(ops) == {
        "fake_ok": "success",
        "fake_partial": "partial",
        "fake_crash": "failed",
    }
