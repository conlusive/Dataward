"""Label the gold sheet in the terminal, one vacancy at a time.

The labelling stays blind: nothing is suggested from the dictionary, so the metric measures the
method and not the labeller's agreement with it. The only help is lookup of what the labeller typed
(an id, a name or an alias, with near-misses offered when a word is not found). The sheet is written
after every vacancy, so a stop at any moment loses nothing, and the same command resumes where it
stopped. The file format is the one `gold-import` already reads.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import process

from jobmarket.gold import NONE_MARK, SHEET_FILE
from jobmarket.skills.taxonomy import Taxonomy

_HEADING = re.compile(r"^## (\S+)\s*$")
HELP = (
    "id або назва через кому · 0 = жодної технічної навички · +Назва = бракує в таксономії · "
    "?текст = пошук · s = пропустити · b = назад · q = вийти"
)


@dataclass
class Section:
    vid: str
    head: list[str]  # the heading, title and the quoted text, up to the `Labels:` line
    labels: list[str] = field(default_factory=list)
    wanted: list[str] = field(default_factory=list)
    none: bool = False

    @property
    def labelled(self) -> bool:
        return bool(self.labels or self.wanted or self.none)

    def title(self) -> str:
        return next((line for line in self.head if line.startswith("**")), self.vid)

    def text(self) -> list[str]:
        return [
            line[2:] if line.startswith("> ") else line for line in self.head if line[:1] == ">"
        ]


@dataclass
class Stats:
    labelled: int = 0
    total: int = 0
    stopped_at: str | None = None


def read_sheet(text: str) -> tuple[list[str], list[Section]]:
    """The lines before the first vacancy, and the vacancies."""
    preamble: list[str] = []
    sections: list[Section] = []
    current: Section | None = None
    in_labels = closed = False
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            current, in_labels, closed = Section(heading.group(1), [line]), False, False
            sections.append(current)
        elif current is None:
            preamble.append(line)
        elif closed:
            continue  # the blank line after `---` belongs to no vacancy; it is written again
        elif line.strip() == "Labels:":
            in_labels = True
        elif line.strip() == "---":
            in_labels, closed = False, True
        elif in_labels and line.strip() == NONE_MARK:
            current.none = True
        elif in_labels and line.startswith("- "):
            current.labels.append(line[2:].strip())
        elif in_labels and line.startswith("+ "):
            current.wanted.append(line[2:].strip())
        elif not in_labels:
            current.head.append(line)
    return preamble, sections


def write_sheet(preamble: list[str], sections: list[Section]) -> str:
    lines = list(preamble)
    for section in sections:
        lines += section.head
        lines.append("Labels:")
        if section.none:
            lines.append(NONE_MARK)
        lines += [f"- {skill}" for skill in sorted(section.labels)]
        lines += [f"+ {name}" for name in section.wanted]
        lines += ["", "---", ""]
    return "\n".join(lines)


class Lookup:
    """Turns what the labeller typed into skill ids; knows nothing about any vacancy."""

    def __init__(self, taxonomy: Taxonomy) -> None:
        self._names: dict[str, str] = {}
        taken: dict[str, set[str]] = {}
        for skill in taxonomy.skills.values():
            for word in (skill.id, skill.name, *skill.aliases):
                taken.setdefault(word.casefold(), set()).add(skill.id)
        # a word that names two skills is not accepted: the labeller must be exact
        self._names = {word: next(iter(ids)) for word, ids in taken.items() if len(ids) == 1}
        self._ids = set(taxonomy.skills)
        self._display = {skill.id: skill.name for skill in taxonomy.skills.values()}

    def resolve(self, word: str) -> str | None:
        return self._names.get(word.strip().casefold())

    def near(self, word: str, limit: int = 5) -> list[str]:
        """Ids that look like ``word`` (for a typo), best first."""
        found = process.extract(word.strip().casefold(), list(self._names), limit=limit * 3)
        ids: list[str] = []
        for candidate, score, _ in found:
            skill_id = self._names[candidate]
            if score >= 60 and skill_id not in ids:
                ids.append(skill_id)
        return ids[:limit]

    def search(self, text: str, limit: int = 12) -> list[str]:
        needle = text.strip().casefold()
        hits = [
            i for i in sorted(self._ids) if needle in i or needle in self._display[i].casefold()
        ]
        return (hits or self.near(needle))[:limit]

    def describe(self, skill_id: str) -> str:
        return f"{skill_id} ({self._display[skill_id]})"


def _show(section: Section, position: int, total: int, say: Callable[[str], None]) -> None:
    say("\n" + "=" * 78)
    say(f"[{position}/{total}] {section.vid}")
    say(section.title())
    say("")
    for line in section.text():
        say(line)
    say("")
    if section.labelled:
        current = (
            "жодної" if section.none and not section.labels else ", ".join(sorted(section.labels))
        )
        missing = f"; бракує: {', '.join(section.wanted)}" if section.wanted else ""
        say(f"(зараз: {current}{missing})")
    say(HELP)


def label_sheet(
    taxonomy: Taxonomy,
    *,
    sheet: Path = SHEET_FILE,
    relabel: bool = False,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
) -> Stats:
    """Walk the vacancies that are not labelled yet (all of them with ``relabel``)."""
    preamble, sections = read_sheet(sheet.read_text(encoding="utf-8"))
    lookup = Lookup(taxonomy)
    stats = Stats(total=len(sections))
    todo = [i for i, s in enumerate(sections) if relabel or not s.labelled]
    cursor = 0
    while cursor < len(todo):
        index = todo[cursor]
        section = sections[index]
        _show(section, index + 1, len(sections), say)
        try:
            answer = ask("> ").strip()
        except (EOFError, KeyboardInterrupt):
            stats.stopped_at = section.vid
            break
        if not answer:
            continue
        if answer == "q":
            stats.stopped_at = section.vid
            break
        if answer == "s":
            cursor += 1
            continue
        if answer == "b":
            cursor = max(cursor - 1, 0)
            continue
        if answer.startswith("?"):
            hits = lookup.search(answer[1:])
            say(
                "  "
                + ("; ".join(lookup.describe(h) for h in hits) if hits else "нічого не знайдено")
            )
            continue
        parsed = _parse_answer(answer, lookup)
        if isinstance(parsed, str):
            say("  " + parsed)
            continue
        section.labels, section.wanted, section.none = parsed
        sheet.write_text(write_sheet(preamble, sections), encoding="utf-8")
        say("  записано: " + _summary(section))
        cursor += 1
    stats.labelled = sum(s.labelled for s in sections)
    return stats


def _parse_answer(answer: str, lookup: Lookup) -> tuple[list[str], list[str], bool] | str:
    """(skill ids, missing skills, none) or a message saying what to fix (nothing is saved then)."""
    if answer == "0":
        return [], [], True
    ids: list[str] = []
    wanted: list[str] = []
    for word in (w.strip() for w in answer.split(",")):
        if not word:
            continue
        if word.startswith("+"):
            if word[1:].strip():
                wanted.append(word[1:].strip())
            continue
        skill_id = lookup.resolve(word)
        if skill_id is None:
            near = lookup.near(word)
            hint = ("; може: " + ", ".join(near)) if near else ""
            return f"не знайдено «{word}»{hint}. Введи рядок ще раз."
        if skill_id not in ids:
            ids.append(skill_id)
    if not ids and not wanted:
        return "порожньо: введи навички, `0` або `s`."
    return ids, wanted, False


def _summary(section: Section) -> str:
    if section.none and not section.labels:
        return "жодної технічної навички"
    extra = f" (+ бракує: {', '.join(section.wanted)})" if section.wanted else ""
    return ", ".join(sorted(section.labels)) + extra
