from datetime import date, timedelta
from pathlib import Path

import pytest

from jobmarket import dashboard_interview as iv
from jobmarket.skills.taxonomy import load_taxonomy

TODAY = date(2026, 11, 9)


def _q(n: int, skill: str = "Python", level: str = "junior") -> iv.Question:
    return iv.Question(f"q{n:02d}", skill, level, f"Питання {n}?", f"Відповідь {n}.")


def _entry(box: int, due: date) -> dict[str, object]:
    return {"box": box, "due": due.isoformat(), "seen": 1, "last": TODAY.isoformat()}


# ---- the bank ----------------------------------------------------------------------------------
def test_the_bank_has_unique_ids_known_levels_and_nothing_empty() -> None:
    bank = iv.load_bank()

    assert len(bank) >= 60 and len({q.id for q in bank}) == len(bank)
    assert {q.level for q in bank} <= set(iv.LEVELS)
    assert all(q.question and q.answer for q in bank)
    assert max(len(q.question) for q in bank) <= 200 and max(len(q.answer) for q in bank) <= 700


def test_every_question_belongs_to_a_skill_of_the_taxonomy() -> None:
    names = {skill.name for skill in load_taxonomy().skills.values()}

    assert {q.skill for q in iv.load_bank()} <= names


def test_every_skill_has_a_few_questions_at_more_than_one_level() -> None:
    bank = iv.load_bank()
    for skill in iv.skills_in_bank(bank):
        mine = [q for q in bank if q.skill == skill]
        assert len(mine) >= 5 and len({q.level for q in mine}) >= 2, skill


def _bank_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "bank.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_malformed_bank_is_refused_with_the_reason(tmp_path: Path) -> None:
    ok = '{id: a, skill: Python, level: junior, question: "Q", answer: "A"}'

    with pytest.raises(iv.BankError, match="duplicate"):
        iv.load_bank(_bank_file(tmp_path, f"questions:\n  - {ok}\n  - {ok}\n"))
    with pytest.raises(iv.BankError, match="unknown level"):
        iv.load_bank(
            _bank_file(tmp_path, ok.replace("junior", "godlike").join(["questions:\n  - ", "\n"]))
        )
    with pytest.raises(iv.BankError, match="lacks"):
        iv.load_bank(_bank_file(tmp_path, "questions:\n  - {id: a, skill: Python}\n"))
    with pytest.raises(iv.BankError, match="empty"):
        iv.load_bank(
            _bank_file(
                tmp_path, ok.replace('answer: "A"', 'answer: " "').join(["questions:\n  - ", "\n"])
            )
        )


# ---- the schedule ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("entry", "rating", "box", "days"),
    [
        (None, "know", 2, 2),  # new and known: box 2
        (None, "partial", 1, 1),
        (None, "dont", 1, 1),
        (_entry(3, TODAY), "know", 4, 8),
        (_entry(3, TODAY), "partial", 3, 4),
        (_entry(4, TODAY), "dont", 1, 1),  # forgotten: back to the start
        (_entry(5, TODAY), "know", 5, 16),  # the last box stays
    ],
)
def test_an_answer_moves_a_question_between_boxes_and_sets_when_it_returns(
    entry: dict[str, object] | None, rating: str, box: int, days: int
) -> None:
    result = iv.review(entry, rating, TODAY)

    assert result["box"] == box and result["due"] == (TODAY + timedelta(days=days)).isoformat()
    assert result["last"] == TODAY.isoformat()


def test_the_times_seen_add_up() -> None:
    first = iv.review(None, "know", TODAY)
    second = iv.review(first, "know", TODAY)

    assert (first["seen"], second["seen"]) == (1, 2)


def test_an_unknown_rating_is_refused() -> None:
    with pytest.raises(ValueError, match="rating"):
        iv.review(None, "maybe", TODAY)


def test_a_question_is_due_on_and_after_its_day_and_an_unreadable_date_means_ask_again() -> None:
    assert iv.is_due(_entry(2, TODAY), TODAY) and not iv.is_due(
        _entry(2, TODAY + timedelta(days=1)), TODAY
    )
    assert iv.is_due({"box": 2, "due": "garbage"}, TODAY) and iv.is_due({"box": 2}, TODAY)


# ---- a session ---------------------------------------------------------------------------------
def test_a_session_asks_what_is_due_first_oldest_first_then_new_questions() -> None:
    bank = [_q(n) for n in range(1, 8)]
    practice = {
        "q03": _entry(2, TODAY - timedelta(days=1)),
        "q05": _entry(2, TODAY - timedelta(days=4)),
        "q06": _entry(2, TODAY + timedelta(days=3)),  # not due: left out
    }

    session = iv.build_session(bank, practice, today=TODAY, size=4)

    assert [q.id for q in session[:2]] == ["q05", "q03"]
    assert "q06" not in [q.id for q in session] and len(session) == 4
    assert all(q.id not in practice for q in session[2:])


def test_a_session_never_exceeds_its_size_or_the_bank() -> None:
    bank = [_q(n) for n in range(1, 4)]

    assert len(iv.build_session(bank, {}, today=TODAY, size=10)) == 3
    assert len(iv.build_session(bank, {}, today=TODAY, size=2)) == 2
    assert iv.build_session([], {}, today=TODAY) == []


def test_a_session_can_be_narrowed_to_skills_and_levels() -> None:
    bank = [_q(1, "Python", "junior"), _q(2, "SQL", "junior"), _q(3, "Python", "senior")]

    assert [
        q.id for q in iv.build_session(bank, {}, today=TODAY, skills={"Python"}, levels={"senior"})
    ] == ["q03"]
    assert {q.skill for q in iv.build_session(bank, {}, today=TODAY, skills={"SQL"})} == {"SQL"}
    assert iv.build_session(bank, {}, today=TODAY, skills=set()) == []  # "no skills" is not "all"


def test_new_questions_are_the_same_all_day_and_differ_between_days() -> None:
    bank = [_q(n) for n in range(1, 21)]

    def order(day: date) -> list[str]:
        return [q.id for q in iv.build_session(bank, {}, today=day, size=20)]

    assert order(TODAY) == order(TODAY)
    assert len({tuple(order(TODAY + timedelta(days=n))) for n in range(5)}) > 1


# ---- progress ----------------------------------------------------------------------------------
def test_the_counts_and_the_per_skill_progress_agree() -> None:
    bank = [_q(1, "Python"), _q(2, "Python"), _q(3, "SQL")]
    practice = {
        "q01": _entry(4, TODAY + timedelta(days=5)),  # learned, not due
        "q02": _entry(2, TODAY),  # seen, due
        "gone": _entry(5, TODAY),  # a question that left the bank is ignored
    }

    assert iv.counts(bank, practice, TODAY) == {"total": 3, "seen": 2, "mastered": 1, "due": 1}
    table = iv.progress(bank, practice, TODAY).set_index("skill")
    assert table.loc["Python"].to_dict() == {"total": 2, "seen": 2, "mastered": 1, "due": 1}
    assert table.loc["SQL"].to_dict() == {"total": 1, "seen": 0, "mastered": 0, "due": 0}
