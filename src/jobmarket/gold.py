"""The labelled gold set for skills: sampling, a label sheet, import and precision/recall.

The labels are the point of the whole thing: the metrics are only as good as who made them, so every
gold file records `labelled_by` and the metrics page repeats it. This module prepares everything
around that. Labelling blind (no suggestions) keeps the metric honest: a labeller tends to accept a
prepared list, which makes the method that prepared it look better than it is.
"""

import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from jobmarket.silver.store import SilverStore
from jobmarket.skills.taxonomy import Taxonomy

GOLD_DIR = Path("data/gold")
SHEET_FILE = GOLD_DIR / "_label_sheet.md"  # contains vacancy texts: not committed
IDS_FILE = GOLD_DIR / "_skill_ids.md"
GOLD_FILE = GOLD_DIR / "skills_gold.yaml"  # ids and labels only: committed
TEXTS_FILE = (
    GOLD_DIR / "skills_gold_texts.yaml"
)  # the texts, to rerun the regression: not committed
SHEET_DESCRIPTION_CHARS = 3500
_HEADING = re.compile(r"^## (\S+)\s*$")


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    company: str
    description: str
    content_hash: str


NONE_MARK = "= none"  # under Labels: the vacancy asks for no technical skill (labelled, but empty)


@dataclass
class SheetLabels:
    """What a sheet says. A vacancy with no label line at all is *not labelled yet* and is left out
    of ``labels``: it must not be taken for "asks for nothing", which would corrupt the metric."""

    labels: dict[str, set[str]] = field(default_factory=dict)  # labelled vacancy id -> skill ids
    wanted: dict[str, list[str]] = field(default_factory=dict)  # vacancy id -> "+ new skill" lines
    unlabelled: set[str] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Metrics:
    vacancies: int
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        found = self.true_positives + self.false_positives
        return self.true_positives / found if found else 0.0

    @property
    def recall(self) -> float:
        wanted = self.true_positives + self.false_negatives
        return self.true_positives / wanted if wanted else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def sample_candidates(silver: SilverStore, n: int, seed: int) -> list[Candidate]:
    """``n`` vacancies chosen at random (fixed seed) from one representative per duplicate group."""
    rows = silver._con.execute(
        "SELECT v.id, v.title, v.company, v.description_text, v.content_hash "
        "FROM silver_vacancy_groups g JOIN silver_vacancies v ON v.id = g.text_id ORDER BY v.id"
    ).fetchall()
    candidates = [Candidate(*row) for row in rows]
    chosen = random.Random(seed).sample(candidates, min(n, len(candidates)))
    return sorted(chosen, key=lambda c: c.id)


def render_skill_ids(taxonomy: Taxonomy) -> str:
    """A cheat sheet of every skill id by category, for the person labelling."""
    by_category: dict[str, list[str]] = {}
    for skill in taxonomy.skills.values():
        by_category.setdefault(skill.category, []).append(f"`{skill.id}` ({skill.name})")
    lines = ["# Skill ids", ""]
    for category in sorted(by_category):
        lines += [f"## {category}", ", ".join(sorted(by_category[category])), ""]
    return "\n".join(lines)


def render_sheet(candidates: list[Candidate], prefill: dict[str, list[str]] | None = None) -> str:
    blind = prefill is None
    lines = [
        "# Skill gold set: label sheet",
        "",
        "Under **Labels** of each vacancy list, one per line as `- skill-id`, every technical",
        "skill the vacancy asks for (required or nice to have). Ids are in `_skill_ids.md`.",
        "A skill missing from the taxonomy: write `+ its name` (reported as a taxonomy gap).",
        f"A vacancy that asks for no technical skill: write `{NONE_MARK}`.",
        "Left empty, it counts as not labelled yet and is skipped by the import.",
        "Spoken languages, soft skills and benefits are not skills here.",
        "",
        "Labelling blind (nothing is suggested) is slower but keeps the metric honest."
        if blind
        else "**These labels are pre-filled by method A. Check every line, but note that a metric "
        "computed from them favours method A.**",
        "",
    ]
    for c in candidates:
        text = c.description[:SHEET_DESCRIPTION_CHARS]
        lines += [f"## {c.id}", f"**{c.title}** ({c.company})", ""]
        lines += [f"> {line}" for line in text.splitlines() if line.strip()]
        lines += ["", "Labels:"]
        lines += [f"- {skill}" for skill in (prefill or {}).get(c.id, [])]
        lines += ["", "---", ""]
    return "\n".join(lines)


def sheet_ids(sheet: Path = SHEET_FILE) -> set[str]:
    """The vacancy ids listed in a label sheet."""
    return {m.group(1) for line in sheet.read_text(encoding="utf-8").splitlines()
            if (m := _HEADING.match(line))}  # fmt: skip


def parse_sheet(text: str, known_ids: set[str]) -> SheetLabels:
    parsed = SheetLabels()
    current: str | None = None
    in_labels = False
    seen: dict[str, set[str]] = {}  # every vacancy in the sheet -> its label lines
    marked_none: set[str] = set()
    marked: set[str] = set()  # vacancies with at least one label line
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _HEADING.match(line)
        if heading:
            current, in_labels = heading.group(1), False
            seen.setdefault(current, set())
            continue
        if current is None:
            continue
        if line.strip() == "Labels:":
            in_labels = True
        elif line.strip() == "---":
            in_labels = False
        elif in_labels and line.strip() == NONE_MARK:
            marked_none.add(current)
            marked.add(current)
        elif in_labels and line.startswith("- "):
            skill = line[2:].strip()
            if skill and skill not in known_ids:
                parsed.problems.append(f"line {number}: {current}: unknown skill id {skill!r}")
            elif skill:
                seen[current].add(skill)
                marked.add(current)
        elif in_labels and line.startswith("+ "):
            parsed.wanted.setdefault(current, []).append(line[2:].strip())
            marked.add(current)
    for vid, skills in seen.items():
        if vid in marked_none and skills:
            parsed.problems.append(f"{vid}: marked `{NONE_MARK}` but also lists skills")
        if vid in marked:
            parsed.labels[vid] = skills
        else:
            parsed.unlabelled.add(vid)
    return parsed


