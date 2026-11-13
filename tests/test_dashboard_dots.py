import re

from jobmarket import dashboard_dots as dots
from jobmarket import dashboard_theme as t


def _fills(svg: str) -> list[str]:
    return re.findall(r'<circle[^>]* fill="([^"]+)"', svg)


def test_a_ring_lights_the_share_of_its_dots_and_says_the_percent() -> None:
    svg = dots.ring(0.25, "ціль дня", colour="#111111", dots=36)

    assert _fills(svg).count("#111111") == 2 * 9  # a quarter of 36, on both circles
    assert ">25%</text>" in svg and 'aria-label="ціль дня: 25%"' in svg


def test_a_ring_is_clamped_to_a_valid_share() -> None:
    assert ">0%</text>" in dots.ring(-3, "x") and ">100%</text>" in dots.ring(7, "x")
    assert dots.REST not in _fills(dots.ring(7, "x"))  # full: no unlit dot


def test_columns_scale_to_the_tallest_and_a_dot_means_the_same_everywhere() -> None:
    svg = dots.columns(
        ["01.11", "02.11"], [("dou", "#111111", [60, 30]), ("djinni", "#222222", [60, 0])], rows=12
    )

    fills = _fills(svg)
    assert fills.count("#111111") == 6 + 3 and fills.count("#222222") == 6  # 10 per dot
    assert "02.11 · dou: 30" in svg  # the tooltip says the real number, not the dots
    assert "одна крапка ≈ 10" in svg


def test_a_small_part_of_a_column_keeps_one_dot_and_a_zero_gets_none() -> None:
    svg = dots.columns(
        ["d"], [("a", "#111111", [1000]), ("b", "#222222", [1]), ("c", "#333333", [0])]
    )

    fills = _fills(svg)
    assert fills.count("#222222") == 1 and fills.count("#333333") == 0
    assert fills.count("#111111") + fills.count("#222222") <= 12  # never taller than the grid


def test_columns_without_data_are_an_empty_figure_not_an_error() -> None:
    assert "немає даних" in dots.columns([], []) and "<circle" not in dots.columns([], [])
    assert "<circle" not in dots.columns(["d"], [("a", "#111111", [0])])


def test_a_waffle_always_has_a_hundred_dots_and_keeps_a_tiny_part() -> None:
    svg = dots.waffle([("a", "#111111", 995), ("b", "#222222", 4), ("c", "#333333", 1)])

    fills = _fills(svg)
    assert len(fills) == 100
    assert fills.count("#222222") >= 1 and fills.count("#333333") >= 1  # it exists: it is shown
    assert "a: 995 (100%)" in svg or "a: 995 (99%)" in svg  # the tooltip has the true share


def test_a_waffle_of_thirds_adds_up() -> None:
    fills = _fills(dots.waffle([("a", "#1", 1), ("b", "#2", 1), ("c", "#3", 1)]))

    assert len(fills) == 100 and sorted(fills.count(c) for c in ("#1", "#2", "#3")) == [33, 33, 34]


def test_names_are_escaped_everywhere() -> None:
    for svg in (
        dots.ring(0.5, "<b>x</b>"),
        dots.waffle([("<b>x</b>", "#111111", 1)]),
        dots.columns(["<b>d</b>"], [("<b>x</b>", "#111111", [1])]),
        dots.spark([1, 2], caption="<b>x</b>"),
    ):
        assert "<b>" not in svg and "&lt;b&gt;" in svg


def test_a_spark_line_marks_now_with_a_bigger_dot_and_survives_a_flat_series() -> None:
    svg = dots.spark([5, 5, 5], colour=t.ACCENT)

    radii = re.findall(r' r="([^"]+)"', svg)
    assert len(radii) == 3 and float(radii[-1]) > float(radii[0])
    assert "<circle" not in dots.spark([])


def test_every_column_carries_its_total_and_its_day_so_nobody_counts_dots() -> None:
    svg = dots.columns(
        ["01.11", "02.11"], [("dou", "#111111", [6000, 3000]), ("djinni", "#222222", [1378, 0])]
    )

    assert ">7\u00a0378</text>" in svg and ">3\u00a0000</text>" in svg  # the fact, in digits
    assert ">01.11</text>" in svg and ">02.11</text>" in svg  # every day is named
    assert "одна крапка ≈ 615" in svg  # and what one dot is worth is written on the figure


def test_many_columns_label_every_nth_but_always_the_last() -> None:
    days = [f"{d:02d}.11" for d in range(1, 31)]
    svg = dots.columns(days, [("a", "#111111", [10.0] * 30)])

    assert ">30.11</text>" in svg and ">01.11</text>" in svg and ">02.11</text>" not in svg


def test_the_key_names_each_part_with_its_share_and_value() -> None:
    html = dots.key([("djinni", "#111111", 6271), ("<b>dou</b>", "#222222", 1107)])

    assert html.count("dw-key-row") == 2 and ">85%</b>" in html and "6\u00a0271" in html
    assert "<b>dou</b>" not in html and "&lt;b&gt;dou&lt;/b&gt;" in html
    assert dots.key([]) == ""


def test_a_balance_puts_arrivals_above_the_axis_and_departures_below_it() -> None:
    svg = dots.balance(
        ["01.11", "02.11"], ("Нові", "#111111", [20, 0]), ("Закриті", "#222222", [10, 30]), rows=6
    )

    ups = [float(y) for y in re.findall(r'cy="([\d.]+)"[^>]* fill="#111111"', svg)]
    downs = [float(y) for y in re.findall(r'cy="([\d.]+)"[^>]* fill="#222222"', svg)]
    axis = float(re.search(r'<line [^>]*y1="([\d.]+)"', svg).group(1))  # type: ignore[union-attr]
    assert ups and all(y < axis for y in ups) and downs and all(y > axis for y in downs)
    assert len(downs) == 2 + 6  # 10 is a third of the peak 30: two dots; 30 fills six
    assert ">30</text>" in svg and "02.11 · Закриті: 30" in svg


def test_a_balance_without_data_is_an_empty_figure() -> None:
    assert "<circle" not in dots.balance([], ("a", "#1", []), ("b", "#2", []))
    assert "<circle" not in dots.balance(["d"], ("a", "#1", [0]), ("b", "#2", [0]))


def test_a_flow_row_has_closed_on_the_left_new_on_the_right_and_the_numbers_at_the_ends() -> None:
    html = dots.flow(
        ["12.11", "13.11"], [361, 20], [163, 0], new_colour="#111111", closed_colour="#222222"
    )

    assert html.count("dw-flow-row") == 2 and "одна крапка ≈ 26" in html  # 361 / 14
    assert html.count("background:#111111") == 14 + 1  # the peak fills 14, 20 keeps one
    assert html.count("background:#222222") == 6  # 163 is 6 dots, 0 has none
    assert ">361</b>" in html and ">163</b>" in html


def test_a_flow_without_data_is_empty_and_names_are_escaped() -> None:
    assert dots.flow([], [], [], new_colour="#1", closed_colour="#2") == ""
    assert "<b>d</b>" not in dots.flow(["<b>d</b>"], [1], [1], new_colour="#1", closed_colour="#2")
