"""Method A: find taxonomy skills in a vacancy by dictionary lookup (no model, no network).

Spellings go into a trie that is walked once per word start, so cost grows with the text, not with
the 2000 spellings. Ambiguous words ("Go", "R", "Spring") only count when written with the exact
case AND a context word is nearby. Skills in "nice to have" sections are marked ``nice``; sections
that list benefits are ignored.
"""

import re
from dataclasses import dataclass
from typing import Any

from jobmarket.skills.taxonomy import Skill, Taxonomy

CONTEXT_WINDOW = 80
_TERMINAL = "$"

_NICE_HEADING = re.compile(
    r"nice[- ]to[- ]have|(?:will|would|could) be a plus|is a plus|are a plus|\ba plus\b|bonus"
    r"|preferred|desirable|good to have|advantages?\b|буде плюсом|буде перевагою|перевагою"
    r"|бажано|бонусом|додатково|буде корисн|будет плюсом",
    re.IGNORECASE,
)
_SKIP_HEADING = re.compile(
    r"we offer|what we offer|our offer|benefits|perks|compensation|working conditions|conditions"
    r"|ми пропонуємо|що ми пропонуємо|пропонуємо|умови|бенефіт|переваги роботи|компенсац"
    r"|we provide|what you get|why join|why us",
    re.IGNORECASE,
)
_REQUIRED_HEADING = re.compile(
    r"requirements?|required|must[- ]have|qualifications?|we expect|what we expect|about you"
    r"|your profile|skills|responsibilit|duties|tasks|what you will|you will|tech stack|technolog"
    r"|stack|вимоги|ми очікуємо|очікуємо|навички|обов.язки|завдання|що потрібно|ваші задачі"
    r"|кого ми шукаємо|про проєкт|про проект|about the project|the role|project",
    re.IGNORECASE,
)
_HEADING_MAX = 90


@dataclass(frozen=True)
class Found:
    skill_id: str
    importance: str  # "required" | "nice"
    confidence: float


@dataclass(frozen=True)
class _Spelling:
    skill: Skill
    exact_case: str | None  # the spelling must appear with exactly this text
    needs_context: bool


def _is_boundary_before(text: str, index: int) -> bool:
    return index == 0 or not (text[index - 1].isalnum() or text[index - 1] in "_+#")


def _is_boundary_after(text: str, end: int, alias: str) -> bool:
    if end >= len(text):
        return True
    follower = text[end]
    if follower.isalnum() or follower == "_":
        return False
    # "C" must not match inside "C++" / "C#"; "Java" may be followed by punctuation.
    return not (follower in "+#" and alias[-1] not in "+#")


class DictionaryExtractor:
    def __init__(self, taxonomy: Taxonomy) -> None:
        self._trie: dict[str, Any] = {}
        self._context: dict[str, re.Pattern[str]] = {}
        for skill in taxonomy.skills.values():
            exact = skill.exact_case
            for spelling in skill.spellings:
                is_exact = exact == spelling
                entry = _Spelling(
                    skill=skill,
                    exact_case=(skill.case or skill.name) if is_exact else None,
                    # Only the bare ambiguous word needs a context word, not "AWS Lambda".
                    needs_context=skill.strict and spelling == skill.ambiguous_word,
                )
                node = self._trie
                for char in spelling:
                    node = node.setdefault(char, {})
                node[_TERMINAL] = entry
            if skill.strict and skill.context:
                words = "|".join(re.escape(w) for w in skill.context)
                self._context[skill.id] = re.compile(
                    rf"(?<![a-z0-9])(?:{words})(?![a-z0-9])", re.IGNORECASE
                )

    def _matches(self, text: str) -> list[tuple[Skill, int, int, bool]]:
        """(skill, start, end, context_confirmed) for every accepted mention in ``text``."""
        lowered = text.lower()
        found: list[tuple[Skill, int, int, bool]] = []
        i = 0
        while i < len(lowered):
            if not _is_boundary_before(lowered, i):
                i += 1
                continue
            node = self._trie
            best: tuple[int, _Spelling] | None = None
            j = i
            while j < len(lowered) and lowered[j] in node:
                node = node[lowered[j]]
                j += 1
                entry = node.get(_TERMINAL)
                if entry is not None and _is_boundary_after(lowered, j, lowered[i:j]):
                    best = (j, entry)
            if best is None:
                i += 1
                continue
            end, spelling = best
            if spelling.exact_case is not None and text[i:end] != spelling.exact_case:
                i += 1
                continue
            confirmed = False
            if spelling.needs_context:
                # The skill's own word is excluded, otherwise "go" would vouch for itself.
                around = (
                    lowered[max(0, i - CONTEXT_WINDOW) : i]
                    + " "
                    + lowered[end : end + CONTEXT_WINDOW]
                )
                if not self._context[spelling.skill.id].search(around):
                    i += 1
                    continue
                confirmed = True
            found.append((spelling.skill, i, end, confirmed))
            i = end
        return found

    def extract(self, title: str, description: str) -> dict[str, Found]:
        """Skills of one vacancy: the title counts as required, the description by its sections."""
        result: dict[str, Found] = {}

        def add(skill: Skill, importance: str, confirmed: bool) -> None:
            confidence = 0.8 if confirmed else 1.0
            previous = result.get(skill.id)
            if previous is None or (previous.importance == "nice" and importance == "required"):
                result[skill.id] = Found(skill.id, importance, confidence)

        for skill, _, _, confirmed in self._matches(title):
            add(skill, "required", confirmed)

        section = "required"
        for line in description.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            heading = self._heading(stripped)
            if heading is not None and not self._matches(stripped):
                section = heading
                continue
            if section == "skip" or self._skipped_label(stripped):
                continue
            importance = (
                "nice" if section == "nice" or _NICE_HEADING.search(stripped) else "required"
            )
            for skill, _, _, confirmed in self._matches(stripped):
                add(skill, importance, confirmed)
        return result

    @staticmethod
    def _heading(line: str) -> str | None:
        """The section a heading opens, or None when the line is ordinary text.

        A heading is short: "Requirements", "Nice to have", "What we offer:". A line with content
        after a colon ("Skills: React, TypeScript") or a longer sentence ("Strong knowledge of
        Python and SQL skills") is text, never a heading.
        """
        if line[0] in "-•*–—·▪●":
            return None
        words = len(line.split())
        if not ((line.endswith(":") and words <= 9) or words <= 4):
            return None
        if re.search(r"[.;,!?]$", line):
            return None
        for name, pattern in (
            ("skip", _SKIP_HEADING),
            ("nice", _NICE_HEADING),
            ("required", _REQUIRED_HEADING),
        ):
            if pattern.search(line):
                return name
        return None

    @staticmethod
    def _skipped_label(line: str) -> bool:
        """ "Benefits: gym, English courses": a benefits label followed by content."""
        label, separator, content = line.partition(":")
        return bool(
            separator
            and content.strip()
            and len(label.split()) <= 6
            and _SKIP_HEADING.search(label)
        )
