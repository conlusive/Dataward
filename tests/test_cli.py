from pathlib import Path

import pytest

from jobmarket.cli import main


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRONZE_DIR", str(tmp_path / "bronze"))
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "test.duckdb"))


def test_fetch_rates_with_nothing_to_fetch_succeeds_without_network() -> None:
    assert main(["fetch-rates"]) == 0


def test_parse_of_an_empty_bronze_succeeds() -> None:
    assert main(["parse", "all", "--run-date", "2026-11-06"]) == 0


def test_unknown_source_is_rejected_by_argparse() -> None:
    with pytest.raises(SystemExit):
        main(["parse", "work_ua", "--run-date", "2026-11-06"])


def test_parse_surveys_of_an_empty_bronze_succeeds() -> None:
    assert main(["parse-surveys"]) == 0


# ---- the hourly flow waits for the day's full sweep ----------------------------------------------
def _sweep(tmp_path: Path, status: str | None) -> None:
    """A database whose daily flow of 2026-11-16 ended with ``status`` (None: it never ran)."""
    from datetime import date

    from jobmarket.ops import OpsStore

    ops = OpsStore(tmp_path / "test.duckdb")
    if status is not None:
        run = ops.start_pipeline("daily", date(2026, 11, 16), trigger="cron", run_url=None)
        ops.finish_pipeline(run, status, [])
    ops.close()


def _fresh(monkeypatch: pytest.MonkeyPatch, *extra: str) -> tuple[int, list[str]]:
    started: list[str] = []

    def record(steps: list, *args: object, **kwargs: object) -> list:  # type: ignore[type-arg]
        started.extend(step.name for step in steps)
        return []

    monkeypatch.setattr("jobmarket.cli.run_flow", record)
    monkeypatch.setattr("jobmarket.cli._publish_run", lambda *a, **k: None)
    code = main(["flow", "fresh", "--run-date", "2026-11-16", *extra])
    return code, started


def test_the_hourly_flow_waits_when_the_day_has_no_full_sweep_and_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sweep(tmp_path, None)

    code, started = _fresh(monkeypatch)

    assert code == 0 and started == []  # nothing scraped, nothing published, no red run


def test_a_sweep_that_failed_does_not_open_the_way_for_the_hourly_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sweep(tmp_path, "failed")

    code, started = _fresh(monkeypatch)

    assert code == 0 and started == []


def test_after_a_successful_sweep_the_hourly_flow_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sweep(tmp_path, "success")

    _, started = _fresh(monkeypatch)

    assert started[:2] == ["scrape", "parse"]


def test_force_runs_the_hourly_flow_before_the_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sweep(tmp_path, None)

    _, started = _fresh(monkeypatch, "--force")

    assert started and started[0] == "scrape"


def test_the_workflow_does_not_fail_when_a_waiting_hour_exported_nothing() -> None:
    workflow = Path(".github/workflows/pipeline-daily.yml").read_text(encoding="utf-8")
    step = workflow[workflow.index("- name: Prepare the public export") :].split("\n\n")[0]

    assert "continue-on-error: true" in step and "export-public" in step
