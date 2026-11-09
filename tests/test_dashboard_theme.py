import re

from jobmarket import dashboard_theme as t


def test_the_stylesheet_carries_the_surface_and_the_accent() -> None:
    css = t.css()

    assert css.startswith("<style>") and css.endswith("</style>")
    assert "--bg: #303032" in css and "--accent: #AAA8FF" in css


def test_the_stylesheet_has_balanced_braces() -> None:
    assert t.css().count("{") == t.css().count("}")


def test_a_pill_pairs_a_word_with_an_icon_so_state_is_not_colour_alone() -> None:
    for tone, icon in (("ok", "✓"), ("warn", "▲"), ("bad", "✕"), ("neutral", "●")):
        html = t.pill("текст", tone)
        assert icon in html and "текст" in html


def test_an_unknown_tone_falls_back_to_neutral() -> None:
    assert "●" in t.pill("x", "nonsense")


def test_text_is_escaped_in_every_piece() -> None:
    nasty = '<script>alert("x")</script>'

    for html in (
        t.pill(nasty), t.hero(nasty, nasty, nasty, [t.pill(nasty)]), t.section(nasty, 1),
        t.card_title(nasty, nasty),
    ):  # fmt: skip
        assert "<script>" not in html


def test_the_hero_has_a_title_a_label_and_optional_chips() -> None:
    plain = t.hero("Dataward", "Заголовок")
    full = t.hero("Dataward", "Заголовок", "підзаголовок", [t.pill("ok", "ok")])

    assert '<h1 class="dw-title">Заголовок</h1>' in plain and "dw-pills" not in plain
    assert "підзаголовок" in full and "dw-pills" in full


def test_a_section_label_is_numbered_with_two_digits() -> None:
    assert "<b>07</b>" in t.section("Показники", 7) and "<b>" not in t.section("Показники")


def test_chart_colours_are_a_fixed_pair_and_the_muted_mark_is_not_one_of_them() -> None:
    assert t.SERIES == ("#8481F5", "#E5603B") and t.MUTED_MARK not in t.SERIES
    assert all(re.fullmatch(r"#[0-9A-F]{6}", colour) for colour in (*t.SERIES, t.ACCENT, t.BG))


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_text_and_marks_are_readable_on_the_surfaces() -> None:
    for surface in (t.BG, t.CARD):
        assert _contrast(t.INK_3, surface) >= 4.5  # muted text
        assert _contrast(t.INK, surface) >= 7
    for mark in (*t.SERIES, t.MUTED_MARK):
        assert _contrast(mark, t.CARD) >= 3  # a mark needs 3:1
