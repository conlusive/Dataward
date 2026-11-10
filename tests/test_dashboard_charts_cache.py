import threading

import pandas as pd
import pytest

from jobmarket import dashboard_charts as charts


@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    charts._built.clear()


def _bars(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"label": [f"skill {i}" for i in range(len(values))], "value": values})


def test_the_same_data_and_options_give_the_same_chart_object() -> None:
    first = charts.ranked_bars(_bars([0.3, 0.2]), fmt=".0%", unit="x")
    again = charts.ranked_bars(_bars([0.3, 0.2]), fmt=".0%", unit="x")  # a new, equal frame

    assert again is first
    assert len(charts._built) == 1


def test_other_data_or_other_options_build_another_chart() -> None:
    base = charts.ranked_bars(_bars([0.3, 0.2]), fmt=".0%", unit="x")

    assert charts.ranked_bars(_bars([0.3, 0.25]), fmt=".0%", unit="x") is not base  # one cell
    assert charts.ranked_bars(_bars([0.3, 0.2]), fmt=".1%", unit="x") is not base  # an option
    assert charts.ranked_bars(_bars([0.3, 0.2]), fmt=".0%", unit="y") is not base


def test_the_order_of_keyword_arguments_does_not_matter() -> None:
    one = charts.ranked_bars(_bars([0.3]), fmt=".0%", unit="x")
    two = charts.ranked_bars(_bars([0.3]), unit="x", fmt=".0%")

    assert two is one


def test_a_cached_chart_is_the_chart_an_uncached_build_gives() -> None:
    frame = _bars([0.3, 0.2, 0.1])
    cached = charts.ranked_bars(frame, fmt=".1%", unit="Частка")

    uncached = charts.ranked_bars.__wrapped__(frame, fmt=".1%", unit="Частка")  # type: ignore[attr-defined]

    assert cached.to_dict() == uncached.to_dict()  # skipping the validation changed nothing


def test_a_frame_with_cells_that_cannot_be_hashed_is_built_without_the_cache() -> None:
    frame = pd.DataFrame({"label": ["a"], "value": [0.5], "extra": [[1, 2]]})  # a list in a cell

    chart = charts.ranked_bars(frame[["label", "value"]].assign(extra=frame["extra"]), unit="x")

    assert chart is not None and len(charts._built) == 0


def test_the_cache_holds_at_most_its_size_and_drops_the_oldest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(charts, "CACHE_SIZE", 3)
    first = charts.ranked_bars(_bars([1.0]), unit="0")
    for number in range(1, 5):
        charts.ranked_bars(_bars([1.0]), unit=str(number))

    assert len(charts._built) == 3
    assert charts.ranked_bars(_bars([1.0]), unit="0") is not first  # it was dropped, then rebuilt


def test_several_threads_asking_at_once_all_get_a_chart() -> None:
    results: list[object] = []

    def ask() -> None:
        results.append(charts.donut(pd.DataFrame({"label": ["a", "b"], "value": [3, 1]})))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 8 and all(r is not None for r in results)
