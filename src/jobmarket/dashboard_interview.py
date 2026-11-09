"""Interview practice: a bank of questions and a spaced-repetition schedule (Leitner boxes).

No Streamlit import. A question you know moves up a box and comes back later; one you do not know
goes back to box 1 and comes back tomorrow. Progress is kept in the profile
(``Profile.practice``: question id -> box, due date, times seen).
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

BANK_FILE = Path(__file__).with_name("interview_questions.yaml")
LEVELS = ("junior", "middle", "senior")
RATINGS = ("know", "partial", "dont")
RATING_LABELS = {"know": "Знаю", "partial": "Частково", "dont": "Не знаю"}
BOXES = 5
DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}  # days until a question in this box comes back
MASTERED_BOX = 4  # from this box on a question counts as learned


class BankError(Exception):
    """The question file is malformed."""


@dataclass(frozen=True)
class Question:
    id: str
    skill: str
    level: str
    question: str
    answer: str


def load_bank(path: Path = BANK_FILE) -> list[Question]:
    """Every question, checked: unique ids, a known level, nothing empty."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    bank: list[Question] = []
    seen: set[str] = set()
    for item in raw.get("questions", []):
        try:
            question = Question(
                id=str(item["id"]), skill=str(item["skill"]), level=str(item["level"]),
                question=str(item["question"]).strip(), answer=str(item["answer"]).strip(),
            )  # fmt: skip
        except KeyError as error:
            raise BankError(f"a question lacks {error}: {item}") from error
        if question.id in seen:
            raise BankError(f"duplicate question id {question.id}")
        if question.level not in LEVELS:
            raise BankError(f"{question.id}: unknown level {question.level!r}")
        if not (question.question and question.answer and question.skill):
            raise BankError(f"{question.id}: an empty field")
        seen.add(question.id)
        bank.append(question)
    return bank


def review(entry: dict[str, Any] | None, rating: str, today: date) -> dict[str, Any]:
    """The new state of a question after an answer: its box, when it is due, how often it was seen.

    "know" moves it up a box, "partial" keeps the box, "dont" sends it back to box 1; a question
    seen for the first time starts in box 1.
    """
    if rating not in RATINGS:
        raise ValueError(f"unknown rating: {rating!r}")
    box = entry["box"] if entry else 1
    box = min(box + 1, BOXES) if rating == "know" else (1 if rating == "dont" else box)
    box = max(1, min(box, BOXES))
    return {
        "box": box,
        "due": (today + timedelta(days=DAYS[box])).isoformat(),
        "seen": (entry.get("seen", 0) if entry else 0) + 1,
        "last": today.isoformat(),
    }


def is_due(entry: dict[str, Any], today: date) -> bool:
    try:
        return date.fromisoformat(str(entry.get("due"))) <= today
    except ValueError:
        return True  # an unreadable date means "ask again"


def build_session(
    bank: list[Question],
    practice: dict[str, dict[str, Any]],
    *,
    today: date,
    skills: set[str] | None = None,
    levels: set[str] | None = None,
    size: int = 10,
) -> list[Question]:
    """Today's questions: the ones that are due first (oldest due first), then new ones.

    ``skills`` and ``levels`` narrow the bank (None means all). The new ones are shuffled with a
    seed taken from the date, so a session is the same all day and different tomorrow.
    """
    pool = [
        q for q in bank
        if (skills is None or q.skill in skills) and (levels is None or q.level in levels)
    ]  # fmt: skip
    due = sorted(
        (q for q in pool if q.id in practice and is_due(practice[q.id], today)),
        key=lambda q: (str(practice[q.id].get("due")), q.id),
    )
    fresh = sorted((q for q in pool if q.id not in practice), key=lambda q: q.id)
    random.Random(today.toordinal()).shuffle(fresh)
    return (due + fresh)[:size]


def counts(
    bank: list[Question], practice: dict[str, dict[str, Any]], today: date
) -> dict[str, int]:
    """How many questions exist, were seen, are learned and are due today."""
    ids = {q.id for q in bank}
    known = {qid: entry for qid, entry in practice.items() if qid in ids}
    return {
        "total": len(bank),
        "seen": len(known),
        "mastered": sum(1 for e in known.values() if e["box"] >= MASTERED_BOX),
        "due": sum(1 for e in known.values() if is_due(e, today)),
    }


def progress(
    bank: list[Question], practice: dict[str, dict[str, Any]], today: date
) -> pd.DataFrame:
    """Per skill: ``skill``, ``total`` questions, ``seen``, ``mastered`` and ``due`` today."""
    rows: dict[str, dict[str, int]] = {}
    for q in bank:
        row = rows.setdefault(q.skill, {"total": 0, "seen": 0, "mastered": 0, "due": 0})
        row["total"] += 1
        entry = practice.get(q.id)
        if entry:
            row["seen"] += 1
            row["mastered"] += int(entry["box"] >= MASTERED_BOX)
            row["due"] += int(is_due(entry, today))
    frame = pd.DataFrame(
        [{"skill": skill, **row} for skill, row in rows.items()],
        columns=["skill", "total", "seen", "mastered", "due"],
    )
    return frame.sort_values(
        ["mastered", "seen", "skill"], ascending=[False, False, True]
    ).reset_index(drop=True)


def skills_in_bank(bank: list[Question]) -> list[str]:
    """The skills that have questions, in the order of the bank."""
    return list(dict.fromkeys(q.skill for q in bank))
