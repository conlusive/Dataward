"""Runs one source for one run_date and records the outcome in ops_scrape_runs."""

from datetime import date

from loguru import logger

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.ops import OpsStore, ScrapeStats
from jobmarket.registry import SOURCES


def _status(stats: ScrapeStats) -> str:
    if stats.errors == 0:
        return "success"
    return "partial" if stats.pages > 0 else "failed"


async def run_source(
    source: str, run_date: date, *, settings: Settings, ops: OpsStore, refetch: bool = False
) -> ScrapeStats:
    scraper_cls = SOURCES[source]
    run_id = ops.start_run(source, run_date)
    logger.info("{} started", run_id)
    stats = ScrapeStats(errors=1)  # reported if the scraper crashes before producing stats
    try:
        async with scraper_cls(
            settings=settings,
            store=BronzeStore(settings.bronze_dir),
            run_id=run_id,
            run_date=run_date,
        ) as scraper:
            try:
                await scraper.run(refetch=refetch)
            finally:
                stats = scraper.stats
    except Exception:
        ops.finish_run(run_id, "failed", stats)
        logger.exception("{} crashed", run_id)
        raise
    status = _status(stats)
    ops.finish_run(run_id, status, stats)
    logger.info("{} {}: {}", run_id, status, stats)
    return stats
