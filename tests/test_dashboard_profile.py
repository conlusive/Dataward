import json
import os
import stat
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from jobmarket import dashboard_data as dd
from jobmarket import dashboard_profile as pr
from tests.dashboard_fixtures import write_catalog

TODAY = date(2026, 11, 9)


@pytest.fixture
def catalog(tmp_path: Path) -> pd.DataFrame:
    write_catalog(tmp_path)
    frame = dd.read_catalog(tmp_path)
    assert frame is not None
    return frame


def _ids(frame: pd.DataFrame) -> list[str]:
    return list(frame["vacancy_id"])


# ---- the file ----------------------------------------------------------------------------------
def test_a_profile_survives_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "p" / "profile.json"
    profile = pr.Profile(
        name="Ярослав", category="Python", level="middle", min_salary=2500, remote=True
    )
    pr.set_skills(profile, ["Python", "SQL"], ["Docker"])
    pr.save_vacancy(profile, "v1", title="Dev", company="Acme", url="https://x.test/1", today=TODAY)
    profile.practice["python-01"] = {"box": 2, "due": "2026-11-11", "seen": 1, "last": "2026-11-09"}

    pr.save(profile, path)

    assert pr.load(path) == profile


def test_a_missing_file_is_an_empty_profile(tmp_path: Path) -> None:
    assert pr.load(tmp_path / "none.json").is_empty()


def test_the_file_is_private_and_no_temporary_file_is_left(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"

    pr.save(pr.Profile(name="x"), path)

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == ["profile.json"]


def test_a_failed_write_keeps_the_previous_file_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "profile.json"
    pr.save(pr.Profile(name="old"), path)

    def broken(*_: object, **__: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("jobmarket.dashboard_profile.json.dump", broken)
    with pytest.raises(OSError, match="disk full"):
        pr.save(pr.Profile(name="new"), path)

    assert pr.load(path).name == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["profile.json"]


def test_a_damaged_file_is_set_aside_and_an_empty_profile_is_returned(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text("{not json", encoding="utf-8")

    assert pr.load(path).is_empty()

    names = sorted(p.name for p in tmp_path.iterdir())
    assert len(names) == 1 and names[0].startswith("profile.json.damaged-")


def test_a_file_that_is_not_an_object_is_treated_as_damaged(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text("[1, 2]", encoding="utf-8")

    assert pr.load(path).is_empty() and not path.exists()


def test_the_default_path_can_be_moved_with_an_environment_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "mine.json"))
    pr.save(pr.Profile(name="here"))

    assert pr.default_path() == tmp_path / "mine.json" and pr.load().name == "here"


def test_a_hand_edited_file_is_coerced_not_trusted(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "name": "x" * 500,
                "level": "wizard",
                "min_salary": "lots",
                "remote": 1,
                "skills": {"Python": "know", "SQL": "master", "": "know"},
                "saved": {
                    "v1": {"status": "teleported", "title": "T", "note": "n" * 5000},
                    "v2": "not an entry",
                },
                "practice": {"q1": {"box": 3}, "q2": {"box": "high"}, "q3": 7},
            }
        ),
        encoding="utf-8",
    )

    profile = pr.load(path)

    assert len(profile.name) == pr.MAX_NAME and profile.level == "" and profile.min_salary == 0
    assert profile.remote is True and profile.skills == {"Python": "know"}
    assert list(profile.saved) == ["v1"] and profile.saved["v1"]["status"] == "saved"
    assert len(profile.saved["v1"]["note"]) == pr.MAX_NOTE
    assert list(profile.practice) == ["q1"]


# ---- changing it -------------------------------------------------------------------------------
def test_a_skill_in_both_lists_counts_as_known() -> None:
    profile = pr.Profile()

    pr.set_skills(profile, ["Python"], ["Python", "Docker"])

    assert profile.known() == {"Python"} and profile.learning() == {"Docker"}


def test_one_skill_can_be_marked_changed_and_forgotten() -> None:
    profile = pr.Profile()

    pr.mark_skill(profile, "Go", "learning")
    pr.mark_skill(profile, "Go", "know")
    assert profile.skills == {"Go": "know"}
    pr.mark_skill(profile, "Go", None)
    assert profile.skills == {}
    with pytest.raises(ValueError, match="skill state"):
        pr.mark_skill(profile, "Go", "expert")


def test_a_vacancy_is_saved_once_as_a_snapshot() -> None:
    profile = pr.Profile()

    first = pr.save_vacancy(profile, "v1", title="Dev", company="Acme", url="u", today=TODAY)
    again = pr.save_vacancy(profile, "v1", title="Other", company="Z", url="u", today=TODAY)

    assert first is True and again is False
    assert profile.saved["v1"]["title"] == "Dev" and profile.saved["v1"]["saved_on"] == "2026-11-09"
    assert profile.saved["v1"]["status"] == "saved"


