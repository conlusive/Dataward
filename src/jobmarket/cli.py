"""CLI: ``jobmarket scrape|parse <source|all> --run-date YYYY-MM-DD``."""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime

import yaml
from loguru import logger

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.gold_commands import evaluate, import_labels, make_sheet
from jobmarket.gold_seeds import write_seeds
from jobmarket.ops import OpsStore
from jobmarket.registry import DAILY_SOURCES, SOURCES
from jobmarket.runner import run_source
from jobmarket.silver.build import PARSERS
from jobmarket.silver.pipeline import run_parse
from jobmarket.silver.rates import missing_rate_dates, needed_rate_dates
from jobmarket.silver.store import SilverStore
from jobmarket.silver.survey_build import load_surveys
from jobmarket.skills.llm import (
    DEFAULT_MODEL,
    PRICES_FILE,
    LlmError,
    OpenAICompatibleClient,
    client_from_env,
)
from jobmarket.skills.llm_step import renormalize_llm_skills, run_llm_extraction
from jobmarket.skills.normalize import Normalizer
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
    parse.add_argument(
        "--missing",
        action="store_true",
        help="parse every stored bronze day without a finished parse instead of one day",
    )
    commands.add_parser(
        "fetch-rates", help="download NBU rates for the dates that silver salaries need"
    )
    commands.add_parser(
        "parse-surveys", help="load the DOU salary survey waves from bronze into silver"
    )
    extract_cmd = commands.add_parser(
        "extract-skills", help="method B: ask the LLM for the skills of the vacancies in silver"
    )
    extract_cmd.add_argument("source", choices=[*PARSERS, "all"])
    extract_cmd.add_argument("--limit", type=int, default=None, help="at most N new LLM requests")
    extract_cmd.add_argument(
        "--max-cost-usd", type=float, default=None, help="stop starting new batches above this cost"
    )
    extract_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="count the requests and estimate the cost, call nothing",
    )
    sample_cmd = commands.add_parser(
        "gold-sample", help="write a label sheet with a random sample of vacancies to label by hand"
    )
    sample_cmd.add_argument("--n", type=int, default=150)
    sample_cmd.add_argument("--seed", type=int, default=1)
    sample_cmd.add_argument(
        "--prefill",
        action="store_true",
        help="suggest method A's skills (faster, biases the metric)",
    )
    sample_cmd.add_argument("--force", action="store_true", help="replace an existing sheet")
    commands.add_parser(
        "gold-import", help="read the labelled sheet into data/gold/skills_gold.yaml"
    )
    commands.add_parser(
        "gold-eval",
        help="precision/recall/F1 of every method against the gold set -> docs/metrics.md",
    )
    commands.add_parser(
        "make-seeds", help="write the dbt seeds (survey positions and cities) from silver"
    )
    review_cmd = commands.add_parser(
        "skills-review", help="list the most frequent skills the taxonomy does not know yet"
    )
    review_cmd.add_argument("--top", type=int, default=30)
    commands.add_parser(
        "skills-renormalize",
        help="map the stored LLM answers onto the current taxonomy again, without the LLM",
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


def _extract_skills(source: str, limit: int | None, max_cost: float | None, dry_run: bool) -> int:
    settings = Settings.from_env()
    try:
        client = client_from_env()
    except LlmError as exc:
        if not dry_run:
            logger.error("{}. Use --dry-run to see what a run would cost without a key.", exc)
            return 2
        client = OpenAICompatibleClient(
            base_url="http://localhost", model=os.environ.get("LLM_MODEL") or DEFAULT_MODEL
        )
    ops = OpsStore(settings.duckdb_path)
    silver = SilverStore(settings.duckdb_path)
    try:
        run_id = f"llm-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        stats = asyncio.run(
            run_llm_extraction(
                silver,
                ops,
                client,
                Normalizer(load_taxonomy()),
                source=None if source == "all" else source,
                run_id=run_id,
                limit=limit,
                max_cost_usd=max_cost,
                dry_run=dry_run,
                raw_dir=settings.bronze_dir / "llm_raw",
            )
        )
        logger.info("{}{}: {}", "dry run " if dry_run else "", run_id, stats)
        if client.model.split("/")[-1] not in _priced_models():
            logger.warning("no price for {} in llm_prices.yaml: the cost above is 0", client.model)
        return 1 if stats.failed else 0
    finally:
        silver.close()
        ops.close()


def _priced_models() -> set[str]:
    return set(yaml.safe_load(PRICES_FILE.read_text(encoding="utf-8"))["models"])


def _gold(args: argparse.Namespace) -> int:
    silver = SilverStore(Settings.from_env().duckdb_path)
    try:
        if args.command == "gold-sample":
            return make_sheet(silver, args.n, args.seed, prefill=args.prefill, force=args.force)
        if args.command == "gold-import":
            return import_labels(silver)
        return evaluate(silver)
    finally:
        silver.close()


def _make_seeds() -> int:
    silver = SilverStore(Settings.from_env().duckdb_path)
    try:
        shares = write_seeds(silver)
    finally:
        silver.close()
    logger.info(
        "seeds written to warehouse/seeds: positions in 'other' {:.1%}, cities unspecified {:.1%}",
        shares["positions_other"],
        shares["cities_unspecified"],
    )
    return 0


def _skills_review(top: int) -> int:
    silver = SilverStore(Settings.from_env().duckdb_path)
    try:
        rows = silver._con.execute(
            "SELECT term, vacancies, suggested_canonical, status FROM silver_unknown_skills "
            "WHERE status = 'new' ORDER BY vacancies DESC, term LIMIT ?",
            [top],
        ).fetchall()
    finally:
        silver.close()
    for term, vacancies, suggestion, _ in rows:
        hint = f"  (similar to: {suggestion})" if suggestion else ""
        print(f"{vacancies:5d}  {term}{hint}")
    if not rows:
        print("No unknown skills waiting for review.")
    return 0


def _skills_renormalize() -> int:
    silver = SilverStore(Settings.from_env().duckdb_path)
    try:
        count = renormalize_llm_skills(silver, Normalizer(load_taxonomy()), run_id="renormalize")
    finally:
        silver.close()
    logger.info("re-mapped the LLM skills of {} vacancies", count)
    return 0


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
    if args.command == "extract-skills":
        return _extract_skills(args.source, args.limit, args.max_cost_usd, args.dry_run)
    if args.command in ("gold-sample", "gold-import", "gold-eval"):
        return _gold(args)
    if args.command == "make-seeds":
        return _make_seeds()
    if args.command == "skills-review":
        return _skills_review(args.top)
    if args.command == "skills-renormalize":
        return _skills_renormalize()
    run_date: date = args.run_date or _default_run_date()
    if args.command == "parse":
        return run_parse(
            Settings.from_env(),
            tuple(PARSERS) if args.source == "all" else (args.source,),
            run_date,
            missing=args.missing,
        )
    sources = DAILY_SOURCES if args.source == "all" else (args.source,)
    return asyncio.run(_scrape(sources, run_date, args.refetch, args.max_pages))


if __name__ == "__main__":
    sys.exit(main())
