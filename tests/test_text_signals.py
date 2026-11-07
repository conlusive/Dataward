from pathlib import Path
from typing import Any

import pytest
import yaml

from jobmarket.silver.text_signals import (
    parse_english_level,
    parse_required_experience,
    parse_seniority,
)

GOLD = yaml.safe_load(
    (Path(__file__).parent.parent / "data" / "gold" / "vacancy_text_cases.yaml").read_text(
        encoding="utf-8"
    )
)
EXPERIENCE: list[dict[str, Any]] = GOLD["experience"]
ENGLISH: list[dict[str, Any]] = GOLD["english"]
SENIORITY: list[dict[str, Any]] = GOLD["seniority"]


def test_gold_file_covers_every_signal_well() -> None:
    assert len(EXPERIENCE) >= 30 and len(ENGLISH) >= 25 and len(SENIORITY) >= 20


@pytest.mark.parametrize("case", EXPERIENCE, ids=[c["text"][:45] or "<empty>" for c in EXPERIENCE])
def test_required_experience(case: dict[str, Any]) -> None:
    expected = None if "expect" in case else case["years"]
    assert parse_required_experience(case["text"]) == expected


@pytest.mark.parametrize("case", ENGLISH, ids=[c["text"][:45] or "<empty>" for c in ENGLISH])
def test_english_level(case: dict[str, Any]) -> None:
    expected = None if "expect" in case else case["level"]
    assert parse_english_level(case["text"]) == expected


@pytest.mark.parametrize("case", SENIORITY, ids=[c["title"][:45] or "<empty>" for c in SENIORITY])
def test_seniority(case: dict[str, Any]) -> None:
    expected = None if "expect" in case else case["level"]
    assert parse_seniority(case["title"]) == expected
