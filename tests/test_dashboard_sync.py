import io
import json
import tarfile
from pathlib import Path

import pytest

from jobmarket import dashboard_sync as sync

TABLES = {"dim_skill.parquet": b"skills", "fct_market_daily.parquet": b"market"}


def _archive(tmp_path: Path, files: dict[str, bytes], *, folder: str = "Dataward-data") -> str:
    """A tar.gz shaped like a GitHub branch archive; returns its file:// URL."""
    path = tmp_path / "branch.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, body in files.items():
            info = tarfile.TarInfo(f"{folder}/{name}" if folder else name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return path.as_uri()


def _manifest(*tables: str) -> bytes:
    return json.dumps(
        {"exported_at": "2026-11-10", "tables": {name: {} for name in tables}}
    ).encode()


def test_the_tables_of_the_manifest_are_written_and_nothing_else(tmp_path: Path) -> None:
    url = _archive(
        tmp_path,
        {**TABLES, "last_update.json": _manifest("dim_skill", "fct_market_daily"),
         "fct_vacancy_catalog.parquet": b"other people's listings", "notes.txt": b"x"},
    )  # fmt: skip
    target = tmp_path / "export"

    written = sync.sync(url, target)

    assert written == 3
    assert {p.name for p in target.iterdir()} == {*TABLES, "last_update.json"}
    assert (target / "dim_skill.parquet").read_bytes() == b"skills"


def test_the_status_of_the_run_is_published_with_the_tables(tmp_path: Path) -> None:
    url = _archive(tmp_path, {"last_update.json": _manifest(), "status.json": b'{"runs": []}'})
    target = tmp_path / "export"

    sync.sync(url, target)

    assert (target / "status.json").read_bytes() == b'{"runs": []}'


def test_a_table_the_manifest_does_not_name_is_never_written(tmp_path: Path) -> None:
    # the public export names only public tables, so the manifest is the one list of what to show
    url = _archive(
        tmp_path, {**TABLES, "last_update.json": _manifest("dim_skill")}
    )  # fct_market_daily is in the archive but not in the manifest
    target = tmp_path / "export"

    sync.sync(url, target)

    assert (target / "dim_skill.parquet").exists()
    assert not (target / "fct_market_daily.parquet").exists()


def test_paths_that_could_escape_the_folder_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "evil.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name in ("top/last_update.json", "top/dim_skill.parquet", "top/../../escaped.parquet",
                     "top/sub/dim_skill.parquet", "/abs.parquet"):  # fmt: skip
            body = _manifest("dim_skill") if name.endswith(".json") else b"x"
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    target = tmp_path / "export"

    sync.sync(path.as_uri(), target)

    assert {p.name for p in target.iterdir()} == {"last_update.json", "dim_skill.parquet"}
    assert not (tmp_path / "escaped.parquet").exists()


def test_a_download_without_a_manifest_changes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "export"
    target.mkdir()
    (target / "dim_skill.parquet").write_bytes(b"yesterday")

    with pytest.raises(ValueError, match="last_update.json"):
        sync.sync(_archive(tmp_path, dict(TABLES)), target)

    assert (target / "dim_skill.parquet").read_bytes() == b"yesterday"


def test_a_failed_refresh_keeps_the_old_files_and_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "export"
    target.mkdir()
    (target / "dim_skill.parquet").write_bytes(b"yesterday")
    monkeypatch.setenv(sync.URL_ENV, (tmp_path / "missing.tar.gz").as_uri())

    assert sync.sync_from_environment(target) is None  # the host is down: carry on

    assert (target / "dim_skill.parquet").read_bytes() == b"yesterday"


def test_a_corrupt_archive_is_a_failed_refresh_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.tar.gz"
    broken.write_bytes(b"not an archive")
    monkeypatch.setenv(sync.URL_ENV, broken.as_uri())

    assert sync.sync_from_environment(tmp_path / "export") is None


def test_without_a_url_nothing_is_fetched_and_no_thread_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(sync.URL_ENV, raising=False)

    assert sync.sync_from_environment(tmp_path) is None
    assert sync.keep_fresh(tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_the_background_refresh_runs_again_after_its_interval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = _archive(tmp_path, {**TABLES, "last_update.json": _manifest("dim_skill")})
    monkeypatch.setenv(sync.URL_ENV, url)
    target = tmp_path / "export"

    thread = sync.keep_fresh(target, every=0.05)

    assert thread is not None and thread.daemon  # never keeps the server from stopping
    thread.join(timeout=0.5)
    assert (target / "dim_skill.parquet").exists()
