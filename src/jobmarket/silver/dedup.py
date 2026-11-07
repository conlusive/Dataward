"""Finds the same vacancy posted more than once (on both sites, or reposted) and groups it.

Vacancies are only compared inside one company (blocking on a normalised company name). Two of them
are the same posting when

* the titles are almost equal (ratio >= TITLE_MIN) and the descriptions are the same text (equal
  content hash) or very similar (first DESCRIPTION_CHARS characters, ratio >= DESCRIPTION_MIN), or
* the descriptions are near-identical (>= NEAR_IDENTICAL_DESCRIPTION) and the titles are close
  (>= NEAR_TITLE_MIN) with no conflicting seniority: "Senior X" and "X" are one posting reformatted,
  "Middle X" and "Senior X" are two roles that share a template.

An identical description alone is not enough: one company can post the same template for two teams.
Groups are connected components of these pairs; the group id is the id of its oldest member.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from rapidfuzz import fuzz

from jobmarket.silver.model import normalize_text
from jobmarket.silver.text_signals import parse_seniority

TITLE_MIN = 92.0
DESCRIPTION_MIN = 85.0
NEAR_IDENTICAL_DESCRIPTION = 97.0
NEAR_TITLE_MIN = 80.0
DESCRIPTION_CHARS = 2000

# Which source to trust for which part of a merged vacancy.
TEXT_PRIORITY = ("dou", "djinni")  # DOU prints the fuller description
SALARY_PRIORITY = ("djinni", "dou")  # Djinni declares the salary in structured data

MatchKind = Literal["exact", "fuzzy"]
_LEGAL_FORMS = re.compile(
    r"\b(?:llc|ltd|limited|inc|incorporated|corp|corporation|gmbh|sp\.? ?z ?o\.? ?o\.?|s\.?r\.?o\.?"
    r"|тов|тзов|пат|ат|фоп)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DedupInput:
    id: str
    source: str
    title: str
    company: str
    description: str
    content_hash: str
    published_at: date | None
    fetched_at: datetime
    has_salary: bool


@dataclass(frozen=True)
class VacancyGroup:
    group_id: str  # id of the canonical (oldest) member
    members: tuple[str, ...]
    sources: tuple[str, ...]
    match_kind: str  # single | exact | fuzzy
    text_id: str  # member whose title and description represent the group
    salary_id: str | None  # member whose salary represents the group, if any member has one


def normalize_company(name: str) -> str:
    """Company key: no bracketed notes, legal forms or punctuation ("Digis (a Fiverr company)")."""
    without_notes = re.sub(r"\([^)]*\)", " ", name)
    without_forms = _LEGAL_FORMS.sub(" ", without_notes)
    return re.sub(r"[^a-z0-9а-яіїєґ]+", "", without_forms.casefold())


def _seniority_conflict(title_a: str, title_b: str) -> bool:
    a, b = parse_seniority(title_a), parse_seniority(title_b)
    return a is not None and b is not None and a != b


def match_kind(a: DedupInput, b: DedupInput) -> MatchKind | None:
    """How ``a`` and ``b`` (same company) match, or None when they are different postings."""
    title_a, title_b = normalize_text(a.title), normalize_text(b.title)
    title_ratio = fuzz.ratio(title_a, title_b)
    if title_ratio < NEAR_TITLE_MIN:
        return None
    same_level = not _seniority_conflict(a.title, b.title)
    if a.content_hash == b.content_hash:
        return "exact" if title_ratio >= TITLE_MIN or same_level else None

    description_a = normalize_text(a.description)[:DESCRIPTION_CHARS]
    description_b = normalize_text(b.description)[:DESCRIPTION_CHARS]
    description_ratio = fuzz.ratio(description_a, description_b)
    if title_ratio >= TITLE_MIN and description_ratio >= DESCRIPTION_MIN:
        return "fuzzy"
    if description_ratio >= NEAR_IDENTICAL_DESCRIPTION and same_level:
        return "fuzzy"
    return None


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self._parent = {item: item for item in items}

    def find(self, item: str) -> str:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        self._parent[self.find(a)] = self.find(b)


def _age_key(vacancy: DedupInput) -> tuple[date, datetime, str]:
    return (vacancy.published_at or date.max, vacancy.fetched_at, vacancy.id)


def _pick(members: list[DedupInput], priority: tuple[str, ...]) -> DedupInput | None:
    """The oldest member of the most trusted source that has one, in priority order."""
    for source in priority:
        candidates = sorted((m for m in members if m.source == source), key=_age_key)
        if candidates:
            return candidates[0]
    return None


def group_vacancies(vacancies: list[DedupInput]) -> list[VacancyGroup]:
    """Every vacancy ends up in exactly one group; unique vacancies form groups of one."""
    by_id = {v.id: v for v in vacancies}
    blocks: dict[str, list[DedupInput]] = {}
    for vacancy in vacancies:
        blocks.setdefault(normalize_company(vacancy.company), []).append(vacancy)

    components = _UnionFind(list(by_id))
    edges: dict[frozenset[str], MatchKind] = {}
    for block in blocks.values():
        for i, first in enumerate(block):
            for second in block[i + 1 :]:
                kind = match_kind(first, second)
                if kind is not None:
                    components.union(first.id, second.id)
                    edges[frozenset((first.id, second.id))] = kind

    members_by_root: dict[str, list[DedupInput]] = {}
    for vacancy in vacancies:
        members_by_root.setdefault(components.find(vacancy.id), []).append(vacancy)

    groups: list[VacancyGroup] = []
    for members in members_by_root.values():
        members.sort(key=_age_key)
        ids = {m.id for m in members}
        kinds = {kind for pair, kind in edges.items() if pair <= ids}
        text = _pick(members, TEXT_PRIORITY) or members[0]
        salary = _pick([m for m in members if m.has_salary], SALARY_PRIORITY)
        groups.append(
            VacancyGroup(
                group_id=members[0].id,
                members=tuple(m.id for m in members),
                sources=tuple(sorted({m.source for m in members})),
                match_kind="single"
                if len(members) == 1
                else ("exact" if kinds == {"exact"} else "fuzzy"),
                text_id=text.id,
                salary_id=salary.id if salary else None,
            )
        )
    return sorted(groups, key=lambda g: g.group_id)
