from pathlib import Path
from typing import Any

import pytest
import yaml

from jobmarket.skills.dictionary import DictionaryExtractor
from jobmarket.skills.taxonomy import load_taxonomy

CASES: list[dict[str, Any]] = yaml.safe_load(
    (Path(__file__).parent.parent / "data" / "gold" / "skills_dictionary_cases.yaml").read_text(
        encoding="utf-8"
    )
)["cases"]
EXTRACTOR = DictionaryExtractor(load_taxonomy())


@pytest.mark.parametrize("case", CASES, ids=[c["text"][:50].replace("\n", " ") for c in CASES])
def test_gold_case(case: dict[str, Any]) -> None:
    found = EXTRACTOR.extract(case.get("title", ""), case["text"])

    required = {k for k, v in found.items() if v.importance == "required"}
    nice = {k for k, v in found.items() if v.importance == "nice"}
    assert required == set(case.get("required", []))
    assert nice == set(case.get("nice", []))


def test_confidence_is_lower_when_a_context_word_had_to_confirm_the_skill() -> None:
    sure = EXTRACTOR.extract("", "Django developer").get("django")
    confirmed = EXTRACTOR.extract("", "Backend services written in Go").get("go")

    assert sure is not None and sure.confidence == 1.0
    assert confirmed is not None and confirmed.confidence == 0.8


def test_the_gold_file_is_large_enough_to_mean_something() -> None:
    assert len(CASES) >= 40


def test_an_unambiguous_spelling_wins_over_the_context_confirmed_one() -> None:
    found = EXTRACTOR.extract("", "Golang and Go services").get("go")

    assert found is not None and found.confidence == 1.0
