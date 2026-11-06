from datetime import UTC, date, datetime
from pathlib import Path

from jobmarket.bronze import BronzeStore, WriteOutcome

RUN_DATE = date(2026, 11, 6)
URL = "https://example.com/job/1"


def _write(store: BronzeStore, content: bytes, run_id: str = "r1") -> WriteOutcome:
    return store.write(
        source="dou",
        run_date=RUN_DATE,
        url=URL,
        content=content,
        status=200,
        run_id=run_id,
        fetched_at=datetime(2026, 11, 6, tzinfo=UTC),
    )


def test_first_write_is_new_and_readable(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path)

    assert _write(store, b"<html>a</html>") is WriteOutcome.NEW

    record = store.read("dou", RUN_DATE, URL)
    assert record is not None
    assert record.content == b"<html>a</html>"
    assert record.meta["url"] == URL
    assert record.meta["status"] == 200


def test_rewrite_same_date_reuses_same_files(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path)

    _write(store, b"same", run_id="r1")
    files_after_first = sorted(p.name for p in store.partition_dir("dou", RUN_DATE).iterdir())
    outcome = _write(store, b"same", run_id="r2")
    files_after_second = sorted(p.name for p in store.partition_dir("dou", RUN_DATE).iterdir())

    assert outcome is WriteOutcome.UNCHANGED
    assert files_after_first == files_after_second
    assert len(files_after_second) == 2  # data + meta, no temp leftovers


def test_changed_content_is_reported_as_updated(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path)
    _write(store, b"v1")

    assert _write(store, b"v2") is WriteOutcome.UPDATED
    record = store.read("dou", RUN_DATE, URL)
    assert record is not None and record.content == b"v2"


def test_data_file_without_meta_counts_as_missing(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path)
    _write(store, b"x")
    meta = next(store.partition_dir("dou", RUN_DATE).glob("*.meta.json"))
    meta.unlink()

    assert not store.exists("dou", RUN_DATE, URL)
    assert store.read("dou", RUN_DATE, URL) is None


def test_partitions_are_separated_by_date_and_source(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path)

    assert store.partition_dir("dou", RUN_DATE) == tmp_path / "dou" / "dt=2026-11-06"
    assert store.partition_dir("djinni", RUN_DATE) != store.partition_dir("dou", RUN_DATE)
