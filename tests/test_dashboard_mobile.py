import re
import shutil
import subprocess
from pathlib import Path

import pytest

from jobmarket import dashboard_mobile as mobile
from jobmarket import dashboard_theme as t


def test_the_drawer_is_closed_once_on_a_narrow_screen_only() -> None:
    code = mobile.script()

    assert f"max-width: {mobile.PHONE_MAX_PX}px" in code  # a phone, not a desktop window
    assert 'stSidebarCollapseButton"] button' in code and "close.click()" in code
    assert "window.__dwDrawer" in code  # once per page load, not at every rerun


def test_the_phone_breakpoint_is_the_one_the_stylesheet_uses() -> None:
    css = t.css()

    # the menu buttons are hidden only above the breakpoint (a drawer below it needs them)
    hidden = re.search(
        r"@media \(min-width: (\d+)px\) \{\s*\[data-testid=\"stSidebarCollapseButton\"\]", css
    )
    assert hidden and int(hidden.group(1)) == mobile.PHONE_MAX_PX + 1
    assert f"@media (max-width: {mobile.PHONE_MAX_PX}px)" in css  # the drawer's own rules


def test_the_card_of_a_tapped_vacancy_covers_the_screen_only_on_a_phone() -> None:
    css = t.css()
    phone = css[css.index("a phone: Streamlit") :]  # the rules for a narrow screen

    # off a phone: a sticky card beside the list, and no "back" button
    assert re.search(r"\.st-key-cat_detail, \.st-key-mkt_detail \{ position: sticky", css)
    assert "st-key-cat_close_open, .st-key-mkt_close_open {\n  display: none; }" in css
    # on a phone: a card nobody has tapped is hidden, the tapped one (its button has the key
    # *_close_open) is fixed over the whole screen
    assert re.search(r"\.st-key-cat_detail, \.st-key-mkt_detail \{ display: none; \}", phone)
    tapped = (
        r"\.st-key-cat_detail:has\(\.st-key-cat_close_open\)[^{]*"
        r"\{\s*display: flex; position: fixed"
    )
    assert re.search(tapped, phone)


def test_figures_go_in_pairs_and_every_phone_rule_is_after_the_desktop_ones() -> None:
    css = t.css()

    assert css.rindex("@media (max-width: 640px)") > css.index(".dw-dir { min-height: 12rem")
    assert "calc(50% - 8px) !important" in css  # two metrics to a row


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_drawer_script_is_valid_javascript(tmp_path: Path) -> None:
    body = mobile.script().removeprefix("<script>").removesuffix("</script>")
    source = tmp_path / "drawer.js"
    source.write_text(body, encoding="utf-8")

    result = subprocess.run(["node", "--check", str(source)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_the_typed_line_is_plain_text_on_a_phone() -> None:
    css = t.css()
    phone = css[css.index("a phone: Streamlit") :]

    # it is nowrap and wider than the screen while it types; the phone rule must turn that off
    assert re.search(
        r"html\.dw-enter \.dw-typed \{[^}]*white-space: normal;[^}]*animation: none;", phone
    )
