"""A personal profile for the dashboard: skills, a target, saved vacancies and practice progress.

No Streamlit import, so everything here is tested directly. The profile is one small JSON file on
this machine (``data/profile/profile.json``, git-ignored; ``PROFILE_PATH`` moves it). It is written
atomically, readable by the owner only, and a damaged file is set aside instead of crashing the
dashboard. There is no account: this is a single-user tool.

Matching and the learning plan work on the vacancy catalog (``fct_vacancy_catalog``).
"""

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

VERSION = 1
SKILL_STATES = ("know", "learning")  # a skill that is not listed is simply "not mine yet"
STATUSES = ("saved", "applied", "interview", "offer", "rejected")
STATUS_LABELS = {
    "saved": "збережено", "applied": "відгукнувся", "interview": "співбесіда",
    "offer": "оффер", "rejected": "відмова",
}  # fmt: skip
LEVELS = ("", "intern", "junior", "middle", "senior", "lead")
MAX_NAME, MAX_NOTE, MAX_TEXT = 80, 2000, 300
REQUIRED_WEIGHT = 2  # a required skill counts twice in a match
ACTIVITY_DAYS = 400  # how far back the answer history is kept
DEFAULT_GOAL = 5  # answers a day that count as "a good day"


def default_path() -> Path:
    return Path(os.environ.get("PROFILE_PATH") or "data/profile/profile.json")


def _text(value: Any, limit: int) -> str:
    return str(value).strip()[:limit] if value is not None else ""


@dataclass
class Profile:
    name: str = ""
    category: str = ""  # the target direction ("" = any)
    level: str = ""  # the target level ("" = any)
    min_salary: int = 0  # USD a month; 0 = no wish
    remote: bool = False
    skills: dict[str, str] = field(default_factory=dict)  # skill name -> "know" | "learning"
    saved: dict[str, dict[str, str]] = field(default_factory=dict)  # vacancy id -> a snapshot
    practice: dict[str, dict[str, Any]] = field(default_factory=dict)  # question id -> its box
    done: dict[str, str] = field(default_factory=dict)  # learning resource url -> the day finished
    activity: dict[str, int] = field(default_factory=dict)  # day -> answers given that day
    goal: int = DEFAULT_GOAL

    def known(self) -> set[str]:
        return {name for name, state in self.skills.items() if state == "know"}

    def learning(self) -> set[str]:
        return {name for name, state in self.skills.items() if state == "learning"}

    def is_empty(self) -> bool:
        return not (self.skills or self.saved or self.practice or self.category or self.name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": VERSION, "name": self.name, "category": self.category, "level": self.level,
            "min_salary": self.min_salary, "remote": self.remote, "skills": self.skills,
            "saved": self.saved, "practice": self.practice, "done": self.done,
            "activity": self.activity, "goal": self.goal,
        }  # fmt: skip

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Profile":
        """Read what a file holds, coercing every field: a hand-edited file must not crash us."""
        skills = {
            _text(name, MAX_TEXT): state
            for name, state in (raw.get("skills") or {}).items()
            if state in SKILL_STATES and _text(name, MAX_TEXT)
        }
        saved: dict[str, dict[str, str]] = {}
        for vacancy_id, entry in (raw.get("saved") or {}).items():
            if not isinstance(entry, dict):
                continue
            status = entry.get("status")
            saved[_text(vacancy_id, MAX_TEXT)] = {
                "status": status if status in STATUSES else "saved",
                "title": _text(entry.get("title"), MAX_TEXT),
                "company": _text(entry.get("company"), MAX_TEXT),
                "url": _text(entry.get("url"), 1000),
                "note": _text(entry.get("note"), MAX_NOTE),
                "saved_on": _text(entry.get("saved_on"), 10),
            }
        practice = {
            _text(question_id, MAX_TEXT): entry
            for question_id, entry in (raw.get("practice") or {}).items()
            if isinstance(entry, dict) and isinstance(entry.get("box"), int)
        }
        done = {
            _text(url, 1000): _text(day, 10)
            for url, day in (raw.get("done") or {}).items()
            if _text(url, 1000)
        }
        activity: dict[str, int] = {}
        for day, count in (raw.get("activity") or {}).items():
            try:
                date.fromisoformat(str(day))
                activity[str(day)] = max(0, min(int(count), 10_000))
            except (TypeError, ValueError):
                continue
        try:
            goal = max(1, min(int(raw.get("goal") or DEFAULT_GOAL), 50))
        except (TypeError, ValueError):
            goal = DEFAULT_GOAL
        level = raw.get("level")
        try:
            min_salary = max(0, int(raw.get("min_salary") or 0))
        except (TypeError, ValueError):
            min_salary = 0
        return cls(
            name=_text(raw.get("name"), MAX_NAME),
            category=_text(raw.get("category"), MAX_TEXT),
            level=level if level in LEVELS else "",
            min_salary=min_salary,
            remote=bool(raw.get("remote")),
            skills=skills,
            saved=saved,
            practice=practice,
            done=done,
            activity=activity,
            goal=goal,
        )


