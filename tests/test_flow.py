import sys
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pytest
from loguru import logger

from jobmarket.cli import main
from jobmarket.flow import (
    Step,
    StepResult,
    backfill_steps,
    daily_steps,
    run_flow,
    subprocess_runner,
    summarize,
)
from jobmarket.notify import send_telegram

DAY = date(2026, 11, 9)


class FakeRunner:
    """Records the steps it is asked to run; `codes` gives the exit codes of a step's attempts."""

    def __init__(self, codes: dict[str, list[int]] | None = None) -> None:
        self.codes = {name: list(values) for name, values in (codes or {}).items()}
        self.calls: list[str] = []
        self.env: dict[str, str] = {}

    def __call__(self, step: Step, env: dict[str, str]) -> int:
        self.calls.append(step.name)
        self.env = env
        queue = self.codes.get(step.name)
        return queue.pop(0) if queue else 0


def _flow(
    tmp_path: Path, runner: FakeRunner, steps: list[Step] | None = None, **kwargs: object
) -> list[StepResult]:
    return run_flow(
        steps or daily_steps(),
        DAY,
        tmp_path / "t.duckdb",
        runner=runner,
        sleep=lambda _s: None,
        **kwargs,  # type: ignore[arg-type]
    )


def _status(results: list[StepResult]) -> dict[str, str]:
    return {r.name: r.status for r in results}


def test_a_healthy_day_runs_every_step_in_order_with_the_run_date(tmp_path: Path) -> None:
    runner = FakeRunner()

    results = _flow(tmp_path, runner)

    assert runner.calls == [
        "scrape", "scrape_surveys", "parse", "dq_silver", "dbt", "dq_gold", "export",
    ]  # fmt: skip
    assert set(_status(results).values()) == {"success"}
    assert runner.env["RUN_DATE"] == "2026-11-09"


def test_a_failing_silver_check_stops_gold_and_the_export_but_not_independent_steps(
    tmp_path: Path,
) -> None:
    runner = FakeRunner({"dq_silver": [1]})

    results = _flow(tmp_path, runner)

    assert _status(results) == {
        "scrape": "success",
        "scrape_surveys": "success",
        "parse": "success",
        "dq_silver": "failed",
        "dbt": "skipped",
        "dq_gold": "skipped",
        "export": "skipped",
    }
    assert "dbt" not in runner.calls and "export" not in runner.calls


def test_a_failed_scrape_skips_parsing_but_the_survey_still_runs(tmp_path: Path) -> None:
    runner = FakeRunner({"scrape": [1, 1]})  # the first attempt and its one retry

    results = _flow(tmp_path, runner)

    assert _status(results)["scrape"] == "failed" and _status(results)["parse"] == "skipped"
    assert _status(results)["scrape_surveys"] == "success"


def test_a_step_that_works_on_the_retry_is_a_success_and_both_attempts_are_recorded(
    tmp_path: Path,
) -> None:
    runner = FakeRunner({"scrape": [1, 0]})

    results = _flow(tmp_path, runner)

    scrape = next(r for r in results if r.name == "scrape")
    assert scrape.status == "success" and scrape.attempts == 2
    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    rows = con.execute(
        "SELECT attempt, status FROM ops_task_runs WHERE task = 'flow' AND source = 'scrape' "
        "ORDER BY attempt"
    ).fetchall()
    assert rows == [(1, "failed"), (2, "success")]


def test_a_step_without_retries_is_tried_once(tmp_path: Path) -> None:
    runner = FakeRunner({"parse": [1, 0]})

    results = _flow(tmp_path, runner)

    assert _status(results)["parse"] == "failed" and runner.calls.count("parse") == 1


def test_the_retry_waits_between_attempts(tmp_path: Path) -> None:
    waits: list[float] = []
    steps = [Step("a", ("true",), retries=2, retry_delay_s=7.0)]

    run_flow(
        steps, DAY, tmp_path / "t.duckdb", runner=FakeRunner({"a": [1, 1, 0]}), sleep=waits.append
    )

    assert waits == [7.0, 7.0]


def test_only_runs_the_chosen_steps_and_a_need_outside_the_choice_counts_as_met(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()

    results = _flow(tmp_path, runner, only=["dbt", "export"])

    assert runner.calls == ["dbt", "export"] and set(_status(results).values()) == {"success"}


def test_an_unknown_step_name_is_refused_before_anything_runs(tmp_path: Path) -> None:
    runner = FakeRunner()

    with pytest.raises(ValueError, match="unknown steps"):
        _flow(tmp_path, runner, only=["dbt", "typo"])

    assert runner.calls == []


def test_a_backfill_rebuilds_gold_from_the_range_without_scraping(tmp_path: Path) -> None:
    runner = FakeRunner()
    steps = backfill_steps(date(2026, 11, 1), date(2026, 11, 5))

    _flow(tmp_path, runner, steps)

    assert runner.calls == ["backfill", "dq_silver", "dbt", "dq_gold", "export"]
    assert steps[0].command[-4:] == ("--from", "2026-11-01", "--to", "2026-11-05")


def test_a_real_command_that_hangs_is_killed_and_counts_as_a_failure() -> None:
    step = Step("slow", (sys.executable, "-c", "import time; time.sleep(30)"), timeout_s=1)

    assert subprocess_runner(step, {}) == 124


def test_the_runner_returns_the_commands_exit_code() -> None:
    ok = Step("ok", (sys.executable, "-c", "pass"))
    bad = Step("bad", (sys.executable, "-c", "raise SystemExit(3)"))

    assert (subprocess_runner(ok, {}), subprocess_runner(bad, {})) == (0, 3)


def test_the_summary_names_the_failed_step_and_why() -> None:
    results = [
        StepResult("scrape", "success", 1, 61.0),
        StepResult("parse", "failed", 1, 5.0, "exit code 1"),
        StepResult("dbt", "skipped", 0, 0.0, "needs parse"),
    ]

    text = summarize("daily", DAY, results)

    assert text.splitlines()[0] == "FAILED: daily 2026-11-09"
    assert "parse" in text and "exit code 1" in text and "needs parse" in text


def test_every_daily_command_is_a_make_target_that_exists() -> None:
    makefile = (Path(__file__).parent.parent / "Makefile").read_text(encoding="utf-8")
    for step in daily_steps() + backfill_steps(DAY, DAY):
        if step.command[0] == "make":
            assert f"\n{step.command[1]}:" in makefile, step.command


# ---- the command and the notification ------------------------------------------------------------
def test_the_command_exits_2_for_a_bad_range_and_for_an_unknown_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "t.duckdb"))

    assert main(["flow", "backfill", "--from", "2026-11-05", "--to", "2026-11-01"]) == 2
    assert main(["flow", "backfill"]) == 2
    assert main(["flow", "daily", "--only", "nope"]) == 2


def test_the_message_goes_to_the_configured_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    assert send_telegram("hello", client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert sent[0].url.path == "/bot123:secret/sendMessage"
    assert b'"chat_id":"42"' in sent[0].content.replace(b" ", b"")


def test_without_a_bot_nothing_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not be called")

    assert not send_telegram("x", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_a_failed_delivery_does_not_raise_and_does_not_log_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines: list[str] = []
    sink = logger.add(lines.append, format="{message}")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    try:
        delivered = send_telegram("x", client=httpx.Client(transport=httpx.MockTransport(handler)))
    finally:
        logger.remove(sink)

    assert delivered is False
    assert lines and "secret" not in "".join(lines)
