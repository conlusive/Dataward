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

    assert "'Tektur'" in css and "clip-path" in css  # a technical face and stepped corners
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

    assert "prefers-reduced-motion" in css and "animation: none !important" in css
    assert 'button[kind="pillsActive"]' in css and 'has([data-baseweb="tag"])' in css


def test_the_pet_card_shows_the_stage_level_and_a_bounded_experience_bar() -> None:
    html = t.pet("<svg></svg>", "Жабеня <b>", 3, 0.4, "40 / 100 XP", ["серія: 2 дн."])

    assert "<svg></svg>" in html and "рівень 3" in html and "width:40%" in html
    assert "&lt;b&gt;" in html and "серія: 2 дн." in html
    assert "width:2%" in t.pet("", "x", 1, 0.0, "", []) and "width:100%" in t.pet(
        "", "x", 1, 3.0, "", []
    )


def test_medals_light_the_earned_ones_and_carry_the_hint() -> None:
    html = t.medals([("Перший крок", "дайте відповідь", True), ("Оффер <i>", "мрія", False)])

    assert html.count('class="dw-medal on"') == 1 and html.count('<span class="dw-medal') == 2
    assert 'title="дайте відповідь"' in html and "&lt;i&gt;" in html


def test_the_frog_has_its_motion_and_the_page_is_never_dimmed_during_a_rerun() -> None:
    css = t.css()

    assert "@keyframes dw-bob" in css and "@keyframes dw-blink-lid" in css
    assert '[data-stale="true"] { opacity: 1 !important' in css  # smoother reruns


def test_every_font_size_comes_from_the_one_scale() -> None:
    """Twenty-one ad-hoc sizes made the page look out of proportion; there are six steps now."""
    css = t.css()
    sizes = re.findall(r"font-size:\s*([^;}]+)", css)

    assert sizes and all(
        s.strip().startswith("var(--fs-") or s.strip().endswith("em") for s in sizes
    ), sizes
    steps = re.findall(r"--fs-([a-z0-9]+):\s*([0-9.]+)rem", css)
    assert [name for name, _ in steps] == ["xs", "sm", "md", "lg", "xl", "2xl"]
    values = [float(v) for _, v in steps]
    assert values == sorted(values) and values[0] >= 0.75 and values[-1] <= 2.5


def test_the_spacing_scale_is_used_for_the_main_boxes() -> None:
    css = t.css()

    assert "--s4: 1rem" in css and "padding: var(--s4)" in css


def test_cards_in_a_row_are_as_tall_as_the_tallest_and_the_menu_sections_cannot_be_folded() -> None:
    css = t.css()

    assert '[data-testid="stHorizontalBlock"] { align-items: stretch; }' in css
    assert "height: 100%" in css and "min-height: 8rem" in css
    assert '[data-testid="stNavSectionHeader"] { pointer-events: none' in css
    assert (
        '[data-testid="stNavSectionHeader"] [data-testid="stIconMaterial"] { display: none; }'
        in css
    )


# ---- colours per part of the product, the avatar, a to-do, key caps, a vacancy's skills ------
def test_a_section_and_stats_wear_the_colour_of_their_domain() -> None:
    assert 'class="dw-section dw-d-jobs"' in t.section("Вакансії", domain="jobs")
    assert "dw-d-" not in t.section("Без розділу")
    assert "dw-d-" not in t.section("Вигадане", domain="nowhere")  # unknown: no class at all
    assert "dw-d-market" in t.stats([("Відкрито", "1")], "market")
    assert set(t.DOMAINS) == {"jobs", "grow", "market", "system"}


def test_a_todo_says_where_it_leads_and_escapes_the_text() -> None:
    html = t.todo("Практика", "<b>5</b> відповідей", "grow")

    assert "dw-d-grow" in html and "Практика" in html
    assert "<b>5</b>" not in html and "&lt;b&gt;5&lt;/b&gt;" in html


