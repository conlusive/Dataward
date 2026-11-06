"""Immutable bronze storage.

Layout: ``{root}/{source}/dt={run_date}/{key_hash}{suffix}`` plus ``{key_hash}.meta.json``.
The path is a pure function of (source, run_date, url), so re-running the same date overwrites
the same files instead of adding new ones. The meta file is written last and acts as the
commit marker: a data file without meta is an incomplete write and is treated as missing.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class WriteOutcome(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class BronzeRecord:
    content: bytes
    meta: dict[str, Any]


def key_hash(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def content_hash(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class BronzeStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def partition_dir(self, source: str, run_date: date) -> Path:
        return self._root / source / f"dt={run_date.isoformat()}"

    def _meta_path(self, source: str, run_date: date, url: str) -> Path:
        return self.partition_dir(source, run_date) / f"{key_hash(url)}.meta.json"

    def exists(self, source: str, run_date: date, url: str) -> bool:
        return self._meta_path(source, run_date, url).is_file()

    def known_urls(self, source: str, since: date) -> set[str]:
        """URLs stored with HTTP 200 in any partition dated ``since`` or later."""
        urls: set[str] = set()
        for partition in (self._root / source).glob("dt=*"):
            try:
                partition_date = date.fromisoformat(partition.name.removeprefix("dt="))
            except ValueError:
                continue
            if partition_date < since:
                continue
            for meta_path in partition.glob("*.meta.json"):
                meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta["status"] == 200:
                    urls.add(meta["url"])
        return urls

    def read(self, source: str, run_date: date, url: str) -> BronzeRecord | None:
        meta_path = self._meta_path(source, run_date, url)
        if not meta_path.is_file():
            return None
        meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        content = (meta_path.parent / meta["file"]).read_bytes()
        return BronzeRecord(content=content, meta=meta)

    def write(
        self,
        *,
        source: str,
        run_date: date,
        url: str,
        content: bytes,
        status: int,
        run_id: str,
        fetched_at: datetime,
        suffix: str = ".html",
    ) -> WriteOutcome:
        previous = self.read(source, run_date, url)
        new_hash = content_hash(content)
        if previous is None:
            outcome = WriteOutcome.NEW
        elif previous.meta["content_hash"] == new_hash:
            outcome = WriteOutcome.UNCHANGED
        else:
            outcome = WriteOutcome.UPDATED

        directory = self.partition_dir(source, run_date)
        directory.mkdir(parents=True, exist_ok=True)
        data_name = f"{key_hash(url)}{suffix}"
        meta = {
            "url": url,
            "status": status,
            "fetched_at": fetched_at.isoformat(),
            "run_id": run_id,
            "content_hash": new_hash,
            "file": data_name,
            "bytes": len(content),
        }
        _atomic_write(directory / data_name, content)
        _atomic_write(
            self._meta_path(source, run_date, url),
            json.dumps(meta, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )
        return outcome
