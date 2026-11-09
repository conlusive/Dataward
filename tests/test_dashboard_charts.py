from datetime import date, timedelta
from typing import Any

import pandas as pd
import pytest

pytest.importorskip("altair")

from jobmarket import dashboard_charts as charts  # noqa: E402
from jobmarket import dashboard_theme as t  # noqa: E402


def _wide(days: int = 3) -> pd.DataFrame:
    index = pd.Index([date(2026, 11, 1 + d) for d in range(days)], name="date")
    return pd.DataFrame({"djinni": range(10, 10 + days), "dou": range(5, 5 + days)}, index=index)


def _colour_scale(spec: dict[str, Any], layer: int | None = None) -> dict[str, Any]:
    encoding = spec["layer"][layer]["encoding"] if layer is not None else spec["encoding"]
    scale: dict[str, Any] = encoding["color"]["scale"]
    return scale


def test_a_source_keeps_its_colour_whatever_the_filter_leaves() -> None:
    both = charts.series_domain(["djinni", "dou"])
    only_djinni = charts.series_domain(["djinni"])

    assert both == (["dou", "djinni"], list(t.SERIES[:2]))
    assert only_djinni == (["djinni"], [t.SERIES[1]])  # djinni is not repainted when dou is gone


def test_unknown_series_come_after_the_known_sources_in_a_stable_order() -> None:
    domain, colours = charts.series_domain(["zeta", "dou", "alpha"])

    assert domain == ["dou", "alpha", "zeta"] and colours[0] == t.SERIES[0]
    assert colours[1:] == [t.SERIES[0], t.SERIES[1]]  # the others take the colours in order


def test_the_line_chart_builds_for_one_day_and_for_many() -> None:
    for days in (1, 2, 30):
        spec = charts.lines(_wide(days)).to_dict()
        assert spec["layer"], days


def test_the_line_chart_gives_every_series_its_own_colour_and_a_tooltip_for_all() -> None:
    spec = charts.lines(_wide()).to_dict()

    assert _colour_scale(spec, 0)["domain"] == ["dou", "djinni"]
    tooltips = [
        layer["encoding"].get("tooltip")
        for layer in spec["layer"]
        if "tooltip" in layer["encoding"]
    ]
    assert {tip["title"] for tip in tooltips[0]} >= {"Дата", "dou", "djinni"}


def test_day_ticks_do_not_repeat_a_label() -> None:
    spec = charts.lines(_wide(4)).to_dict()

    axis = spec["layer"][0]["encoding"]["x"]["axis"]
    assert axis["tickCount"] == {"interval": "day", "step": 1}
    assert spec["layer"][0]["encoding"]["x"]["timeUnit"] == "yearmonthdate"


def test_many_days_thin_the_ticks_instead_of_crowding_them() -> None:
    axis = charts.lines(_wide(30)).to_dict()["layer"][0]["encoding"]["x"]["axis"]

    assert axis["tickCount"]["step"] > 1


def test_grouped_columns_use_the_series_order_that_was_asked_for() -> None:
    """Regression: a local variable once shadowed the `order` argument, so the series got dates."""
    frame = pd.DataFrame(
        {
            "date": [date(2026, 11, 1), date(2026, 11, 2)] * 2,
            "series": ["Нові", "Нові", "Закриті", "Закриті"],
            "value": [5, 6, 1, 2],
        }
    )

    spec = charts.grouped_columns(frame, order=["Нові", "Закриті"]).to_dict()

    assert spec["encoding"]["color"]["scale"]["domain"] == ["Нові", "Закриті"]
    assert spec["encoding"]["color"]["scale"]["range"] == list(t.SERIES[:2])
    assert spec["encoding"]["x"]["sort"] == ["01.11", "02.11"]  # the days still sort by date


def test_ranked_bars_keep_the_given_order_cap_the_thickness_and_end_square() -> None:
    frame = pd.DataFrame({"label": ["b", "a", "c"], "value": [3, 2, 1]})

    spec = charts.ranked_bars(frame).to_dict()

    bars = spec["layer"][0]
    assert bars["encoding"]["y"]["sort"] == ["b", "a", "c"]
    assert bars["mark"]["size"] <= 24
    assert not any(key.startswith("cornerRadius") for key in bars["mark"])  # pixel style: square


def test_an_emphasised_bar_is_the_accent_and_the_rest_are_grey() -> None:
    frame = pd.DataFrame({"label": ["a", "b"], "value": [2, 1]})

    spec = charts.ranked_bars(frame, emphasis="a").to_dict()

    condition = spec["layer"][0]["encoding"]["color"]["condition"]
    assert (
        condition["value"] == t.MARK
        and spec["layer"][0]["encoding"]["color"]["value"] == t.MUTED_MARK
    )


def test_ranges_draw_a_span_and_a_dot_with_all_three_values_in_the_tooltip() -> None:
    frame = pd.DataFrame({"label": ["x"], "low": [1000.0], "mid": [2000.0], "high": [3000.0]})

    spec = charts.ranges(frame).to_dict()

    span, dot = spec["layer"]
    assert span["mark"]["type"] == "rule" and dot["mark"]["type"] == "point"
    assert len(span["encoding"]["tooltip"]) == 4


