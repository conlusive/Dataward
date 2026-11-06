from pathlib import Path
from typing import Any

import pytest
import yaml

from jobmarket.silver.salary import parse_salary

GOLD = Path(__file__).parent.parent / "data" / "gold" / "salary_cases.yaml"
_GOLD = yaml.safe_load(GOLD.read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = _GOLD["cases"]
FREE_TEXT_CASES: list[dict[str, Any]] = _GOLD["free_text_cases"]


def test_gold_file_is_large_enough_to_mean_something() -> None:
    assert len(CASES) >= 40


def _check(case: dict[str, Any], *, require_context: bool) -> None:
    got = parse_salary(case["text"], require_context=require_context)

    if "expect" in case:
        assert got is None, f"{case['text']!r} should not contain a salary, got {got}"
        return
    assert got is not None, f"{case['text']!r}: nothing parsed"
    assert (got.min, got.max, got.currency) == (case["min"], case["max"], case["currency"])
    assert got.period == case.get("period", "month")
    assert got.net == case.get("net")


@pytest.mark.parametrize("case", CASES, ids=[c["text"][:40] or "<empty>" for c in CASES])
def test_gold_case(case: dict[str, Any]) -> None:
    _check(case, require_context=False)


@pytest.mark.parametrize("case", FREE_TEXT_CASES, ids=[c["text"][:40] for c in FREE_TEXT_CASES])
def test_free_text_case_needs_a_pay_word_nearby(case: dict[str, Any]) -> None:
    _check(case, require_context=True)


def test_context_is_not_required_for_declared_ranges() -> None:
    assert parse_salary("550-700 USD/MONTH") is not None
    assert parse_salary("550-700 USD/MONTH", require_context=True) is None


def test_first_plausible_expression_wins() -> None:
    got = parse_salary("Bonus $50. We pay $3000-4000, plus $500 for relocation.")

    assert got is not None and (got.min, got.max) == (3000, 4000)


def test_matched_fragment_is_reported() -> None:
    got = parse_salary("Salary: 2000-3000$ gross, remote")

    assert got is not None and "2000-3000$" in got.matched
