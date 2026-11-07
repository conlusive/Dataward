import pytest

from jobmarket.skills.normalize import Normalizer, clean_term
from jobmarket.skills.taxonomy import load_taxonomy

NORMALIZER = Normalizer(load_taxonomy())


@pytest.mark.parametrize(
    ("raw", "skill_id"),
    [
        ("Python", "python"),
        ("  PostgreSQL ", "postgresql"),
        ("postgres", "postgresql"),
        ("Python.", "python"),
        ("(Kubernetes)", "kubernetes"),
        ("k8s", "kubernetes"),
        ("Node.js", "nodejs"),
        ("Go", "go"),  # the model already decided it is the language, so no context is needed
        ("CI/CD", "ci-cd"),
        ("Machine   Learning", "machine-learning"),
    ],
)
def test_exact_spellings_and_aliases(raw: str, skill_id: str) -> None:
    match = NORMALIZER.normalize(raw)

    assert (match.skill_id, match.how) == (skill_id, "exact")


@pytest.mark.parametrize(
    ("raw", "skill_id"), [("Kubernets", "kubernetes"), ("Postgresqll", "postgresql")]
)
def test_a_close_misspelling_is_matched_fuzzily(raw: str, skill_id: str) -> None:
    match = NORMALIZER.normalize(raw)

    assert (match.skill_id, match.how) == (skill_id, "fuzzy") and match.score >= 90


def test_short_names_are_never_matched_fuzzily() -> None:
    assert NORMALIZER.normalize("Gox").skill_id is None


def test_an_unknown_skill_gets_a_suggestion_only_when_something_is_close() -> None:
    near = NORMALIZER.normalize("Kafka Streaming")
    far = NORMALIZER.normalize("Quantum basketry")

    assert near.skill_id is None and near.suggestion is not None
    assert far.skill_id is None and far.suggestion is None


def test_empty_input_matches_nothing() -> None:
    assert NORMALIZER.normalize("  ...  ").skill_id is None


def test_clean_term_collapses_spaces_and_strips_punctuation() -> None:
    assert clean_term("  Spring   Boot, ") == "spring boot"