def write_gold(
    labels: dict[str, set[str]],
    candidates: dict[str, Candidate],
    gold_file: Path,
    texts_file: Path,
    *,
    labelled_by: str,
    wanted: dict[str, list[str]] | None = None,
) -> None:
    gold = [
        {
            "id": vid,
            "content_hash": candidates[vid].content_hash,
            "skills": sorted(labels[vid]),
        }
        for vid in sorted(labels)
        if vid in candidates
    ]
    gold_file.parent.mkdir(parents=True, exist_ok=True)
    # a re-import must not drop the regression floor the owner set by hand
    floor = None
    if gold_file.exists():
        floor = (yaml.safe_load(gold_file.read_text(encoding="utf-8")) or {}).get(
            "regression_min_f1"
        )
    gold_file.write_text(
        "# Labelled skills per vacancy (ids from the taxonomy). Texts are kept separately.\n"
        + yaml.safe_dump(
            {
                "labelled_by": labelled_by,
                **({"regression_min_f1": floor} if floor is not None else {}),
                # skills a vacancy asks for that the taxonomy lacks: the list of what to add next
                "wanted": {
                    v: sorted(w) for v, w in (wanted or {}).items() if v in candidates and w
                },
                "vacancies": gold,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    texts_file.write_text(
        yaml.safe_dump(
            {
                "vacancies": [
                    {
                        "id": vid,
                        "title": candidates[vid].title,
                        "description": candidates[vid].description,
                    }
                    for vid in sorted(labels)
                    if vid in candidates
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def load_labelled_by(gold_file: Path = GOLD_FILE) -> str | None:
    """Who made the labels (None for a file written before this was recorded)."""
    value = yaml.safe_load(gold_file.read_text(encoding="utf-8")).get("labelled_by")
    return str(value) if value else None


def load_wanted(gold_file: Path = GOLD_FILE) -> dict[str, list[str]]:
    """Skills named in the sheet's `+ Name` lines that the taxonomy lacks, per vacancy."""
    data = yaml.safe_load(gold_file.read_text(encoding="utf-8"))
    return {str(v): [str(n) for n in names] for v, names in (data.get("wanted") or {}).items()}


def load_gold(gold_file: Path = GOLD_FILE) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(gold_file.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["vacancies"]}


def score(gold: dict[str, set[str]], predicted: dict[str, set[str]]) -> Metrics:
    """Micro-averaged over (vacancy, skill) pairs; a vacancy not in ``predicted`` found nothing."""
    tp = fp = fn = 0
    for vid, wanted in gold.items():
        found = predicted.get(vid, set())
        tp += len(wanted & found)
        fp += len(found - wanted)
        fn += len(wanted - found)
    return Metrics(len(gold), tp, fp, fn)


def top_errors(
    gold: dict[str, set[str]], predicted: dict[str, set[str]], limit: int = 10
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """The skills most often found wrongly and most often missed."""
    false_positive: dict[str, int] = {}
    missed: dict[str, int] = {}
    for vid, wanted in gold.items():
        found = predicted.get(vid, set())
        for skill in found - wanted:
            false_positive[skill] = false_positive.get(skill, 0) + 1
        for skill in wanted - found:
            missed[skill] = missed.get(skill, 0) + 1
    key = lambda item: (-item[1], item[0])  # noqa: E731
    return sorted(false_positive.items(), key=key)[:limit], sorted(missed.items(), key=key)[:limit]


def render_metrics(
    rows: list[tuple[str, Metrics, float | None]],
    gaps: list[tuple[str, int]],
    errors: dict[str, tuple[list[tuple[str, int]], list[tuple[str, int]]]],
    labelled_by: str | None = None,
) -> str:
    lines = [
        "# Skill extraction metrics",
        "",
        "Measured against the gold set (`data/gold/skills_gold.yaml`),",
        "micro-averaged over (vacancy, skill) pairs. Cost is per 10,000 vacancies, from the",
        "logged token usage.",
        "",
        f"**The labels were made by: {labelled_by or 'not recorded'}.** A metric is only as"
        " independent as its labels.",
        "",
        "| Method | Vacancies | Precision | Recall | F1 | Cost per 10k vacancies |",
        "|---|---|---|---|---|---|",
    ]
    for name, m, cost in rows:
        cost_text = f"${cost:.2f}" if cost is not None else "n/a"
        lines.append(
            f"| {name} | {m.vacancies} | {m.precision:.2f} | {m.recall:.2f} | {m.f1:.2f} "
            f"| {cost_text} |"
        )
    for name, (false_positive, missed) in errors.items():
        lines += [
            "",
            f"## {name}: most frequent mistakes",
            "",
            "Found wrongly: " + (", ".join(f"{s} ({n})" for s, n in false_positive) or "none"),
            "",
            "Missed: " + (", ".join(f"{s} ({n})" for s, n in missed) or "none"),
        ]
    lines += ["", "## Skills the labellers wanted that the taxonomy lacks", ""]
    lines.append(", ".join(f"{s} ({n})" for s, n in gaps) if gaps else "none")
    return "\n".join(lines) + "\n"