def test_the_trend_and_survey_charts_build() -> None:
    months = pd.DataFrame({"month": [date(2026, 10, 1), date(2026, 11, 1)], "value": [0.1, 0.2]})
    years = pd.DataFrame(
        {"year": [2024, 2025], "low": [1.0, 2.0], "mid": [2.0, 3.0], "high": [3.0, 4.0]}
    )

    assert len(charts.share_trend(months).to_dict()["layer"]) == 3
    assert len(charts.survey_band(years).to_dict()["layer"]) == 3


def test_the_markers_are_squares_in_every_chart() -> None:
    months = pd.DataFrame({"month": [date(2026, 10, 1), date(2026, 11, 1)], "value": [0.1, 0.2]})
    years = pd.DataFrame(
        {"year": [2024, 2025], "low": [1.0, 2.0], "mid": [2.0, 3.0], "high": [3.0, 4.0]}
    )
    ranged = pd.DataFrame({"label": ["x"], "low": [1.0], "mid": [2.0], "high": [3.0]})
    specs = [
        charts.lines(_wide()).to_dict(),
        charts.share_trend(months).to_dict(),
        charts.survey_band(years).to_dict(),
        charts.ranges(ranged).to_dict(),
    ]

    for spec in specs:
        shapes = [
            layer["mark"].get("shape")
            for layer in spec["layer"]
            if layer["mark"]["type"] == "point"
        ]
        assert shapes and set(shapes) <= {"square", None}, spec["layer"]
        assert "square" in shapes


def test_a_ranked_stack_keeps_its_order_and_greys_the_folded_tail() -> None:
    domain, colours = charts.series_domain(
        ["QA", "Java", "Python", "DevOps", "Інші"], keep_order=True
    )

    assert domain == ["QA", "Java", "Python", "DevOps", "Інші"]
    assert colours == [*t.SERIES, t.MUTED_MARK]


def _daily() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [date(2026, 11, 1), date(2026, 11, 2)] * 3,
            "series": ["a", "a", "b", "b", "c", "c"],
            "value": [3, 4, 2, 1, 1, 1],
        }
    )


def test_stacked_bars_are_thin_stack_in_the_given_order_and_carry_no_legend_of_their_own() -> None:
    spec = charts.stacked_bars(_daily(), order=["c", "b", "a"]).to_dict()

    assert spec["mark"]["size"] <= 12 and spec["encoding"]["color"]["legend"] is None
    assert spec["encoding"]["color"]["scale"]["domain"] == ["c", "b", "a"]
    ranks = {row["series"]: row["rank"] for row in spec["datasets"][spec["data"]["name"]]}
    assert ranks == {"c": 0, "b": 1, "a": 2}  # the stack goes from the bottom up


def test_stacked_bars_get_thinner_as_days_pile_up_and_thin_their_labels() -> None:
    many = pd.concat(
        [_daily().assign(date=date(2026, 10, 1) + timedelta(days=n)) for n in range(40)],
        ignore_index=True,
    )

    spec = charts.stacked_bars(many).to_dict()

    assert spec["mark"]["size"] == 5
    assert len(spec["encoding"]["x"]["axis"]["values"]) <= 14


# ---- rings and the activity grid ----------------------------------------------------------------
def _spec(chart: Any) -> dict[str, Any]:
    spec: dict[str, Any] = chart.to_dict()
    return spec


def test_a_donut_keeps_the_order_of_the_parts_and_greys_the_folded_tail() -> None:
    frame = pd.DataFrame({"label": ["dou", "djinni", charts.OTHER], "value": [60, 30, 10]})

    spec = _spec(charts.donut(frame))
    scale = _colour_scale(spec, layer=0)

    assert scale["domain"] == ["dou", "djinni", charts.OTHER]
    assert scale["range"] == [t.SERIES[0], t.SERIES[1], t.MUTED_MARK]
    assert spec["height"] == spec["width"]  # a ring is square, whatever the page width is


def test_a_ring_clamps_the_value_to_a_valid_share() -> None:
    for ratio, expected in ((-0.5, 0.0), (0.42, 0.42), (3.0, 1.0)):
        spec = _spec(charts.ring(ratio, caption="Готовність"))
        values = [row["value"] for row in next(iter(spec["datasets"].values()))]
        assert values[0] == pytest.approx(expected)
        assert sum(values) == pytest.approx(1.0)


def test_the_activity_grid_is_one_cell_per_day_in_five_levels() -> None:
    frame = pd.DataFrame(
        {
            "date": [date(2026, 11, 2), date(2026, 11, 3)],
            "week": [0, 0],
            "weekday": [0, 1],
            "count": [0, 4],
            "level": [0, 2],
        }
    )

    spec = _spec(charts.activity_grid(frame, cell=15))

    assert _colour_scale(spec)["range"] == list(charts.HEAT)
    assert spec["height"] == 7 * 15 and spec["width"] == 15  # a single week so far
