"""The daily flow and the backfill flow: steps with dependencies, retries, timeouts and ops rows.

The commands themselves live in the Makefile and the CLI (one definition of "how to scrape" or
"how to build gold"); this module decides the order, what happens when a step fails and what is
recorded. A failed step makes the steps that need it `skipped`; independent steps still run. Each
attempt of each step is a row in `ops_task_runs` (task `flow`, source = step name).

DuckDB allows one process to hold the file, so no connection is kept open while a step runs.
"""

import os
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from loguru import logger

from jobmarket.ops import OpsStore


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    needs: tuple[str, ...] = ()
    timeout_s: int = 1800
    retries: int = 0  # extra attempts after the first one (a step must be idempotent to have any)
    retry_delay_s: float = 60.0


@dataclass(frozen=True)
class StepResult:
    name: str
    status: str  # success | failed | skipped
    attempts: int
    seconds: float
    detail: str = ""


Runner = Callable[[Step, dict[str, str]], int]

TIMEOUT_EXIT_CODE = 124


def daily_steps() -> list[Step]:
    """Scrape -> silver -> silver checks -> gold -> gold checks -> export."""
    return [
        Step("scrape", ("make", "scrape"), timeout_s=150 * 60, retries=1),
        Step("scrape_surveys", ("make", "scrape-surveys"), timeout_s=20 * 60, retries=1),
        Step("parse", ("make", "parse"), needs=("scrape",), timeout_s=40 * 60),
        Step("dq_silver", ("make", "dq-silver"), needs=("parse",), timeout_s=5 * 60),
        Step("dbt", ("make", "dbt-build"), needs=("dq_silver",), timeout_s=30 * 60),
        Step("dq_gold", ("make", "dq-gold"), needs=("dbt",), timeout_s=5 * 60),
        Step("export", ("make", "export"), needs=("dq_gold",), timeout_s=10 * 60),
    ]


def fresh_steps() -> list[Step]:
    """The hourly run: only what is new since the last run, then the same road to the export.

    The scrape reads the first listing pages again and fetches only vacancy pages not stored yet,
    so it costs a few dozen requests instead of the nightly sweep. Today is parsed again as a whole
    (a finished day is otherwise skipped). Closures still come from the nightly run: a vacancy is
    closed after two days without a sighting, so an hourly run can never close one by itself.
    """
    return [
        Step("scrape", ("make", "scrape-fresh"), timeout_s=20 * 60, retries=1),
        Step("parse", ("make", "parse-today"), needs=("scrape",), timeout_s=20 * 60),
        Step("dq_silver", ("make", "dq-silver"), needs=("parse",), timeout_s=5 * 60),
        Step("dbt", ("make", "dbt-build"), needs=("dq_silver",), timeout_s=30 * 60),
        Step("dq_gold", ("make", "dq-gold"), needs=("dbt",), timeout_s=5 * 60),
        Step("export", ("make", "export"), needs=("dq_gold",), timeout_s=10 * 60),
    ]


def backfill_steps(start: date, end: date) -> list[Step]:
    """Re-parse the stored days of a range and rebuild gold; no network."""
    return [
        Step(
            "backfill",
            ("uv", "run", "jobmarket", "backfill", "all", "--from", str(start), "--to", str(end)),
            timeout_s=60 * 60,
        ),
        Step("dq_silver", ("make", "dq-silver"), needs=("backfill",), timeout_s=5 * 60),
        Step("dbt", ("make", "dbt-build"), needs=("dq_silver",), timeout_s=30 * 60),
        Step("dq_gold", ("make", "dq-gold"), needs=("dbt",), timeout_s=5 * 60),
        Step("export", ("make", "export"), needs=("dq_gold",), timeout_s=10 * 60),
    ]


def trigger_from_env(flow: str) -> str:
    """cron | manual | backfill, from the environment the run was started in."""
    if flow == "backfill":
        return "backfill"
    return {"schedule": "cron", "workflow_dispatch": "manual"}.get(
        os.environ.get("GITHUB_EVENT_NAME", ""), "manual"
    )


def run_url_from_env() -> str | None:
    """The GitHub Actions run, when running there."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    return f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None


def subprocess_runner(step: Step, env: dict[str, str]) -> int:
    """Run the step's command with its own timeout; a timeout is exit code 124."""
    try:
        return subprocess.run(step.command, env=env, timeout=step.timeout_s, check=False).returncode
    except subprocess.TimeoutExpired:
        logger.error("step {} timed out after {} s", step.name, step.timeout_s)
        return TIMEOUT_EXIT_CODE


