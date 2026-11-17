import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from jobmarket import rearm
from jobmarket.rearm import Run, choose_flow, next_start, superseded

ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 11, 17, 21, 40, tzinfo=UTC)


def _run(
    run_id: int, ago: timedelta, title: str = "fresh", conclusion: str | None = "success"
) -> Run:
    return Run(
        id=run_id,
        created_at=NOW - ago,
        title=title,
        status="completed" if conclusion else "in_progress",
        conclusion=conclusion,
    )


def test_the_next_start_is_the_next_seventeen_past() -> None:
    assert next_start(datetime(2026, 11, 17, 21, 40, tzinfo=UTC)) == datetime(
        2026, 11, 17, 22, 17, tzinfo=UTC
    )
    assert next_start(datetime(2026, 11, 17, 21, 5, tzinfo=UTC)) == datetime(
        2026, 11, 17, 21, 17, tzinfo=UTC
    )


def test_a_start_less_than_ten_minutes_away_waits_for_the_following_hour() -> None:
    # 21:10 -> 21:17 is only seven minutes: a run that has just ended must not be followed at once
    assert next_start(datetime(2026, 11, 17, 21, 10, tzinfo=UTC)) == datetime(
        2026, 11, 17, 22, 17, tzinfo=UTC
    )
    assert next_start(datetime(2026, 11, 17, 23, 55, tzinfo=UTC)) == datetime(
        2026, 11, 18, 0, 17, tzinfo=UTC
    )


def test_only_the_newest_run_carries_the_chain_on() -> None:
    mine = _run(1, timedelta(minutes=30))

    assert not superseded(mine, [mine, _run(0, timedelta(hours=2))])  # nothing newer
    assert superseded(mine, [mine, _run(2, timedelta(minutes=5), conclusion=None)])  # a newer one
    assert not superseded(mine, [mine])


def test_a_full_sweep_is_started_when_none_succeeded_in_a_day() -> None:
    runs = [_run(1, timedelta(hours=1)), _run(2, timedelta(hours=30), "daily")]

    assert choose_flow(NOW, runs) == "daily"


def test_no_sweep_is_started_after_a_successful_one_within_the_day() -> None:
    assert choose_flow(NOW, [_run(1, timedelta(hours=19), "daily")]) == "fresh"


def test_a_failed_sweep_is_not_retried_every_hour() -> None:
    failed_lately = [_run(1, timedelta(hours=2), "daily", conclusion="failure")]
    failed_long_ago = [_run(1, timedelta(hours=7), "daily", conclusion="failure")]

    assert choose_flow(NOW, failed_lately) == "fresh"  # wait: the sites are not asked again at once
    assert choose_flow(NOW, failed_long_ago) == "daily"
    assert choose_flow(NOW, [_run(1, timedelta(hours=1), "daily", conclusion=None)]) == "fresh"


def test_a_run_without_a_sweep_in_its_history_starts_one() -> None:
    assert choose_flow(NOW, []) == "daily"


class _Clock:
    """A clock the test moves: ``sleep`` advances it, so a wait of an hour takes no time."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def sleep(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _main(
    monkeypatch: pytest.MonkeyPatch,
    runs: list[Run],
    later: list[Run] | None = None,
    pings: list[datetime] | None = None,
) -> list[tuple[str, ...]]:
    """Run ``main`` against fake runs; ``later`` is what the list looks like after the wait."""
    clock = _Clock(NOW)
    calls: list[tuple[str, ...]] = []
    lists = iter([runs, later if later is not None else runs])
    monkeypatch.setenv("RUN_ID", "1")
    monkeypatch.setattr(rearm, "fetch_runs", lambda: next(lists))

    def record(*args: str) -> str:
        calls.append(args)
        return ""

    sink = pings if pings is not None else []
    monkeypatch.setattr(rearm, "_gh", record)
    monkeypatch.setattr(rearm, "ping", lambda *a: sink.append(clock.now))
    monkeypatch.setattr(time, "sleep", clock.sleep)
    monkeypatch.setattr(
        rearm, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: clock.now)})
    )
    assert rearm.main() == 0
    return calls


def test_the_chain_waits_and_then_starts_the_next_run(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [_run(1, timedelta(minutes=35)), _run(2, timedelta(hours=3), "daily")]

    calls = _main(monkeypatch, runs)

    assert calls == [("workflow", "run", "pipeline-daily.yml", "--ref", "main", "-f", "flow=fresh")]


def test_a_run_that_was_overtaken_while_it_waited_starts_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mine = _run(1, timedelta(minutes=35))
    sweep = _run(2, timedelta(hours=3), "daily")
    newer = _run(3, timedelta(minutes=1), conclusion=None)

    assert _main(monkeypatch, [mine, sweep], later=[newer, mine, sweep]) == []


def test_the_workflow_hands_the_chain_a_token_that_can_only_start_workflows() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "pipeline-daily.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["rearm"]

    assert job["permissions"] == {"actions": "write", "contents": "read"}
    assert job["needs"] == ["scrape", "publish-data"]  # after the run, whatever its result
    assert "!cancelled()" in job["if"]  # a failed run must not end the chain
    assert "jobmarket.rearm" in job["steps"][-1]["run"]
    # the job that waits an hour is outside the groups that queue the jobs that write
    assert "concurrency" not in workflow and "concurrency" not in job
    assert workflow["jobs"]["scrape"]["concurrency"]["cancel-in-progress"] is False
    assert workflow["permissions"] == {"contents": "read"}  # everything else stays read-only
    assert "'fresh' || 'daily'" in workflow["run-name"]  # the title names the flow


def test_the_site_is_asked_after_it_every_few_minutes_while_the_chain_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pings: list[datetime] = []

    _main(monkeypatch, [_run(1, timedelta(minutes=35))], pings=pings)

    # waits from 21:40 to 22:17: 37 minutes, so a first ping at once and then every 8 minutes
    gaps = [b - a for a, b in zip(pings, pings[1:], strict=False)]
    assert len(pings) >= 4 and pings[0] == NOW
    assert all(timedelta(minutes=8) <= gap < timedelta(minutes=10) for gap in gaps)  # under 15 min


def test_a_site_that_does_not_answer_does_not_stop_the_chain(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(*args: object, **kwargs: object) -> object:
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)

    rearm.ping("https://example.invalid")

    assert "did not answer" in capsys.readouterr().out
