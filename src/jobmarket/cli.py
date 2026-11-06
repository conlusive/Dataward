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
from jobmarket.silver.store import SilverStore


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
    return parser


def _parse(sources: Sequence[str], run_date: date) -> int:
    settings = Settings.from_env()
    ops = OpsStore(settings.duckdb_path)
    silver = SilverStore(settings.duckdb_path)
    bronze = BronzeStore(settings.bronze_dir)
    exit_code = 0
    try:
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
            if stats.failed:
                exit_code = 1
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
    run_date: date = args.run_date or _default_run_date()
    if args.command == "parse":
        return _parse(tuple(PARSERS) if args.source == "all" else (args.source,), run_date)
    sources = DAILY_SOURCES if args.source == "all" else (args.source,)
    return asyncio.run(_scrape(sources, run_date, args.refetch, args.max_pages))


if __name__ == "__main__":
    sys.exit(main())
