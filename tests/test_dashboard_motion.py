import re
import shutil
import subprocess
from pathlib import Path

import pytest

from jobmarket import dashboard_motion as motion


def test_the_script_switches_the_enter_class_on_when_the_address_changes() -> None:
    code = motion.script()

    assert "classList.add('dw-enter')" in code and "classList.remove('dw-enter')" in code
    assert "location.pathname" in code  # a new page, not a rerun of the same one


def test_the_page_is_held_while_it_is_built_and_shown_when_the_run_ends() -> None:
    code = motion.script()

    assert "classList.remove('dw-go')" in code and "classList.add('dw-go')" in code
    assert "history.pushState" in code  # the hold starts with the address, not 150 ms later
    assert "data-test-script-state" in code and "notRunning" in code  # the app's own run state
    assert "MutationObserver" in code and f'"quiet": {motion.QUIET_MS}' in code  # lazy widgets
    assert "data-stale" in code  # a second opinion: released once nothing is stale any more
    assert (
        f'"cap": {motion.MAX_HOLD_MS}' in code and motion.MAX_HOLD_MS <= 2000
    )  # CSS frees it at 2 s


def test_a_rerun_of_the_same_page_does_not_start_the_arrival_again() -> None:
    code = motion.script()

    assert "window.__dwPath === location.pathname) return" in code  # remembered across script runs
    assert "window.__dwMotion()" in code  # an earlier watcher is stopped before a new one starts


def test_the_class_stays_long_enough_for_the_slowest_arrival_and_no_longer() -> None:
    css_typing_ms = 1200 + 2 * 700  # the typed line, then two blinks of the caret

    assert css_typing_ms <= motion.ENTER_MS <= 4000
    assert re.search(rf'"ms": {motion.ENTER_MS}', motion.script())


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_script_is_valid_javascript(tmp_path: Path) -> None:
    body = motion.script().removeprefix("<script>").removesuffix("</script>")
    source = tmp_path / "motion.js"
    source.write_text(body, encoding="utf-8")

    result = subprocess.run(["node", "--check", str(source)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
