from datetime import date, timedelta

import pytest

from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_progress as pg

TODAY = date(2026, 11, 9)
NONE = {"total": 60, "seen": 0, "mastered": 0, "due": 0}


def _days(*back: int, count: int = 1) -> dict[str, int]:
    return {(TODAY - timedelta(days=n)).isoformat(): count for n in back}


def _profile(**changes: object) -> pr.Profile:
    return pr.Profile(**changes)  # type: ignore[arg-type]


# ---- experience and levels ---------------------------------------------------------------------
def test_experience_comes_from_what_was_actually_done() -> None:
    profile = _profile(activity=_days(0, 1, count=4))  # 8 answers
    pr.set_skills(profile, ["Python", "SQL"], ["Go"])
    pr.save_vacancy(profile, "a", title="A", company="", url="u", today=TODAY)
    pr.save_vacancy(profile, "b", title="B", company="", url="u", today=TODAY)
    pr.update_saved(profile, "b", status="interview", note="")
    profile.done = {"https://x/1": "2026-11-01", "https://x/2": "2026-11-02"}

    parts = pg.xp_breakdown(profile, {**NONE, "mastered": 3})

    assert parts == {
        "відповіді": 16, "освоєні питання": 30, "пройдені матеріали": 10,
        "збережені вакансії": 4, "відгуки": 5, "відомі навички": 2,
    }  # fmt: skip
    assert sum(parts.values()) == 67


def test_a_new_profile_has_no_experience() -> None:
    assert sum(pg.xp_breakdown(_profile(), NONE).values()) == 0


@pytest.mark.parametrize(
    ("xp", "level", "into", "need"),
    [
        (0, 1, 0, 25),
        (24, 1, 24, 25),
        (25, 2, 0, 75),
        (99, 2, 74, 75),
        (100, 3, 0, 125),
        (225, 4, 0, 175),
    ],
)
def test_levels_start_at_the_squares_of_the_step(xp: int, level: int, into: int, need: int) -> None:
    info = pg.level_info(xp)

    assert (info.level, info.into, info.need) == (level, into, need)
    assert info.ratio == pytest.approx(into / need) and 0 <= info.ratio < 1


def test_a_negative_experience_is_level_one() -> None:
    assert pg.level_info(-5).level == 1


@pytest.mark.parametrize(
    ("level", "key"),
    [
        (1, "tadpole"),
        (2, "tadpole"),
        (3, "froglet"),
        (5, "froglet"),
        (6, "frog"),
        (9, "frog"),
        (10, "king"),
        (40, "king"),
    ],
)
def test_the_frog_grows_with_the_level(level: int, key: str) -> None:
    assert pg.stage(level).key == key


# ---- the streak --------------------------------------------------------------------------------
def test_a_streak_counts_the_days_in_a_row_up_to_today() -> None:
    assert pg.streak(_days(0, 1, 2), TODAY) == 3


def test_yesterday_keeps_the_streak_alive_until_today_is_over() -> None:
    assert pg.streak(_days(1, 2), TODAY) == 2


def test_a_missed_day_breaks_it() -> None:
    assert pg.streak(_days(2, 3, 4), TODAY) == 0
    assert pg.streak(_days(0, 2, 3), TODAY) == 1  # today only: yesterday was missed


def test_a_day_with_no_answers_does_not_count() -> None:
    assert pg.streak({TODAY.isoformat(): 0}, TODAY) == 0 and pg.streak({}, TODAY) == 0


def test_the_longest_streak_remembers_an_old_one() -> None:
    assert pg.longest_streak(_days(0, 10, 11, 12, 13)) == 4
    assert pg.longest_streak({}) == 0


# ---- the frog's mood ---------------------------------------------------------------------------
def test_the_frog_is_pleased_with_the_day() -> None:
    assert pg.mood(_profile(activity=_days(0, count=5)), TODAY) == "party"  # the goal is 5
    assert pg.mood(_profile(activity=_days(0, count=1)), TODAY) == "happy"
    assert pg.mood(_profile(activity=_days(0, count=2), goal=2), TODAY) == "party"


def test_the_frog_dozes_off_after_a_few_days_away_and_is_idle_before_that() -> None:
    assert pg.mood(_profile(activity=_days(3)), TODAY) == "sleepy"
    assert pg.mood(_profile(activity=_days(2)), TODAY) == "idle"
    assert pg.mood(_profile(), TODAY) == "idle"  # a new profile is not sleepy


# ---- achievements ------------------------------------------------------------------------------
def _unlocked(profile: pr.Profile, counts: dict[str, int] = NONE) -> set[str]:
    return {a.key for a in pg.achievements(profile, counts) if a.unlocked}


def test_nothing_is_earned_by_an_empty_profile() -> None:
    assert _unlocked(_profile()) == set()


def test_achievements_follow_the_facts() -> None:
    profile = _profile(activity=_days(0, 1, 2))
    pr.set_skills(profile, [f"S{n}" for n in range(10)], [])
    pr.save_vacancy(profile, "a", title="A", company="", url="u", today=TODAY)
    pr.update_saved(profile, "a", status="offer", note="")
    profile.done = {f"https://x/{n}": "2026-11-01" for n in range(3)}

    earned = _unlocked(profile, {**NONE, "mastered": 5})

    assert earned == {
        "first",
        "streak3",
        "learned5",
        "read3",
        "skills10",
        "saved",
        "applied",
        "offer",
    }


def test_every_achievement_says_how_to_earn_it() -> None:
    assert all(a.hint and a.title for a in pg.achievements(_profile(), NONE))


# ---- what to do next ---------------------------------------------------------------------------
def test_a_new_profile_is_asked_for_its_skills_first() -> None:
    steps = pg.next_steps(_profile(), NONE, TODAY)

    assert steps[0].page == "views/profile.py"


def test_due_questions_come_before_the_daily_goal() -> None:
    profile = _profile()
    pr.set_skills(profile, ["Python"], [])

    steps = pg.next_steps(profile, {**NONE, "due": 4}, TODAY)

    assert [s.page for s in steps[:2]] == ["views/practice.py", "views/practice.py"]
    assert "4" in steps[0].text and "5" in steps[1].text


def test_an_endangered_streak_is_mentioned_and_a_met_goal_is_not_asked_again() -> None:
    profile = _profile(activity=_days(1, 2))
    pr.set_skills(profile, ["Python"], [])
    assert "Серія 2 дн." in pg.next_steps(profile, NONE, TODAY)[0].text

    met = _profile(activity=_days(0, count=5))
    pr.set_skills(met, ["Python"], [])
    assert pg.next_steps(met, NONE, TODAY) == []


def test_the_best_skill_to_learn_and_stale_applications_are_suggested() -> None:
    profile = _profile(activity=_days(0, count=5))
    pr.set_skills(profile, ["Python"], [])
    pr.save_vacancy(profile, "a", title="A", company="", url="u", today=TODAY - timedelta(days=5))

    steps = pg.next_steps(profile, NONE, TODAY, top_skill="Docker", unlocks=3)

    assert [s.page for s in steps] == ["views/learn.py", "views/saved.py"]
    assert "Docker" in steps[0].text and "3" in steps[0].text


def test_at_most_four_steps_are_offered() -> None:
    profile = _profile()
    pr.save_vacancy(profile, "a", title="A", company="", url="u", today=TODAY - timedelta(days=9))

    assert len(pg.next_steps(profile, {**NONE, "due": 2}, TODAY, top_skill="Go", unlocks=1)) == 4
