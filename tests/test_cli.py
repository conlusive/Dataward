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
