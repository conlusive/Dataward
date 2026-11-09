from collections.abc import Iterator
from pathlib import Path

import pytest

from jobmarket.cli import main
from jobmarket.gold import Candidate, parse_sheet, render_sheet
from jobmarket.gold_commands import import_labels
from jobmarket.gold_label import Lookup, label_sheet, read_sheet, write_sheet
from jobmarket.silver.store import SilverStore
from jobmarket.skills.taxonomy import Skill, Taxonomy, load_taxonomy

TAXONOMY = load_taxonomy()
KNOWN = set(TAXONOMY.skills)
CANDIDATES = [
    Candidate("dou:1", "Python Developer", "Acme", "We use Python and Django.\nAlso Docker.", "h1"),
    Candidate("dou:2", "Data Engineer", "Beta", "Kafka, PostgreSQL.", "h2"),
    Candidate("dou:3", "Office Manager", "Gamma", "Coffee and calendars.", "h3"),
]


class Typed:
    """Scripted answers; records what was shown. Raises EOFError when the script runs out."""

    def __init__(self, *answers: str) -> None:
        self._answers: Iterator[str] = iter(answers)
        self.shown: list[str] = []

    def ask(self, prompt: str) -> str:
        try:
            return next(self._answers)
        except StopIteration:
            raise EOFError from None

    def say(self, text: str) -> None:
        self.shown.append(text)

    @property
    def output(self) -> str:
        return "\n".join(self.shown)


@pytest.fixture
def sheet(tmp_path: Path) -> Path:
    path = tmp_path / "sheet.md"
    path.write_text(render_sheet(CANDIDATES), encoding="utf-8")
    return path


def _run(sheet: Path, *answers: str, relabel: bool = False) -> tuple[Typed, object]:
    typed = Typed(*answers)
    stats = label_sheet(TAXONOMY, sheet=sheet, relabel=relabel, ask=typed.ask, say=typed.say)
    return typed, stats


def _labels(sheet: Path):  # type: ignore[no-untyped-def]
    return parse_sheet(sheet.read_text(encoding="utf-8"), KNOWN)


# ---- the file format -----------------------------------------------------------------------
def test_reading_and_writing_a_sheet_changes_nothing(sheet: Path) -> None:
    text = sheet.read_text(encoding="utf-8")

    assert write_sheet(*read_sheet(text)) == text


def test_rewriting_does_not_pile_up_blank_lines(sheet: Path) -> None:
    text = sheet.read_text(encoding="utf-8")

    once = write_sheet(*read_sheet(text))
    for _ in range(3):
        once = write_sheet(*read_sheet(once))

    assert once == text


def test_a_sheet_with_labels_survives_the_round_trip() -> None:
    sheet = render_sheet(CANDIDATES).replace(
        "Labels:\n\n---", "Labels:\n- python\n+ New thing\n\n---", 1
    )

    assert write_sheet(*read_sheet(sheet)) == sheet


# ---- labelling -------------------------------------------------------------------------------
def test_ids_names_and_aliases_are_all_accepted_and_saved_as_ids(sheet: Path) -> None:
    _run(sheet, "python, Django, docker", "apache kafka, postgres", "0")

    parsed = _labels(sheet)
    assert parsed.labels["dou:1"] == {"python", "django", "docker"}
    assert parsed.labels["dou:2"] == {
        "kafka",
        "postgresql",
    }  # "apache kafka" and "postgres" are aliases
    assert parsed.problems == []


def test_zero_means_the_vacancy_asks_for_no_technical_skill_and_is_labelled(sheet: Path) -> None:
    _run(sheet, "python", "kafka", "0")

    parsed = _labels(sheet)
    assert parsed.labels["dou:3"] == set() and parsed.unlabelled == set()
    assert "= none" in sheet.read_text(encoding="utf-8")


def test_a_skipped_vacancy_stays_unlabelled_and_is_not_taken_for_empty(sheet: Path) -> None:
    _run(sheet, "python", "s", "kafka")

    parsed = _labels(sheet)
    assert "dou:2" in parsed.unlabelled and "dou:2" not in parsed.labels
    assert set(parsed.labels) == {"dou:1", "dou:3"}


def test_an_unknown_word_is_refused_with_near_misses_and_nothing_is_saved(sheet: Path) -> None:
    before = sheet.read_text(encoding="utf-8")

    typed, _ = _run(sheet, "pyton, docker", "q")

    assert "не знайдено «pyton»" in typed.output and "python" in typed.output
    assert sheet.read_text(encoding="utf-8") == before  # the valid half of the line was not saved


def test_after_a_refusal_the_corrected_line_is_accepted(sheet: Path) -> None:
    _run(sheet, "pyton", "python")

    assert _labels(sheet).labels["dou:1"] == {"python"}


def test_a_skill_the_taxonomy_lacks_is_recorded_as_wanted(sheet: Path) -> None:
    _run(sheet, "python, +Quantum basketry")

    parsed = _labels(sheet)
    assert parsed.labels["dou:1"] == {"python"} and parsed.wanted == {"dou:1": ["Quantum basketry"]}


def test_a_wanted_skill_alone_counts_as_labelled(sheet: Path) -> None:
    _run(sheet, "+Quantum basketry")

    assert "dou:1" not in _labels(sheet).unlabelled


