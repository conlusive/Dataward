import shutil
import subprocess
from pathlib import Path

import pytest

from jobmarket import dashboard_theme as t
from jobmarket import dashboard_tips as tips


def test_the_script_shifts_a_tip_left_by_how_far_it_would_run_past_the_edge() -> None:
    code = tips.script()

    assert "--dx" in code and "innerWidth" in code and "getBoundingClientRect" in code
    assert "mouseover" in code and "focusin" in code  # a pointer and the keyboard
    assert "window.__dwTips" in code  # a second run replaces the first listeners


def test_the_style_reads_the_shift_and_a_phone_menu_is_frosted_glass() -> None:
    css = t.css()

    assert "left: var(--dx, 0)" in css  # the tip text moves with the measured shift
    assert "backdrop-filter: blur(28px) saturate(1.7)" in css and "-webkit-backdrop-filter" in css
    assert "@supports ((backdrop-filter: blur(1px))" in css  # and readable where it cannot blur
    assert (
        '[data-testid="stSidebar"], [data-testid="stHeader"] { background: rgba(' in css
    )  # the bar too
    assert "max-width: 768px" in css  # on a desktop the menu stays panel-less


def test_the_labels_of_the_figures_do_not_wrap() -> None:
    assert ".dw-stat em { color: var(--ink-2); white-space: nowrap;" in t.css()


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_script_is_valid_javascript(tmp_path: Path) -> None:
    body = tips.script().removeprefix("<script>").removesuffix("</script>")
    source = tmp_path / "tips.js"
    source.write_text(body, encoding="utf-8")

    result = subprocess.run(["node", "--check", str(source)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