def load(path: Path | None = None) -> Profile:
    """The saved profile, or an empty one; a damaged file is set aside as ``*.damaged-<time>``."""
    path = path or default_path()
    if not path.exists():
        return Profile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("the profile file is not an object")
        return Profile.from_dict(raw)
    except (ValueError, AttributeError, TypeError, OSError):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        with contextlib.suppress(OSError):
            path.replace(path.with_name(f"{path.name}.damaged-{stamp}"))
        return Profile()


def save(profile: Profile, path: Path | None = None) -> None:
    """Write the profile atomically (a half-written file is never visible), for the owner only."""
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".profile-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(profile.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


# ---- changing a profile (each returns nothing and changes it in place) ---------------------------
def set_skills(profile: Profile, know: list[str], learning: list[str]) -> None:
    """Replace the skill lists; a skill in both counts as known."""
    chosen = {name: "learning" for name in learning}
    chosen.update({name: "know" for name in know})
    profile.skills = chosen


def mark_skill(profile: Profile, skill: str, state: str | None) -> None:
    """Set one skill to "know" or "learning", or forget it with ``None``."""
    if state is None:
        profile.skills.pop(skill, None)
    elif state in SKILL_STATES:
        profile.skills[skill] = state
    else:
        raise ValueError(f"unknown skill state: {state!r}")


def save_vacancy(
    profile: Profile, vacancy_id: str, *, title: str, company: str, url: str, today: date
) -> bool:
    """Bookmark a vacancy as a snapshot (it outlives the catalog); False if already saved."""
    if vacancy_id in profile.saved:
        return False
    profile.saved[vacancy_id] = {
        "status": "saved", "title": _text(title, MAX_TEXT), "company": _text(company, MAX_TEXT),
        "url": _text(url, 1000), "note": "", "saved_on": today.isoformat(),
    }  # fmt: skip
    return True


def update_saved(profile: Profile, vacancy_id: str, *, status: str, note: str) -> None:
    entry = profile.saved.get(vacancy_id)
    if entry is None:
        return
    entry["status"] = status if status in STATUSES else entry["status"]
    entry["note"] = _text(note, MAX_NOTE)


def remove_saved(profile: Profile, vacancy_id: str) -> None:
    profile.saved.pop(vacancy_id, None)


def record_answer(profile: Profile, today: date) -> None:
    """Count one answer given today (the history behind the streak); old days are forgotten."""
    key = today.isoformat()
    profile.activity[key] = profile.activity.get(key, 0) + 1
    cutoff = (today - timedelta(days=ACTIVITY_DAYS)).isoformat()
    profile.activity = {day: n for day, n in profile.activity.items() if day >= cutoff}


def toggle_resource(profile: Profile, url: str, today: date) -> bool:
    """Mark a learning resource finished, or take the mark back; True if it is finished now."""
    if url in profile.done:
        del profile.done[url]
        return False
    profile.done[_text(url, 1000)] = today.isoformat()
    return True


def status_counts(profile: Profile) -> dict[str, int]:
    """How many saved vacancies are in each stage, every stage present."""
    counts = dict.fromkeys(STATUSES, 0)
    for entry in profile.saved.values():
        counts[entry["status"]] += 1
    return counts


# ---- matching a profile against vacancies --------------------------------------------------------
def match(
    skills: list[str], required: list[str], mine: set[str]
) -> tuple[float | None, list[str], list[str]]:
    """(score, skills I have, skills I lack) for one vacancy; the score is None without skills.

    A required skill counts ``REQUIRED_WEIGHT`` times, any other once; the missing ones are
    listed required first, so the first of them is what to learn first.
    """
    if not skills:
        return None, [], []
    must = set(required)
    weight = {name: REQUIRED_WEIGHT if name in must else 1 for name in skills}
    have = [name for name in skills if name in mine]
    missing = sorted(
        (name for name in skills if name not in mine), key=lambda n: (n not in must, n)
    )
    return sum(weight[n] for n in have) / sum(weight.values()), have, missing


def rank_vacancies(
    catalog: pd.DataFrame, profile: Profile, *, only_open: bool = True
) -> pd.DataFrame:
    """The vacancies that suit the target, best match first, with ``match``, ``have``, ``missing``.

    The target narrows by direction, level and remote work; a minimum salary drops only vacancies
    that state a salary below it (most state none, and hiding them would hide the market).
    """
    keep = pd.Series(True, index=catalog.index)
    if only_open:
        keep &= catalog["is_open"]
    if profile.category:
        keep &= catalog["category"] == profile.category
    if profile.level:
        keep &= catalog["seniority"] == profile.level
    if profile.remote:
        keep &= catalog["remote"].fillna(False)
    if profile.min_salary:
        keep &= catalog["salary_top"].isna() | (catalog["salary_top"] >= profile.min_salary)
    chosen = catalog[keep].copy()
    mine = profile.known()
    scored = [
        match(list(s), list(r), mine)
        for s, r in zip(chosen["skills"], chosen["skills_required"], strict=True)
    ]
    chosen["match"] = [score for score, _, _ in scored]
    chosen["have"] = [have for _, have, _ in scored]
    chosen["missing"] = [missing for _, _, missing in scored]
    ranked = chosen.sort_values(
        ["match", "first_listed_on", "title"], ascending=[False, False, True], na_position="last"
    )
    return ranked.reset_index(drop=True)


