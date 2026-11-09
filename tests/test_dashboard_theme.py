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


def test_chart_colours_are_four_fixed_ones_and_the_muted_mark_is_not_one_of_them() -> None:
    assert t.SERIES == ("#8481F5", "#E5603B", "#26A08F", "#B58A1F")
    assert t.MUTED_MARK not in t.SERIES and len(set(t.SERIES)) == 4
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


def test_skill_tags_mark_the_required_ones_and_escape_the_text() -> None:
    html = t.chips(["Python", "<b>x</b>", "SQL"], ["Python"])

    assert '<span class="dw-chip req">Python</span>' in html
    assert '<span class="dw-chip">SQL</span>' in html and "<b>" not in html
    assert t.chips([]) == ""


def test_a_fact_list_leaves_out_empty_values_and_escapes_the_rest() -> None:
    html = t.facts([("Компанія", "Acme <i>"), ("Де", ""), ("Рівень", "senior")])

    assert "<dt>Компанія</dt><dd>Acme &lt;i&gt;</dd>" in html and "Де" not in html
    assert t.facts([("a", "")]) == ""


def test_a_sidebar_label_is_escaped() -> None:
    assert "&lt;" in t.side_label("<x>") and "dw-side-label" in t.side_label("Пошук")


def test_the_style_is_pixel_and_terminal() -> None:
    css = t.css()

    assert "'Tiny5'" in css and "clip-path" in css  # pixel type and stepped corners
    assert "prefers-reduced-motion" in css  # the blinking cursor can be switched off


def test_bracket_statistics_are_escaped_and_arrive_one_after_another() -> None:
    html = t.stats([("Відкрито", "6 710"), ("<b>x</b>", "1")])

    assert "<em>Відкрито:</em><b>6 710</b>" in html and "<b>x</b>" not in html
    assert 'style="--i:0"' in html and 'style="--i:1"' in html


def test_the_pulse_strip_has_a_square_per_run_with_a_label() -> None:
    html = t.pulse([("09.11: success", "ok"), ("10.11: failed", "bad"), ("x", "nonsense")])

    assert html.count("<span") == 3 and 'class="ok"' in html and 'class="bad"' in html
    assert 'title="09.11: success"' in html and 'class="neutral"' in html


def test_a_legend_lists_the_series_with_their_colours_in_order() -> None:
    html = t.legend(["dou", "<i>djinni</i>"], [t.SERIES[0], t.SERIES[1]])

    assert html.index("dou") < html.index("djinni") and t.SERIES[1] in html
    assert "<i>djinni</i>" not in html  # the name is escaped


def test_the_typed_line_has_its_whole_text_for_readers() -> None:
    html = t.typed("вакансії · навички")

    assert "вакансії · навички" in html and "--chars:18ch" in html


def test_a_hero_can_type_its_subtitle() -> None:
    assert "dw-typed" in t.hero("a", "b", "line", typed_subtitle=True)
    assert "dw-typed" not in t.hero("a", "b", "line")


def test_a_direction_tile_shows_its_share_and_skills_and_is_escaped() -> None:
    html = t.direction_tile(2, "<QA>", "294", 0.07, ["Python", "SQL"])

    assert "&lt;QA&gt;" in html and "294" in html and "width:7%" in html
    assert "Python" in html and 'style="--i:2"' in html
    assert "width:2%" in t.direction_tile(0, "x", "1", 0.0, [])  # never an invisible meter
    assert "width:100%" in t.direction_tile(0, "x", "1", 7.0, [])


def test_a_vacancy_tile_says_when_the_company_or_salary_is_missing() -> None:
    bare = t.vacancy_tile(0, "Dev", "", "", [])
    full = t.vacancy_tile(1, "Dev", "Acme", "2 000 $", ["Python"])

    assert "компанія не вказана" in bare and "dw-vac-pay" not in bare
    assert "Acme" in full and "2 000 $" in full and "Python" in full


def test_active_filters_are_shown_as_tags_or_as_a_quiet_note() -> None:
    assert "фільтри не задано" in t.active_filters([])
    tags = t.active_filters([("Джерело", "dou"), ("Пошук", "<x>")])

    assert tags.count("dw-tag") == 2 and "Джерело: dou" in tags and "&lt;x&gt;" in tags


def test_a_count_badge_is_empty_for_zero() -> None:
    assert t.count_badge(0) == "" and ">3<" in t.count_badge(3)


def test_the_motion_has_a_way_out_and_filters_have_an_active_look() -> None:
    css = t.css()

    assert "@keyframes dw-wipe" in css and "prefers-reduced-motion" in css
    assert "animation: none !important" in css
    assert 'button[kind="pillsActive"]' in css and 'has([data-baseweb="tag"])' in css
