import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from jobmarket import dashboard_keys as keys

APP = Path(__file__).parent.parent / "dashboard" / "app.py"


def test_every_shortcut_goes_to_a_page_that_is_in_the_menu() -> None:
    menu = set(re.findall(r'st\.Page\("[^"]+", title="([^"]+)"', APP.read_text()))

    assert {title for title, _ in keys.PAGES} == menu  # one list of pages, no page without a key


def test_the_keys_after_g_are_single_distinct_letters() -> None:
    letters = [key for _, key in keys.PAGES]

    assert all(re.fullmatch(r"[a-z]", key) and key != "g" for key in letters)
    assert len(set(letters)) == len(letters)


def test_the_help_lists_what_the_script_does() -> None:
    described = {keys_ for keys_, _ in keys.OTHER}

    assert {"/", "?", "Ctrl K", "Space", "Esc"} <= described


def test_the_script_carries_its_data_and_is_safe_to_embed() -> None:
    code = keys.script()
    data = json.loads(code.rsplit("\n)(", 1)[1].removesuffix(");</script>"))

    assert data == keys.config()
    assert code.count("</script>") == 1  # data cannot close the tag early
    assert "window.__dwKeys" in code  # a second run replaces the first listener


def test_keys_are_matched_by_position_so_they_work_in_the_ukrainian_layout() -> None:
    code = keys.script()

    assert "e.code === 'KeyK'" in code and "'Key' + p.key.toUpperCase()" in code
    assert "e.key.toLowerCase" not in code  # a letter by its character would break in a layout


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_script_is_valid_javascript(tmp_path: Path) -> None:
    body = keys.script().removeprefix("<script>").removesuffix("</script>")
    source = tmp_path / "keys.js"
    source.write_text(body, encoding="utf-8")

    result = subprocess.run(["node", "--check", str(source)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_the_release_of_space_cannot_click_the_button_that_appears_under_it() -> None:
    code = keys.script()

    assert "keyup" in code and "swallow" in code  # else one Space reveals and also rates
