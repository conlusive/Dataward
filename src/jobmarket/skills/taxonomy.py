"""The skill taxonomy: loading from YAML and validation."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TAXONOMY_FILE = Path(__file__).with_name("taxonomy.yaml")
_SKILL_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class TaxonomyError(Exception):
    """The taxonomy file breaks one of its rules; the message lists every problem."""


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    category: str
    parent: str | None
    aliases: tuple[str, ...]
    strict: bool
    context: tuple[str, ...]
    case: str | None  # exact spelling required for the alias equal to ``case`` (any case otherwise)
    name_is_alias: bool

    @property
    def spellings(self) -> tuple[str, ...]:
        """Every text that identifies the skill, lower-cased."""
        names = ([self.name] if self.name_is_alias else []) + list(self.aliases)
        return tuple(dict.fromkeys(n.lower() for n in names))

    @property
    def exact_case(self) -> str | None:
        """The spelling (lower-cased) that must be matched with the exact case, if any."""
        if self.case:
            return self.case.lower()
        return self.name.lower() if self.strict else None

    @property
    def ambiguous_word(self) -> str:
        """The bare word that is also ordinary language ("go", "spark"); strict skills only."""
        return (self.case or self.name).lower()


@dataclass(frozen=True)
class Taxonomy:
    categories: tuple[str, ...]
    skills: dict[str, Skill]


def validate(raw: dict[str, Any]) -> list[str]:
    """Every rule violation in a parsed taxonomy file, as readable messages."""
    problems: list[str] = []
    categories = raw.get("categories") or []
    entries = raw.get("skills") or []
    ids: dict[str, int] = {}
    owners: dict[str, set[str]] = {}

    for entry in entries:
        sid = str(entry.get("id", ""))
        if not _SKILL_ID.match(sid):
            problems.append(f"{sid!r}: id must be a lower-case slug")
        ids[sid] = ids.get(sid, 0) + 1
        if not entry.get("name"):
            problems.append(f"{sid}: name is missing")
        if entry.get("category") not in categories:
            problems.append(f"{sid}: unknown category {entry.get('category')!r}")
        if entry.get("strict") and not entry.get("context"):
            problems.append(f"{sid}: a strict skill needs `context` words")
        aliases = [str(a) for a in entry.get("aliases") or []]
        if any(not a.strip() for a in aliases):
            problems.append(f"{sid}: empty alias")
        lowered = [a.lower() for a in aliases]
        if len(set(lowered)) != len(lowered):
            problems.append(f"{sid}: repeated alias")
        names = ([str(entry.get("name", ""))] if entry.get("name_is_alias", True) else []) + aliases
        for spelling in {n.lower() for n in names if n}:
            owners.setdefault(spelling, set()).add(sid)

    problems += [f"{sid!r}: id used {count} times" for sid, count in ids.items() if count > 1]
    for spelling, who in sorted(owners.items()):
        if len(who) > 1:
            problems.append(f"alias {spelling!r} belongs to several skills: {sorted(who)}")
    for entry in entries:
        parent = entry.get("parent")
        if parent and (parent not in ids or parent == entry.get("id")):
            problems.append(f"{entry.get('id')}: parent {parent!r} does not exist")
    return problems


def load_taxonomy(path: Path = TAXONOMY_FILE) -> Taxonomy:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = validate(raw)
    if problems:
        raise TaxonomyError("; ".join(problems))
    skills = {
        e["id"]: Skill(
            id=e["id"],
            name=e["name"],
            category=e["category"],
            parent=e.get("parent"),
            aliases=tuple(str(a) for a in e.get("aliases") or []),
            strict=bool(e.get("strict", False)),
            context=tuple(str(c) for c in e.get("context") or []),
            case=e.get("case"),
            name_is_alias=bool(e.get("name_is_alias", True)),
        )
        for e in raw["skills"]
    }
    return Taxonomy(categories=tuple(raw["categories"]), skills=skills)