def test_back_returns_to_the_previous_vacancy_and_the_new_answer_replaces_the_old(
    sheet: Path,
) -> None:
    _run(sheet, "python", "kafka", "b", "postgresql", "0")

    assert _labels(sheet).labels["dou:2"] == {"postgresql"}  # kafka was replaced, not added


def test_search_shows_matches_and_writes_nothing(sheet: Path) -> None:
    typed, _ = _run(sheet, "?postg", "q")

    assert "postgresql (PostgreSQL)" in typed.output
    assert _labels(sheet).labels == {}


def test_quitting_saves_what_was_done_and_the_next_run_resumes_there(sheet: Path) -> None:
    _run(sheet, "python", "q")

    typed, _ = _run(sheet, "kafka", "0")

    assert "[2/3] dou:2" in typed.output  # it starts at the first unlabelled vacancy
    assert "[1/3] dou:1" not in typed.output  # and does not show the labelled one again
    assert _labels(sheet).unlabelled == set()


def test_a_vacancy_marked_as_asking_for_nothing_is_not_asked_about_again(sheet: Path) -> None:
    _run(sheet, "python", "kafka", "0")  # the last one is `= none`

    typed, stats = _run(sheet)  # everything is labelled: nothing to show

    assert "dou:" not in typed.output
    assert stats.labelled == 3  # type: ignore[attr-defined]


def test_closing_the_input_stops_cleanly_and_keeps_the_labels(sheet: Path) -> None:
    _, stats = _run(sheet, "python")  # the script ends: EOFError, as with Ctrl-D

    assert stats.labelled == 1 and _labels(sheet).labels["dou:1"] == {"python"}  # type: ignore[attr-defined]


def test_relabel_walks_through_labelled_vacancies_too(sheet: Path) -> None:
    _run(sheet, "python", "kafka", "0")

    typed, _ = _run(sheet, "django", "q", relabel=True)

    assert "[1/3] dou:1" in typed.output and _labels(sheet).labels["dou:1"] == {"django"}


def test_the_vacancy_text_is_shown_but_no_suggestion_is_ever_made(sheet: Path) -> None:
    typed, _ = _run(sheet, "q")

    assert "We use Python and Django." in typed.output
    assert "підказ" not in typed.output.lower() and "suggest" not in typed.output.lower()


def test_the_description_in_the_sheet_is_not_touched_by_labelling(sheet: Path) -> None:
    _run(sheet, "python", "kafka", "0")

    text = sheet.read_text(encoding="utf-8")
    for line in ("> We use Python and Django.", "> Kafka, PostgreSQL.", "> Coffee and calendars."):
        assert text.count(line) == 1


# ---- the lookup ------------------------------------------------------------------------------
def _skill(skill_id: str, name: str, *aliases: str) -> Skill:
    return Skill(skill_id, name, "tool", None, tuple(aliases), False, (), None, True)


def test_a_word_that_names_two_skills_is_not_accepted() -> None:
    taxonomy = Taxonomy(
        ("tool",),
        {"a": _skill("a", "Alpha", "shared"), "b": _skill("b", "Beta", "shared")},
    )
    lookup = Lookup(taxonomy)

    assert lookup.resolve("shared") is None  # ambiguous: the labeller must be exact
    assert lookup.resolve("alpha") == "a" and lookup.resolve("BETA") == "b"


def test_lookup_is_case_insensitive_and_ignores_surrounding_spaces() -> None:
    lookup = Lookup(TAXONOMY)

    assert (
        lookup.resolve("  PostgreSQL ") == "postgresql" and lookup.resolve("nonsense-xyz") is None
    )


# ---- importing a partly labelled sheet ---------------------------------------------------------
def test_importing_a_partly_labelled_sheet_keeps_only_the_labelled_vacancies(
    tmp_path: Path, sheet: Path
) -> None:
    from datetime import datetime

    from jobmarket.silver.model import ParsedVacancy

    silver = SilverStore(tmp_path / "t.duckdb")
    for c in CANDIDATES:
        silver.upsert(
            ParsedVacancy(id=c.id, source="dou", url=f"https://x/{c.id}", title=c.title,
                          company=c.company, category=None, description_text=c.description),
            run_id="r", loaded_at=datetime(2026, 11, 1), source_file="f",
            fetched_at=datetime(2026, 11, 1),
        )  # fmt: skip
    _run(sheet, "python", "s", "0")  # dou:2 is skipped
    gold = tmp_path / "gold.yaml"

    code = import_labels(silver, sheet=sheet, gold_file=gold, texts_file=tmp_path / "texts.yaml")

    text = gold.read_text(encoding="utf-8")
    assert code == 0 and "dou:1" in text and "dou:3" in text and "dou:2" not in text


def test_a_sheet_with_nothing_labelled_is_not_imported(tmp_path: Path, sheet: Path) -> None:
    silver = SilverStore(tmp_path / "t.duckdb")

    code = import_labels(
        silver, sheet=sheet, gold_file=tmp_path / "g.yaml", texts_file=tmp_path / "t.yaml"
    )

    assert code == 2 and not (tmp_path / "g.yaml").exists()


def test_none_together_with_skills_is_a_problem() -> None:
    sheet = render_sheet(CANDIDATES).replace(
        "Labels:\n\n---", "Labels:\n= none\n- python\n\n---", 1
    )

    parsed = parse_sheet(sheet, KNOWN)

    assert any("dou:1" in p and "none" in p for p in parsed.problems)


def test_the_command_without_a_sheet_says_what_to_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["gold-label"]) == 1
