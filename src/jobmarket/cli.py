"""CLI: ``jobmarket scrape <source|all> --run-date YYYY-MM-DD [--refetch]``."""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime

from jobmarket.config import Settings
from jobmarket.ops import OpsStore
from jobmarket.registry import DAILY_SOURCES, SOURCES
from jobmarket.runner import run_source


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
    return parser


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
    sources = DAILY_SOURCES if args.source == "all" else (args.source,)
    return asyncio.run(_scrape(sources, run_date, args.refetch, args.max_pages))


if __name__ == "__main__":
    sys.exit(main())