def test_a_saved_vacancy_moves_through_the_stages_with_a_note() -> None:
    profile = pr.Profile()
    pr.save_vacancy(profile, "v1", title="Dev", company="", url="u", today=TODAY)

    pr.update_saved(profile, "v1", status="interview", note="  дзвонити в п'ятницю ")
    pr.update_saved(
        profile, "v1", status="teleported", note="x"
    )  # an unknown stage changes nothing
    pr.update_saved(profile, "gone", status="offer", note="")  # an unknown vacancy is ignored

    assert profile.saved["v1"]["status"] == "interview" and profile.saved["v1"]["note"] == "x"
    assert pr.status_counts(profile) == {
        "saved": 0, "applied": 0, "interview": 1, "offer": 0, "rejected": 0,
    }  # fmt: skip
    pr.remove_saved(profile, "v1")
    assert not profile.saved


# ---- matching ----------------------------------------------------------------------------------
def test_a_required_skill_counts_twice_and_the_missing_ones_list_required_first() -> None:
    score, have, missing = pr.match(
        ["Python", "Django", "Docker"], ["Python", "Django"], {"Python"}
    )

    assert score == pytest.approx(2 / 5)  # weights 2 + 2 + 1
    assert have == ["Python"] and missing == ["Django", "Docker"]


def test_a_match_is_whole_when_everything_is_known_and_zero_when_nothing_is() -> None:
    assert pr.match(["A", "B"], ["A"], {"A", "B"})[0] == 1.0
    assert pr.match(["A", "B"], ["A"], set())[0] == 0.0
    assert pr.match(["A", "B"], [], {"A"})[0] == 0.5  # no required ones: every skill weighs 1


def test_a_vacancy_without_skills_has_no_match() -> None:
    assert pr.match([], [], {"A"}) == (None, [], [])


def test_vacancies_are_ranked_by_how_well_the_profile_fits(catalog: pd.DataFrame) -> None:
    profile = pr.Profile()
    pr.set_skills(profile, ["Python"], [])

    ranked = pr.rank_vacancies(catalog, profile)

    assert _ids(ranked) == ["v2", "v1", "v6", "v3", "v5"]  # the closed v4 is left out
    assert ranked["match"].iloc[0] == pytest.approx(2 / 3)
    assert pd.isna(ranked["match"].iloc[-1])  # no skills: last
    assert ranked["missing"].iloc[1] == ["Django", "Docker"]


def test_the_target_narrows_the_ranking(catalog: pd.DataFrame) -> None:
    def ids(**target: object) -> list[str]:
        return sorted(_ids(pr.rank_vacancies(catalog, pr.Profile(**target))))  # type: ignore[arg-type]

    assert ids(category="Python") == ["v1", "v2"]
    assert ids(level="senior") == ["v1", "v6"]
    assert ids(remote=True) == ["v1", "v3", "v6"]


def test_a_minimum_salary_drops_only_vacancies_that_state_a_lower_one(
    catalog: pd.DataFrame,
) -> None:
    ranked = pr.rank_vacancies(catalog, pr.Profile(min_salary=3000))

    assert sorted(_ids(ranked)) == ["v1", "v3", "v5", "v6"]  # v2 (2000) is out; no-salary stay


def test_closed_vacancies_can_be_included(catalog: pd.DataFrame) -> None:
    assert "v4" in _ids(pr.rank_vacancies(catalog, pr.Profile(), only_open=False))


def test_readiness_is_the_median_match_of_the_best_vacancies(catalog: pd.DataFrame) -> None:
    profile = pr.Profile()
    pr.set_skills(profile, ["Python"], [])
    ranked = pr.rank_vacancies(catalog, profile)

    assert pr.readiness(ranked) == pytest.approx((0.4 + 1 / 3) / 2)  # 2/3, 0.4, 1/3, 0
    assert pr.readiness(ranked, top=1) == pytest.approx(2 / 3)
    assert pr.readiness(ranked.iloc[0:0]) is None


def test_the_plan_puts_first_what_unlocks_the_most_vacancies(catalog: pd.DataFrame) -> None:
    profile = pr.Profile()
    pr.set_skills(profile, ["Python"], [])
    ranked = pr.rank_vacancies(catalog, profile)

    plan = pr.learning_plan(ranked, profile.known())

    assert plan["skill"].tolist() == ["Docker", "Django", "SQL"]  # Python is known: not listed
    docker = plan.iloc[0]
    assert (docker["vacancies"], docker["required"], docker["unlocks"]) == (3, 2, 1)
    assert plan.iloc[2]["unlocks"] == 0  # SQL alone never completes a vacancy


def test_the_plan_is_empty_when_everything_is_known_or_there_is_nothing(
    catalog: pd.DataFrame,
) -> None:
    everything = {"Python", "Django", "Docker", "SQL", "Java"}
    ranked = pr.rank_vacancies(catalog, pr.Profile())

    assert pr.learning_plan(ranked, everything).empty
    assert pr.learning_plan(ranked.iloc[0:0], set()).empty
    assert len(pr.learning_plan(ranked, set(), top=2)) == 2


