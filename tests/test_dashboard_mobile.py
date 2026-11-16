import re

from jobmarket import dashboard_theme as t

PHONE_MAX_PX = 768  # Streamlit's own breakpoint between a drawer and a fixed sidebar


def test_the_phone_breakpoint_is_the_one_the_stylesheet_uses() -> None:
    css = t.css()

    # the menu buttons are hidden only above the breakpoint (a drawer below it needs them)
    hidden = re.search(
        r"@media \(min-width: (\d+)px\) \{\s*\[data-testid=\"stSidebarCollapseButton\"\]", css
    )
    assert hidden and int(hidden.group(1)) == PHONE_MAX_PX + 1
    assert f"@media (max-width: {PHONE_MAX_PX}px)" in css  # the drawer's own rules


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


def test_the_typed_line_is_plain_text_on_a_phone() -> None:
    css = t.css()
    phone = css[css.index("a phone: Streamlit") :]

    # it is nowrap and wider than the screen while it types; the phone rule must turn that off
    assert re.search(
        r"html\.dw-enter \.dw-typed \{[^}]*white-space: normal;[^}]*animation: none;", phone
    )
