"""The silver pipeline: bronze -> parsed vacancies -> enrichment -> duplicates, with run metrics."""

from collections.abc import Sequence
from datetime import UTC, date, datetime

from loguru import logger

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.ops import OpsStore
from jobmarket.silver.build import parse_source
from jobmarket.silver.dedup_step import apply_dedup
from jobmarket.silver.rates import load_nbu_rates
from jobmarket.silver.salary_step import apply_salaries
from jobmarket.silver.sightings import listed_vacancy_ids
from jobmarket.silver.store import SilverStore
from jobmarket.silver.text_step import apply_text_signals
from jobmarket.silver.usd import apply_usd
from jobmarket.skills.dictionary import DictionaryExtractor
from jobmarket.skills.dictionary_step import apply_dictionary_skills, load_taxonomy_into_silver
from jobmarket.skills.taxonomy import load_taxonomy

# A few pages that do not match the parser are normal (odd vacancies); a large share means the
# site changed its markup, and then the run must fail so that somebody looks.
MAX_FAILED_SHARE = 0.05


def _days_to_parse(
    source: str, bronze: BronzeStore, ops: OpsStore, run_date: date, *, missing: bool
) -> list[date]:
    """One day, or every stored bronze day that has no finished parse yet (oldest first)."""
    if not missing:
        return [run_date]
    done = ops.parsed_dates(source)
    return [day for day in bronze.partition_dates(source) if day not in done]


def run_parse(
    settings: Settings, sources: Sequence[str], run_date: date, *, missing: bool = False
) -> int:
    """Parse and enrich ``sources``; returns 1 when too many pages no longer match their parser."""
    ops = OpsStore(settings.duckdb_path)
    silver = SilverStore(settings.duckdb_path)
    bronze = BronzeStore(settings.bronze_dir)
    exit_code = 0
    try:
        logger.info("NBU rates loaded from bronze: {} rows", load_nbu_rates(bronze, silver))
        taxonomy = load_taxonomy()
        load_taxonomy_into_silver(silver, taxonomy)
        extractor = DictionaryExtractor(taxonomy)
        today = datetime.now(UTC).date().isoformat()

        for source in sources:
            for day in _days_to_parse(source, bronze, ops, run_date, missing=missing):
                if _parse_day(source, day, bronze=bronze, silver=silver, ops=ops):
                    exit_code = 1
            # The enrichment is recomputed from silver every time: a changed taxonomy or rule
            # applies to vacancies parsed earlier without waiting for a new page.
            enrich_id = f"enrich-{source}-{today}"
            logger.info("salaries {}: {}", source, apply_salaries(silver, source))
            logger.info("text signals {}: {}", source, apply_text_signals(silver, source))
            logger.info(
                "skills {}: {}",
                source,
                apply_dictionary_skills(silver, extractor, source, run_id=enrich_id),
            )
            usd = apply_usd(silver, source)
            logger.info("usd {}: {}", source, usd)
            if usd.missing_dates:
                days = ", ".join(sorted(d.isoformat() for d in usd.missing_dates))
                logger.warning("no NBU rate for {}; run `jobmarket fetch-rates`", days)

        # Duplicates are found across sources, so this runs once, after every source.
        dedup_id = ops.start_task("dedup", "all", run_date)
        try:
            dedup = apply_dedup(silver, run_id=dedup_id)
        except Exception as exc:
            ops.finish_task(
                dedup_id, "failed", rows_in=0, rows_out=0, rows_failed=0, error=repr(exc)
            )
            raise
        ops.finish_task(
            dedup_id, "success", rows_in=dedup.vacancies, rows_out=dedup.groups, rows_failed=0
        )
        logger.info("dedup: {}", dedup)
    finally:
        silver.close()
        ops.close()
    return exit_code


def _parse_day(
    source: str, day: date, *, bronze: BronzeStore, silver: SilverStore, ops: OpsStore
) -> bool:
    """Parse one stored day of one source; True when too many pages no longer match the parser."""
    task_id = ops.start_task("parse", source, day)
    try:
        stats = parse_source(source, day, bronze=bronze, silver=silver, run_id=task_id)
    except Exception as exc:
        ops.finish_task(task_id, "failed", rows_in=0, rows_out=0, rows_failed=0, error=repr(exc))
        raise
    status = "success" if stats.failed == 0 else ("partial" if stats.parsed else "failed")
    ops.finish_task(
        task_id, status, rows_in=stats.pages, rows_out=stats.parsed, rows_failed=stats.failed
    )
    logger.info("{} {}: {}", task_id, status, stats)
    listed = listed_vacancy_ids(bronze, source, day)
    silver.add_sightings(listed, day)
    logger.info("sightings {}: {} vacancies listed on {}", source, len(listed), day)
    too_many = stats.failed > MAX_FAILED_SHARE * stats.pages
    if stats.failed and not too_many:
        logger.warning(
            "{}: {} of {} pages did not match the parser", task_id, stats.failed, stats.pages
        )
    return too_many
