"""CLI: ``jobmarket scrape|parse <source|all> --run-date YYYY-MM-DD``."""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import yaml
from loguru import logger

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.dq import LAYERS, run_checks
from jobmarket.export import EXPORT_DIR, ExportError, export_gold
from jobmarket.flow import (
    StepResult,
    backfill_steps,
    daily_steps,
    run_flow,
    run_url_from_env,
    summarize,
)
from jobmarket.gold_commands import evaluate, import_labels, make_sheet
from jobmarket.gold_seeds import write_seeds
from jobmarket.notify import send_telegram
from jobmarket.observe import (
    render_message,
    render_status,
    run_report,
    status_document,
    write_status,
)
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
    status_cmd = commands.add_parser(
        "status", help="pipeline runs, SLOs and the checks that need attention"
    )
    status_cmd.add_argument("--json", dest="json_path", type=Path, default=None)
    flow_cmd = commands.add_parser(
        "flow", help="run a whole flow (steps, retries, timeouts, ops rows): daily or backfill"
    )
    flow_cmd.add_argument("name", choices=["daily", "backfill"])
    flow_cmd.add_argument("--run-date", type=date.fromisoformat, default=None)
    flow_cmd.add_argument("--from", dest="start", type=date.fromisoformat, default=None)
    flow_cmd.add_argument("--to", dest="end", type=date.fromisoformat, default=None)
    flow_cmd.add_argument("--only", default=None, help="comma-separated steps to run")
    backfill = commands.add_parser(
        "backfill",
        help="re-parse the stored bronze days of a date range into silver (no network)",
    )
    backfill.add_argument("source", choices=[*PARSERS, "all"])
    backfill.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    backfill.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
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
    commands.add_parser(
        "export",
        help="write the gold marts to data/export as parquet, checked against the contracts",
    )
    dq_cmd = commands.add_parser(
        "dq", help="data-quality checks; exit 1 on an error (a warning only reports)"
    )
    dq_cmd.add_argument("--layer", choices=LAYERS, default=None, help="only this layer's checks")
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


def _flow(args: argparse.Namespace) -> int:
    run_date: date = args.run_date or _default_run_date()
    if args.name == "backfill":
        if args.start is None or args.end is None or args.start > args.end:
            logger.error("flow backfill needs --from and --to, with --from not after --to")
            return 2
        steps = backfill_steps(args.start, args.end)
    else:
        steps = daily_steps()
    only = args.only.split(",") if args.only else None
    try:
        results = run_flow(
            steps, run_date, Settings.from_env().duckdb_path, only=only, flow=args.name
        )
    except ValueError as error:
        logger.error("{}", error)
        return 2
    logger.info("flow summary\n{}", summarize(args.name, run_date, results))
    _publish_run(args.name, run_date, results, Settings.from_env().duckdb_path)
    return 0 if all(r.status == "success" for r in results) else 1


def _publish_run(flow: str, run_date: date, results: list[StepResult], db_path: Path) -> None:
    """status.json for the dashboard and the Telegram message. Observability must never fail the
    run, so a problem here is logged and the run's own result stands."""
    report = None
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            report = run_report(con, run_date)
        finally:
            con.close()
        write_status(db_path, EXPORT_DIR / "status.json")
    except (duckdb.Error, OSError) as error:
        logger.warning("could not build the run report: {!r}", error)
    send_telegram(render_message(flow, run_date, results, report, run_url_from_env()))


def _status(json_path: Path | None) -> int:
    db_path = Settings.from_env().duckdb_path
    document = status_document(db_path)
    print(render_status(document))
    if json_path is not None:
        write_status(db_path, json_path)
    return 0


def _dq(layer: str | None) -> int:
    settings = Settings.from_env()
    results = run_checks(settings.duckdb_path, layer=layer)
    today = datetime.now(UTC).date()
    ops = OpsStore(settings.duckdb_path)
    task_id = ops.start_task("dq", layer or "all", today)
    ops.add_dq_results(
        task_id,
        [(r.name, r.layer, r.observed, r.warn, r.error, r.status, r.detail) for r in results],
    )
    errors = [r for r in results if r.status == "error"]
    warnings = [r for r in results if r.status == "warn"]
    status = "failed" if errors else ("partial" if warnings else "success")
    ops.finish_task(
        task_id,
        status,
        rows_in=len(results),
        rows_out=sum(r.status == "pass" for r in results),
        rows_failed=len(errors),
    )
    ops.close()
    for r in results:
        logger.log(
            {"error": "ERROR", "warn": "WARNING"}.get(r.status, "INFO"),
            "dq {} [{}] {}: {}",
            r.status.upper(),
            r.layer,
            r.name,
            r.detail,
        )
        if os.environ.get("GITHUB_ACTIONS") and r.status in ("error", "warn"):
            level = "error" if r.status == "error" else "warning"
            print(f"::{level} title=dq {r.name}::{r.detail}")
    logger.info(
        "{}: {} checks, {} warnings, {} errors", task_id, len(results), len(warnings), len(errors)
    )
    return 1 if errors else 0


def _export() -> int:
    try:
        counts = export_gold(Settings.from_env().duckdb_path)
    except ExportError as error:
        logger.error("export failed: {}", error)
        return 1
    logger.info("exported {} tables to {}: {}", len(counts), EXPORT_DIR, counts)
    return 0


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
    if args.command == "dq":
        return _dq(args.layer)
    if args.command == "export":
        return _export()
    if args.command == "make-seeds":
        return _make_seeds()
    if args.command == "skills-review":
        return _skills_review(args.top)
    if args.command == "skills-renormalize":
        return _skills_renormalize()
    if args.command == "status":
        return _status(args.json_path)
    if args.command == "flow":
        return _flow(args)
    if args.command == "backfill":
        if args.start > args.end:
            logger.error("--from {} is after --to {}", args.start, args.end)
            return 2
        return run_parse(
            Settings.from_env(),
            tuple(PARSERS) if args.source == "all" else (args.source,),
            args.end,
            date_range=(args.start, args.end),
        )
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
