"""The public dashboard's copy of the data: fetch the nightly export, swap it in, repeat.

The container has no volume with the export. The nightly workflow publishes the *public* export
(without the third-party listings) to the ``data`` branch; this module downloads that branch as an
archive, keeps only the files the archive's own manifest (``last_update.json``) names, and replaces
the files in the data directory one by one, so a page never reads a half-written file. A failed
download leaves what is there untouched. With no ``DASHBOARD_DATA_URL`` nothing happens: a local run
reads the export it built itself.
"""

import io
import json
import logging
import os
import re
import tarfile
import tempfile
import threading
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

MANIFEST: Final = "last_update.json"
STATUS: Final = "status.json"  # the run's health, shown on the "Стан системи" page
URL_ENV: Final = "DASHBOARD_DATA_URL"
REFRESH_SECONDS: Final = (
    20 * 60
)  # the export is published hourly; a sleeping host re-fetches on start
FIRST_REFRESH_SECONDS: Final = 60  # the image has the data of its build: refresh once it is calm
STALE_SECONDS: Final = 2 * 3600  # older than this at a start: fetch before serving, not after
DIR_ENV: Final = "DASHBOARD_DATA_DIR"
DEFAULT_DIR: Final = (
    "data/export"  # the same default as dashboard_data.data_dir (a test keeps them equal)
)
MAX_BYTES: Final = 100 * 1024 * 1024
TIMEOUT_SECONDS: Final = 30
_TABLE_FILE: Final = re.compile(r"^[A-Za-z0-9_]+\.parquet$")

log = logging.getLogger(__name__)


def _files(archive: tarfile.TarFile) -> dict[str, bytes]:
    """The regular files directly under the archive's top folder (``name-branch/file``).

    GitHub wraps a branch in one folder; anything deeper, any link and any name that is not a plain
    table file, the manifest or the status is ignored, so a crafted archive cannot write elsewhere.
    """
    files: dict[str, bytes] = {}
    total = 0
    for member in archive:
        parts = Path(member.name).parts
        if not member.isfile() or len(parts) != 2:
            continue
        name = parts[1]
        if name not in (MANIFEST, STATUS) and not _TABLE_FILE.match(name):
            continue
        total += member.size
        if total > MAX_BYTES:
            raise ValueError("the archive is larger than the limit")
        handle = archive.extractfile(member)
        if handle is not None:
            files[name] = handle.read()
    return files


def fetch(url: str) -> dict[str, bytes]:
    """Download the archive at ``url``; returns the manifest and the tables it lists."""
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310  (our own URL from the environment)
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("the download is larger than the limit")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        files = _files(archive)
    if MANIFEST not in files:
        raise ValueError(f"the archive has no {MANIFEST}")
    listed = set(json.loads(files[MANIFEST])["tables"])
    # a table the manifest does not name is not published data (a private one never is named)
    return {
        name: body
        for name, body in files.items()
        if name in (MANIFEST, STATUS) or Path(name).stem in listed
    }


def _replace(directory: Path, name: str, body: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=".sync-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
        os.replace(temporary, directory / name)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def sync(url: str, directory: Path) -> int:
    """Fetch the export and put it in ``directory``; returns how many files were written.

    The manifest goes last: a reader that sees the new manifest finds the new tables.
    """
    files = fetch(url)
    directory.mkdir(parents=True, exist_ok=True)
    for name in sorted(files, key=lambda n: n == MANIFEST):
        _replace(directory, name, files[name])
    return len(files)


def sync_from_environment(directory: Path) -> int | None:
    """``sync`` with the URL of ``DASHBOARD_DATA_URL``; ``None`` if there is none or it failed."""
    url = os.environ.get(URL_ENV)
    if not url:
        return None
    try:
        written = sync(url, directory)
    except (OSError, ValueError, KeyError, tarfile.TarError, json.JSONDecodeError) as error:
        log.warning("the data could not be refreshed, the old files stay: %s", error)
        return None
    log.info("the data was refreshed: %d files", written)
    return written


def keep_fresh(
    directory: Path, every: float = REFRESH_SECONDS, first_after: float = FIRST_REFRESH_SECONDS
) -> threading.Thread | None:
    """Refresh the data ``first_after`` seconds from now, then every ``every`` seconds.

    Runs in a background thread (``None``: no URL set). The first refresh is not immediate: the
    image already holds the export of its build, and the first visitors should have the CPU.
    """
    if not os.environ.get(URL_ENV):
        return None
    stop = threading.Event()

    def loop() -> None:
        wait = first_after
        while not stop.wait(wait):
            sync_from_environment(directory)
            wait = every

    thread = threading.Thread(target=loop, name="dashboard-data-refresh", daemon=True)
    thread.start()
    return thread


def is_stale(directory: Path, now: datetime, max_age: float = STALE_SECONDS) -> bool:
    """No export here, an unreadable manifest, or one exported more than ``max_age`` seconds ago.

    An image carries the export of its build. A host that slept for days, or an old image, would
    otherwise serve that for the first minute after it wakes (no catalog yet, old numbers).
    """
    try:
        manifest = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
        exported = datetime.fromisoformat(str(manifest["exported_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        return True
    if exported.tzinfo is None:
        exported = exported.replace(tzinfo=UTC)
    return (now - exported).total_seconds() > max_age


def main() -> None:
    """Entry point of the container start: fetch before the server starts if the data is stale.

    Fresh data (an image built minutes ago) starts at once; the background refresh takes over.
    Nothing heavy is imported here: a start on a small plan is mostly Python importing.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    directory = Path(os.environ.get(DIR_ENV) or DEFAULT_DIR)
    if not is_stale(directory, datetime.now(UTC)):
        log.info("the data in %s is fresh: starting with it", directory)
        return
    if sync_from_environment(directory) is None and os.environ.get(URL_ENV):
        log.warning("starting with the data that is already in %s", directory)


if __name__ == "__main__":
    main()