def run_flow(
    steps: Sequence[Step],
    run_date: date,
    db_path: Path,
    *,
    only: Sequence[str] | None = None,
    runner: Runner = subprocess_runner,
    sleep: Callable[[float], None] = time.sleep,
    flow: str = "daily",
) -> list[StepResult]:
    """Run the steps in order; ``only`` limits the run to some of them (their needs among the
    selected steps still apply, a need that was not selected counts as met).

    The whole run is a row in `ops_pipeline_runs` (flow, trigger, link to the Actions run, which
    steps failed), next to the per-attempt rows in `ops_task_runs`."""
    names = {step.name for step in steps}
    unknown = set(only or ()) - names
    if unknown:
        raise ValueError(f"unknown steps: {sorted(unknown)}; the flow has {sorted(names)}")
    selected = [s for s in steps if only is None or s.name in only]
    env = {**os.environ, "RUN_DATE": run_date.isoformat()}
    results: dict[str, StepResult] = {}
    pipeline_id = _pipeline_start(db_path, flow, run_date)

    for step in selected:
        blocked = [n for n in step.needs if n in results and results[n].status != "success"]
        if blocked:
            logger.warning("step {} skipped: needs {}", step.name, ", ".join(blocked))
            results[step.name] = StepResult(step.name, "skipped", 0, 0.0, f"needs {blocked[0]}")
            continue
        results[step.name] = _run_step(step, run_date, db_path, env, runner, sleep)
    ordered = [results[s.name] for s in selected]
    _pipeline_finish(db_path, pipeline_id, ordered)
    return ordered


def _pipeline_start(db_path: Path, flow: str, run_date: date) -> str:
    ops = OpsStore(db_path)
    try:
        return ops.start_pipeline(
            flow, run_date, trigger=trigger_from_env(flow), run_url=run_url_from_env()
        )
    finally:
        ops.close()


def _pipeline_finish(db_path: Path, run_id: str, results: Sequence[StepResult]) -> None:
    failed = [r.name for r in results if r.status == "failed"]
    ops = OpsStore(db_path)
    try:
        ops.finish_pipeline(run_id, "failed" if failed else "success", failed)
    finally:
        ops.close()


def _run_step(
    step: Step,
    run_date: date,
    db_path: Path,
    env: dict[str, str],
    runner: Runner,
    sleep: Callable[[float], None],
) -> StepResult:
    started = time.monotonic()
    code = 1
    attempt = 0
    for attempt in range(1, step.retries + 2):
        run_id = _record_start(db_path, step, run_date)
        logger.info("step {} (attempt {}/{}) started", step.name, attempt, step.retries + 1)
        code = runner(step, env)
        _record_finish(db_path, run_id, code)
        if code == 0:
            break
        logger.error("step {} attempt {} failed with exit code {}", step.name, attempt, code)
        if attempt <= step.retries:
            sleep(step.retry_delay_s)
    seconds = time.monotonic() - started
    status = "success" if code == 0 else "failed"
    detail = "" if code == 0 else f"exit code {code}"
    logger.info("step {} {} in {:.0f} s", step.name, status, seconds)
    return StepResult(step.name, status, attempt, seconds, detail)


def _record_start(db_path: Path, step: Step, run_date: date) -> str:
    ops = OpsStore(db_path)
    try:
        return ops.start_task("flow", step.name, run_date)
    finally:
        ops.close()


def _record_finish(db_path: Path, run_id: str, code: int) -> None:
    ops = OpsStore(db_path)
    try:
        ops.finish_task(
            run_id,
            "success" if code == 0 else "failed",
            rows_in=0,
            rows_out=0,
            rows_failed=0 if code == 0 else 1,
            error=None if code == 0 else f"exit code {code}",
        )
    finally:
        ops.close()


def summarize(flow: str, run_date: date, results: Sequence[StepResult]) -> str:
    """A few lines for the log and for the Telegram message."""
    ok = all(r.status == "success" for r in results)
    lines = [f"{'OK' if ok else 'FAILED'}: {flow} {run_date}"]
    for r in results:
        extra = f" ({r.detail})" if r.detail else ""
        lines.append(f"{r.status:>8}  {r.name}  {r.seconds:.0f}s{extra}")
    return "\n".join(lines)