def readiness(ranked: pd.DataFrame, *, top: int = 20) -> float | None:
    """How ready the profile is for the target: the median match of its ``top`` best vacancies."""
    scores = ranked["match"].dropna().head(top)
    return float(scores.median()) if len(scores) else None


def learning_plan(ranked: pd.DataFrame, mine: set[str], *, top: int = 15) -> pd.DataFrame:
    """What to learn next: ``skill``, ``vacancies`` that ask for it, ``required`` that demand it and
    ``unlocks`` (vacancies where it is the only required skill still missing).

    Skills already known are left out; the order is unlocks first, then demand.
    """
    demand: dict[str, int] = {}
    required: dict[str, int] = {}
    unlocks: dict[str, int] = {}
    for skills, must in zip(ranked["skills"], ranked["skills_required"], strict=True):
        wanted = set(must) or set(skills)  # a vacancy that marks none treats all as required
        lacking = wanted - mine
        for name in set(skills) - mine:
            demand[name] = demand.get(name, 0) + 1
        for name in lacking:
            required[name] = required.get(name, 0) + 1
        if len(lacking) == 1:
            only = next(iter(lacking))
            unlocks[only] = unlocks.get(only, 0) + 1
    rows = [
        {"skill": name, "vacancies": count, "required": required.get(name, 0),
         "unlocks": unlocks.get(name, 0)}
        for name, count in demand.items()
    ]  # fmt: skip
    frame = pd.DataFrame(rows, columns=["skill", "vacancies", "required", "unlocks"])
    return (
        frame.sort_values(["unlocks", "vacancies", "skill"], ascending=[False, False, True])
        .head(top)
        .reset_index(drop=True)
    )


# ---- tables the page edits (the page shows them, these apply the edits back) --------------------
LABEL_TO_STATUS = {label: status for status, label in STATUS_LABELS.items()}


def saved_table(profile: Profile) -> pd.DataFrame:
    """The saved vacancies as an editable table: the stage and the note can change, the rest not."""
    rows = [
        {
            "id": vacancy_id, "Етап": STATUS_LABELS[entry["status"]], "Назва": entry["title"],
            "Компанія": entry["company"], "Нотатка": entry["note"], "Посилання": entry["url"],
            "Збережено": entry["saved_on"], "Видалити": False,
        }
        for vacancy_id, entry in sorted(
            profile.saved.items(), key=lambda item: item[1]["saved_on"], reverse=True
        )
    ]  # fmt: skip
    columns = ["id", "Етап", "Назва", "Компанія", "Нотатка", "Посилання", "Збережено", "Видалити"]
    return pd.DataFrame(rows, columns=columns)


def apply_saved_table(profile: Profile, edited: pd.DataFrame) -> int:
    """Take the stage, note and delete marks of an edited ``saved_table``; returns what changed."""
    changed = 0
    for row in edited.to_dict("records"):
        vacancy_id = str(row["id"])
        entry = profile.saved.get(vacancy_id)
        if entry is None:
            continue
        if row.get("Видалити"):
            remove_saved(profile, vacancy_id)
            changed += 1
            continue
        status = LABEL_TO_STATUS.get(str(row.get("Етап")), entry["status"])
        note = _text(row.get("Нотатка"), MAX_NOTE)
        if (status, note) != (entry["status"], entry["note"]):
            update_saved(profile, vacancy_id, status=status, note=note)
            changed += 1
    return changed


def plan_table(plan: pd.DataFrame, profile: Profile, questions: dict[str, int]) -> pd.DataFrame:
    """The learning plan with two ticks per skill, "Вчу" and "Знаю", and the trainer's questions."""
    rows = [
        {
            "Навичка": row.skill, "Відкриває": row.unlocks, "Обов'язкова у": row.required,
            "Згадується у": row.vacancies, "Питань": questions.get(row.skill, 0),
            "Вчу": profile.skills.get(row.skill) == "learning",
            "Знаю": profile.skills.get(row.skill) == "know",
        }
        for row in plan.itertuples()
    ]  # fmt: skip
    columns = ["Навичка", "Відкриває", "Обов'язкова у", "Згадується у", "Питань", "Вчу", "Знаю"]
    return pd.DataFrame(rows, columns=columns)


def apply_plan_table(profile: Profile, edited: pd.DataFrame) -> int:
    """Take the ticks of an edited ``plan_table``: "Знаю" beats "Вчу"; no tick forgets the skill."""
    changed = 0
    for row in edited.to_dict("records"):
        skill = str(row["Навичка"])
        state = "know" if row.get("Знаю") else "learning" if row.get("Вчу") else None
        if profile.skills.get(skill) != state:
            mark_skill(profile, skill, state)
            changed += 1
    return changed