def test_the_avatar_shows_the_name_level_and_a_bounded_bar() -> None:
    low = t.avatar("<svg></svg>", "Ярослав", 3, "Жабеня", 0.0, ["серія 2 дн."])
    high = t.avatar("<svg></svg>", "<i>x</i>", 3, "Жабеня", 7.0, [])

    assert "Ярослав" in low and "рівень 3" in low and "серія 2 дн." in low
    assert 'style="width:2%"' in low  # an empty bar still shows a sliver
    assert 'style="width:100%"' in high and "<i>x</i>" not in high


def test_key_caps_are_one_per_key_and_escaped() -> None:
    html = t.kbd("g", "<")

    assert html.count('class="dw-kbd"') == 2 and "&lt;" in html


def test_skill_rows_mark_required_known_and_unknown_share() -> None:
    html = t.skill_rows(
        [
            {"skill": "Python", "share": 0.5, "required": True, "mine": True},
            {"skill": "Rust", "share": None, "required": False, "mine": False},
        ]
    )

    assert html.count("dw-skillrow") == 2 and html.count(" req") == 1
    assert 'class="dw-name mine">Python' in html and "50% ринку" in html
    assert "— ринку" in html and 'style="width:0%"' in html  # no share: no bar, an honest dash


def test_an_arrival_animation_only_plays_while_the_page_is_entering() -> None:
    css = t.css()
    arrivals = ("dw-fade", "dw-type", "dw-grow")
    rules = re.findall(r"([^{}]+)\{([^{}]*animation:[^{}]*)\}", css)
    arriving = [(sel.strip(), body) for sel, body in rules if any(a in body for a in arrivals)]

    assert arriving  # the arrivals exist ...
    # ... but never on their own: a rerun after a click would play them again and read as lag
    assert all(sel.startswith("html.dw-enter") for sel, _ in arriving)
    assert 'stVerticalBlockBorderWrapper"]:has(' not in css  # :has() over every wrapper is slow


def test_nothing_moves_per_element_on_arrival() -> None:
    css = t.css()

    # a staggered rise or a wipe shows the page being built, which read as jumping
    assert "dw-rise" not in css and "dw-wipe" not in css and "animation-delay" not in css


def test_a_held_page_shows_itself_even_if_the_script_never_releases_it() -> None:
    css = t.css()

    assert re.search(
        r"html:not\(\.dw-go\) [^{]*\{[^}]*opacity: 0;[^}]*dw-unhide 0s 2s forwards", css
    )


def test_the_toolbar_of_tables_and_charts_is_hidden_everywhere() -> None:
    css = t.css()

    assert '[data-testid="stElementToolbar"]' in css and "display: none !important" in css


def test_the_parts_of_the_product_have_the_colours_asked_for() -> None:
    import colorsys

    def hue(name: str) -> float:
        colour = t.DOMAINS[name].lstrip("#")
        red, green, blue = (int(colour[i : i + 2], 16) / 255 for i in (0, 2, 4))
        return colorsys.rgb_to_hsv(red, green, blue)[0] * 360

    assert 235 <= hue("grow") <= 265  # learning: violet
    assert hue("market") <= 12 or hue("market") >= 350  # analytics: red
    assert 40 <= hue("system") <= 52  # the state of the system: yellow
    assert len({t.DOMAINS[name] for name in t.DOMAINS}) == 4  # four parts, four colours


def test_a_ring_is_bounded_labelled_and_coloured_by_its_domain() -> None:
    low, high = t.ring(-1.0, "ціль", "grow"), t.ring(7.0, "<b>x</b>", "jobs")

    assert '--p:0"' in low and "0%" in low and "dw-d-grow" in low
    assert '--p:100"' in high and "dw-d-jobs" in high
    assert "<b>x</b>" not in high and "&lt;b&gt;x&lt;/b&gt;" in high
    assert 'role="img"' in high and "aria-label" in high  # a reader gets the figure as text


def test_the_single_system_item_carries_its_own_colour_since_it_has_no_heading() -> None:
    css = t.css()

    assert "div:nth-child(5) a { border-left: 4px solid var(--dom); }" in css