# ---- the tables the page edits -----------------------------------------------------------------
def _profile_with_two_saved() -> pr.Profile:
    profile = pr.Profile()
    pr.save_vacancy(profile, "v1", title="Old", company="A", url="u1", today=date(2026, 11, 1))
    pr.save_vacancy(profile, "v2", title="New", company="B", url="u2", today=date(2026, 11, 8))
    return profile


def test_the_saved_table_lists_the_newest_first_with_readable_stages() -> None:
    table = pr.saved_table(_profile_with_two_saved())

    assert table["id"].tolist() == ["v2", "v1"] and set(table["Етап"]) == {"збережено"}
    assert not table["Видалити"].any()
    assert pr.saved_table(pr.Profile()).empty


def test_edits_of_the_saved_table_change_stages_notes_and_remove_marked_rows() -> None:
    profile = _profile_with_two_saved()
    edited = pr.saved_table(profile)
    edited.loc[edited["id"] == "v2", "Етап"] = "співбесіда"
    edited.loc[edited["id"] == "v2", "Нотатка"] = "п'ятниця"
    edited.loc[edited["id"] == "v1", "Видалити"] = True

    changed = pr.apply_saved_table(profile, edited)

    assert changed == 2 and list(profile.saved) == ["v2"]
    assert (
        profile.saved["v2"]["status"] == "interview" and profile.saved["v2"]["note"] == "п'ятниця"
    )
    assert pr.apply_saved_table(profile, pr.saved_table(profile)) == 0  # no edit, no change


def test_an_edited_stage_that_is_not_a_stage_changes_nothing() -> None:
    profile = _profile_with_two_saved()
    edited = pr.saved_table(profile)
    edited["Етап"] = "якась вигадка"

    assert pr.apply_saved_table(profile, edited) == 0
    assert {e["status"] for e in profile.saved.values()} == {"saved"}


def _plan() -> pd.DataFrame:
    return pd.DataFrame(
        {"skill": ["Docker", "Django"], "vacancies": [3, 1], "required": [2, 1], "unlocks": [1, 1]}
    )


def test_the_plan_table_shows_the_current_state_of_each_skill_and_the_trainers_questions() -> None:
    profile = pr.Profile()
    pr.mark_skill(profile, "Docker", "learning")

    table = pr.plan_table(_plan(), profile, {"Docker": 5})

    assert table["Вчу"].tolist() == [True, False] and table["Знаю"].tolist() == [False, False]
    assert table["Питань"].tolist() == [5, 0] and table["Відкриває"].tolist() == [1, 1]


def test_ticks_in_the_plan_table_set_forget_and_prefer_known_over_learning() -> None:
    profile = pr.Profile()
    pr.mark_skill(profile, "Docker", "learning")
    edited = pr.plan_table(_plan(), profile, {})
    edited.loc[0, "Знаю"] = True  # Docker: both ticks -> known
    edited.loc[1, "Вчу"] = True  # Django: new

    assert pr.apply_plan_table(profile, edited) == 2
    assert profile.skills == {"Docker": "know", "Django": "learning"}

    edited.loc[:, ["Вчу", "Знаю"]] = False  # untick everything: forgotten
    assert pr.apply_plan_table(profile, edited) == 2 and profile.skills == {}


# ---- activity, finished materials and the goal -------------------------------------------------
def test_answers_are_counted_per_day() -> None:
    profile = pr.Profile()

    pr.record_answer(profile, TODAY)
    pr.record_answer(profile, TODAY)
    pr.record_answer(profile, date(2026, 11, 8))

    assert profile.activity == {"2026-11-09": 2, "2026-11-08": 1}


def test_a_very_old_day_is_forgotten() -> None:
    profile = pr.Profile(activity={"2020-01-01": 5})

    pr.record_answer(profile, TODAY)

    assert list(profile.activity) == ["2026-11-09"]


def test_a_finished_material_can_be_marked_and_unmarked() -> None:
    profile = pr.Profile()

    assert pr.toggle_resource(profile, "https://x.test/a", TODAY) is True
    assert profile.done == {"https://x.test/a": "2026-11-09"}
    assert pr.toggle_resource(profile, "https://x.test/a", TODAY) is False
    assert profile.done == {}


def test_activity_materials_and_the_goal_survive_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    profile = pr.Profile(
        goal=8, done={"https://x.test/a": "2026-11-01"}, activity={"2026-11-09": 3}
    )

    pr.save(profile, path)

    assert pr.load(path) == profile


def test_a_hand_edited_activity_goal_and_materials_are_coerced(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "goal": 9999,
                "activity": {"2026-11-09": 4, "not a day": 3, "2026-11-08": "x", "2026-11-07": -5},
                "done": {"https://x.test/a": "2026-11-01", "": "2026-11-02"},
            }
        ),
        encoding="utf-8",
    )

    profile = pr.load(path)

    assert profile.goal == 50  # at most fifty answers a day
    assert profile.activity == {"2026-11-09": 4, "2026-11-07": 0}
    assert profile.done == {"https://x.test/a": "2026-11-01"}


def test_a_goal_that_is_not_a_number_falls_back_to_the_default(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"goal": "many"}), encoding="utf-8")

    assert pr.load(path).goal == pr.DEFAULT_GOAL
