"""Maps a skill name written by the LLM (or anyone) onto the taxonomy.

Order, as in the plan: exact spelling, then a close spelling (rapidfuzz ratio >= 90). The planned
embedding step (similarity >= 0.86) needs an embedding model and is left out; a name that matches
nothing is an *unknown* skill and goes to review.
"""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from jobmarket.skills.taxonomy import Taxonomy

FUZZY_MIN = 90.0
SUGGESTION_MIN = 75.0
FUZZY_MIN_LENGTH = 5  # "go" ~ "gb" is noise; short names must match exactly


@dataclass(frozen=True)
class Normalized:
    skill_id: str | None
    how: str | None  # exact | fuzzy | None (unknown)
    score: float
    suggestion: str | None  # best skill id below the fuzzy threshold, for the review list


def clean_term(raw: str) -> str:
    """Lower-cased, single-spaced, without surrounding punctuation."""
    text = re.sub(r"\s+", " ", raw.casefold()).strip()
    return text.strip(" .,;:()[]{}\"'`")


class Normalizer:
    def __init__(self, taxonomy: Taxonomy) -> None:
        self._exact: dict[str, str] = {}
        for skill in taxonomy.skills.values():
            for spelling in skill.spellings:
                self._exact[spelling] = skill.id
        self._spellings = list(self._exact)

    def normalize(self, raw: str) -> Normalized:
        term = clean_term(raw)
        if not term:
            return Normalized(None, None, 0.0, None)
        exact = self._exact.get(term)
        if exact is not None:
            return Normalized(exact, "exact", 100.0, None)
        best = process.extractOne(term, self._spellings, scorer=fuzz.ratio)
        if best is None:
            return Normalized(None, None, 0.0, None)
        spelling, score, _ = best
        if score >= FUZZY_MIN and len(term) >= FUZZY_MIN_LENGTH:
            return Normalized(self._exact[spelling], "fuzzy", float(score), None)
        suggestion = self._exact[spelling] if score >= SUGGESTION_MIN else None
        return Normalized(None, None, float(score), suggestion)
