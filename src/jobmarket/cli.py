"""CLI: ``jobmarket scrape|parse <source|all> --run-date YYYY-MM-DD``."""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime

from loguru import logger

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.ops import OpsStore
from jobmarket.registry import DAILY_SOURCES, SOURCES
from jobmarket.runner import run_source
from jobmarket.silver.build import PARSERS, parse_source
from jobmarket.silver.dedup_step import apply_dedup
from jobmarket.silver.rates import load_nbu_rates, missing_rate_dates, needed_rate_dates
from jobmarket.silver.salary_step import apply_salaries
from jobmarket.silver.store import SilverStore
from jobmarket.silver.survey_build import load_surveys
from jobmarket.silver.text_step import apply_text_signals
from jobmarket.silver.usd import apply_usd
from jobmarket.skills.dictionary import DictionaryExtractor
from jobmarket.skills.dictionary_step import apply_dictionary_skills, load_taxonomy_into_silver
from jobmarket.skills.taxonomy import load_taxonomy


def _default_run_date() -> date:
    env_value = os.environ.get("RUN_DATE")
    return date.fromisoformat(env_value) if env_value else datetime.now(UTC).date()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobmarket")
    commands = parser.add_subparsers(dest="command", required=True)
    scrape = commands.add_parser("scrape", help="fetch raw data into bronze")
    scrape.add_argument("source", choices=[*SOURCES, "all"])
    scrape.add_argument(
        "--run-date",
        type=date.fromisoformat,
        default=None,
        help="YYYY-MM-DD; defaults to $RUN_DATE or today (UTC)",
    )
    scrape.add_argument(
        "--refetch", action="store_true", help="re-download files already in bronze"
    )
    scrape.add_argument(
        "--max-pages", type=int, default=None, help="cap listing pages per category (for testing)"
    )
    parse = commands.add_parser("parse", help="parse bronze pages into silver_vacancies")
    parse.add_argument("source", choices=[*PARSERS, "all"])
    parse.add_argument(
        "--run-date",
        type=date.fromisoformat,
        default=None,
        help="YYYY-MM-DD; defaults to $RUN_DATE or today (UTC)",
    )
    commands.add_parser(
        "fetch-rates", help="download NBU rates for the dates that silver salaries need"
    )
    commands.add_parser(
        "parse-surveys", help="load the DOU salary survey waves from bronze into silver"
    )
    return parser


def _parse_surveys() -> int:
    settings = Settings.from_env()
    ops = OpsStore(settings.duckdb_path)
    silver = SilverStore(settings.duckdb_path)
    today = datetime.now(UTC).date()
    task_id = ops.start_task("parse", "dou_salaries", today)
    try:
        stats = load_surveys(BronzeStore(settings.bronze_dir), silver, run_id=task_id)
    except Exception as exc:
        ops.finish_task(task_id, "failed", rows_in=0, rows_out=0, rows_failed=0, error=repr(exc))
        raise
    finally:
        silver.close()
    problems = stats.failed + stats.unmapped
    status = "success" if problems == 0 else ("partial" if stats.loaded else "failed")
    ops.finish_task(
        task_id,
        status,
        rows_in=stats.rows_kept + stats.rows_no_salary + stats.rows_outliers,
        rows_out=stats.rows_kept,
        rows_failed=problems,
    )
    ops.close()
    logger.info("{} {}: {}", task_id, status, stats)
    return 1 if problems else 0


async def _fetch_rates() -> int:
    settings = Settings.from_env()
    ops = OpsStore(settings.duckdb_path)
    silver = SilverStore(settings.duckdb_path)
    try:
        bronze = BronzeStore(settings.bronze_dir)
        missing = missing_rate_dates(bronze, needed_rate_dates(silver))
        logger.info("NBU rates missing for {} dates", len(missing))
        exit_code = 0
        for day in missing:
            stats = await run_source("nbu_rates", day, settings=settings, ops=ops)
            exit_code = 1 if stats.errors else exit_code
        return exit_code
    finally:
        silver.close()
        ops.close()


def _parse(sources: Sequence[str], run_date: date) -> int:
    settings = Settings.from_env()
    ops = OpsStore(settings.duckdb_path)
    silver = SilverStore(settings.duckdb_path)
    bronze = BronzeStore(settings.bronze_dir)
    exit_code = 0
    try:
        logger.info("NBU rates loaded from bronze: {} rows", load_nbu_rates(bronze, silver))
        taxonomy = load_taxonomy()
        load_taxonomy_into_silver(silver, taxonomy)
        extractor = DictionaryExtractor(taxonomy)
        for source in sources:
            task_id = ops.start_task("parse", source, run_date)
            try:
                stats = parse_source(source, run_date, bronze=bronze, silver=silver, run_id=task_id)
            except Exception as exc:
                ops.finish_task(
                    task_id, "failed", rows_in=0, rows_out=0, rows_failed=0, error=repr(exc)
                )
                raise
            status = "success" if stats.failed == 0 else ("partial" if stats.parsed else "failed")
            ops.finish_task(
                task_id,
                status,
                rows_in=stats.pages,
                rows_out=stats.parsed,
                rows_failed=stats.failed,
            )
            logger.info("{} {}: {}", task_id, status, stats)
            logger.info("salaries {}: {}", source, apply_salaries(silver, source))
            logger.info("text signals {}: {}", source, apply_text_signals(silver, source))
            skills = apply_dictionary_skills(silver, extractor, source, run_id=task_id)
            logger.info("skills {}: {}", source, skills)
            usd = apply_usd(silver, source)
            logger.info("usd {}: {}", source, usd)
            if usd.missing_dates:
                days = ", ".join(sorted(d.isoformat() for d in usd.missing_dates))
                logger.warning("no NBU rate for {}; run `jobmarket fetch-rates`", days)
            if stats.failed:
                exit_code = 1
        # Duplicates are found across sources, so this runs once, after every source is parsed.
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


async def _scrape(
    sources: Sequence[str], run_date: date, refetch: bool, max_pages: int | None
) -> int:
    settings = Settings.from_env()
    if max_pages is not None:
        settings = replace(settings, max_list_pages=max_pages)
    ops = OpsStore(settings.duckdb_path)
    exit_code = 0
    try:
        for source in sources:
            stats = await run_source(source, run_date, settings=settings, ops=ops, refetch=refetch)
            if stats.errors:
                exit_code = 1
    finally:
        ops.close()
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "fetch-rates":
        return asyncio.run(_fetch_rates())
    if args.command == "parse-surveys":
        return _parse_surveys()
    run_date: date = args.run_date or _default_run_date()
    if args.command == "parse":
        return _parse(tuple(PARSERS) if args.source == "all" else (args.source,), run_date)
    sources = DAILY_SOURCES if args.source == "all" else (args.source,)
    return asyncio.run(_scrape(sources, run_date, args.refetch, args.max_pages))


if __name__ == "__main__":
    sys.exit(main())
