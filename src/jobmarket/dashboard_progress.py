"""Progress and play: experience, levels, a streak, the frog's mood, achievements, next steps.

No Streamlit import. Everything is worked out from the saved profile (nothing here is stored
separately), so it cannot drift from the facts and cannot be earned twice: experience comes from
answers given, questions learned, learning resources finished, vacancies saved and applied to, and
skills known.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from math import isqrt

from jobmarket import dashboard_profile as pr

XP_ANSWER, XP_MASTERED, XP_RESOURCE, XP_SAVED, XP_APPLIED, XP_SKILL = 2, 10, 5, 2, 5, 1
LEVEL_STEP = 25  # level n starts at LEVEL_STEP * (n - 1) ** 2 experience
APPLIED_STAGES = {"applied", "interview", "offer"}
SLEEPY_AFTER_DAYS = 3  # this long without an answer and the frog dozes off


@dataclass(frozen=True)
class Level:
    level: int
    xp: int
    into: int  # experience gained inside this level
    need: int  # experience this level takes

    @property
    def ratio(self) -> float:
        return self.into / self.need


@dataclass(frozen=True)
class Stage:
    key: str
    name: str


@dataclass(frozen=True)
class Achievement:
    key: str
    title: str
    hint: str
    unlocked: bool


@dataclass(frozen=True)
class Step:
    text: str
    page: str


def xp_breakdown(profile: pr.Profile, counts: dict[str, int]) -> dict[str, int]:
    """Experience by source; ``counts`` is ``dashboard_interview.counts`` of the profile."""
    applied = sum(1 for entry in profile.saved.values() if entry["status"] in APPLIED_STAGES)
    return {
        "відповіді": XP_ANSWER * sum(profile.activity.values()),
        "освоєні питання": XP_MASTERED * counts["mastered"],
        "пройдені матеріали": XP_RESOURCE * len(profile.done),
        "збережені вакансії": XP_SAVED * len(profile.saved),
        "відгуки": XP_APPLIED * applied,
        "відомі навички": XP_SKILL * len(profile.known()),
    }


def level_info(xp: int) -> Level:
    """The level for an amount of experience: 0 -> 1, 25 -> 2, 100 -> 3, 225 -> 4, ..."""
    xp = max(0, xp)
    level = 1 + isqrt(xp // LEVEL_STEP)
    floor = LEVEL_STEP * (level - 1) ** 2
    ceiling = LEVEL_STEP * level**2
    return Level(level, xp, xp - floor, ceiling - floor)


def stage(level: int) -> Stage:
    """What the frog has grown into: a tadpole at first, a king at level 10."""
    if level >= 10:
        return Stage("king", "Король жаб")
    if level >= 6:
        return Stage("frog", "Жаба")
    if level >= 3:
        return Stage("froglet", "Жабеня")
    return Stage("tadpole", "Пуголовок")


def _days(activity: dict[str, int]) -> set[date]:
    return {date.fromisoformat(day) for day, count in activity.items() if count > 0}


def streak(activity: dict[str, int], today: date) -> int:
    """Days in a row with an answer, up to today; yesterday still counts (today is not over)."""
    days = _days(activity)
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def longest_streak(activity: dict[str, int]) -> int:
    best = run = 0
    previous: date | None = None
    for day in sorted(_days(activity)):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best, previous = max(best, run), day
    return best


def answers_on(profile: pr.Profile, day: date) -> int:
    return profile.activity.get(day.isoformat(), 0)


def mood(profile: pr.Profile, today: date) -> str:
    """party (the goal is met), happy (answered today), sleepy (a few days away), else idle."""
    answered = answers_on(profile, today)
    if answered >= profile.goal:
        return "party"
    if answered:
        return "happy"
    days = _days(profile.activity)
    if days and (today - max(days)).days >= SLEEPY_AFTER_DAYS:
        return "sleepy"
    return "idle"


def achievements(profile: pr.Profile, counts: dict[str, int]) -> list[Achievement]:
    """Every achievement with whether it is earned yet."""
    answers = sum(profile.activity.values())
    longest = longest_streak(profile.activity)
    stages = {entry["status"] for entry in profile.saved.values()}
    mastered = counts["mastered"]
    earned = [
        ("first", "Перший крок", "дайте відповідь на перше питання", answers >= 1),
        ("streak3", "Три дні поспіль", "відповідайте три дні підряд", longest >= 3),
        ("streak7", "Тиждень без пропусків", "серія з 7 днів", longest >= 7),
        ("learned5", "П'ять питань освоєно", "5 питань у 4-й коробці", mastered >= 5),
        ("learned20", "Двадцять питань освоєно", "20 питань у 4-й коробці", mastered >= 20),
        (
            "read3",
            "Три матеріали пройдено",
            "позначте 3 ресурси пройденими",
            len(profile.done) >= 3,
        ),
        (
            "skills10",
            "Десять навичок",
            "додайте 10 навичок, які вмієте",
            len(profile.known()) >= 10,
        ),
        ("saved", "Перша вакансія в профілі", "збережіть вакансію", bool(profile.saved)),
        ("applied", "Перший відгук", "позначте «відгукнувся»", bool(stages & APPLIED_STAGES)),
        ("offer", "Оффер", "позначте вакансію як «оффер»", "offer" in stages),
    ]
    return [Achievement(*item) for item in earned]


def next_steps(
    profile: pr.Profile,
    counts: dict[str, int],
    today: date,
    *,
    top_skill: str | None = None,
    unlocks: int = 0,
) -> list[Step]:
    """What to do now, most useful first (at most four); the page is a path for ``st.page_link``."""
    steps: list[Step] = []
    if not profile.known():
        steps.append(
            Step("Додайте навички, які ви вмієте: за ними рахується збіг", "views/profile.py")
        )
    if counts["due"]:
        steps.append(Step(f"Повторіть питань: {counts['due']}", "views/practice.py"))
    left = profile.goal - answers_on(profile, today)
    if left > 0:
        alive = streak(profile.activity, today)
        tail = (
            f" Серія {alive} дн. під загрозою." if alive and answers_on(profile, today) == 0 else ""
        )
        steps.append(
            Step(f"Дайте ще {left} відповідей, щоб виконати ціль дня.{tail}", "views/practice.py")
        )
    if top_skill and unlocks:
        steps.append(Step(f"Вивчіть {top_skill}: відкриє вакансій — {unlocks}", "views/learn.py"))
    stale_before = (today - timedelta(days=3)).isoformat()
    waiting = [
        e for e in profile.saved.values()
        if e["status"] == "saved" and e["saved_on"] and e["saved_on"] <= stale_before
    ]  # fmt: skip
    if waiting:
        steps.append(Step(f"Збережені вакансії чекають рішення: {len(waiting)}", "views/saved.py"))
    return steps[:4]
