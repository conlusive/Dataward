import importlib
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from jobmarket import dashboard_reload as reload


@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "dwtest_mod.py"
    path.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(reload, "_STARTED", time.time() - 1000)  # the "dashboard process" is old
    before = reload._STARTED - 100  # the file was written before the process started
    os.utime(path, (before, before))
    monkeypatch.syspath_prepend(str(tmp_path))
    yield path
    sys.modules.pop("dwtest_mod", None)
    reload._loaded_at.pop("dwtest_mod", None)


def _edit(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    later = time.time() - 10  # an edit after the process started, a moment ago
    os.utime(path, (later, later))


def test_an_edited_module_is_dropped_so_the_next_import_reads_the_new_code(module: Path) -> None:
    assert importlib.import_module("dwtest_mod").VALUE == 1
    assert reload.refresh(prefix="dwtest_") == []  # nothing changed yet

    _edit(module, "VALUE = 2\n")

    assert reload.refresh(prefix="dwtest_") == ["dwtest_mod"]
    assert importlib.import_module("dwtest_mod").VALUE == 2


def test_an_untouched_module_stays_loaded(module: Path) -> None:
    first = importlib.import_module("dwtest_mod")

    reload.refresh(prefix="dwtest_")
    reload.refresh(prefix="dwtest_")

    assert importlib.import_module("dwtest_mod") is first


def test_a_module_is_dropped_once_per_edit(module: Path) -> None:
    importlib.import_module("dwtest_mod")
    reload.refresh(prefix="dwtest_")
    _edit(module, "VALUE = 2\n")

    assert reload.refresh(prefix="dwtest_") == ["dwtest_mod"]
    importlib.import_module("dwtest_mod")
    assert reload.refresh(prefix="dwtest_") == []  # the new copy is not stale until edited again


def test_only_modules_with_the_prefix_are_touched(module: Path) -> None:
    importlib.import_module("dwtest_mod")
    _edit(module, "VALUE = 2\n")

    assert reload.refresh(prefix="unrelated_") == []  # an edited module outside the prefix stays
    assert "dwtest_mod" in sys.modules


def test_a_module_that_imported_the_edited_one_is_dropped_with_it(
    module: Path, tmp_path: Path
) -> None:
    """Regression: the importer kept the old copy of the edited module and served stale code."""
    user = tmp_path / "dwtest_user.py"
    user.write_text("import dwtest_mod\nSEEN = dwtest_mod.VALUE\n", encoding="utf-8")
    long_ago = reload._STARTED - 100
    os.utime(user, (long_ago, long_ago))
    assert importlib.import_module("dwtest_user").SEEN == 1
    _edit(module, "VALUE = 2\n")

    dropped = reload.refresh(prefix="dwtest_")

    assert dropped == ["dwtest_mod", "dwtest_user"]
    assert importlib.import_module("dwtest_user").SEEN == 2
    sys.modules.pop("dwtest_user", None)
    reload._loaded_at.pop("dwtest_user", None)
