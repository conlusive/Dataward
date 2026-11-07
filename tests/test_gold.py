from datetime import datetime
from pathlib import Path

import pytest

from jobmarket.gold import (
    Candidate,
    Metrics,
    load_gold,
    parse_sheet,
    render_metrics,
    render_sheet,
    sample_candidates,
    score,
    top_errors,
    write_gold,
)
from jobmarket.gold_commands import evaluate, import_labels, make_sheet
from jobmarket.silver.dedup_step import apply_dedup
from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.store import SilverStore

KNOWN = {"python", "django", "docker", "kafka"}


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    store = SilverStore(tmp_path / "test.duckdb")
    for i in range(1, 9):
        store.upsert(
            ParsedVacancy(
                id=f"dou:{i}",
                source="dou",
                url=f"https://example.com/{i}",
                title=f"Developer number {i}",
                company=f"Company {i}",
                category=None,
                description_text=f"Python and Django daily. Vacancy {i} is unique text {i * 7919}.",
            ),
            run_id="r",
            loaded_at=datetime(2026, 11, 1),
            source_file="x",
            fetched_at=datetime(2026, 11, 1),
        )
    apply_dedup(store, run_id="d")
    return store


def test_the_sample_is_reproducible_and_never_larger_than_the_corpus(silver: SilverStore) -> None:
    first = sample_candidates(silver, 5, seed=1)
    again = sample_candidates(silver, 5, seed=1)
    other = sample_candidates(silver, 5, seed=2)

    assert [c.id for c in first] == [c.id for c in again] and len(first) == 5
    assert [c.id for c in first] != [c.id for c in other]
    assert len(sample_candidates(silver, 100, seed=1)) == 8


def test_a_duplicated_vacancy_is_sampled_once(silver: SilverStore) -> None:
    silver.upsert(
        ParsedVacancy(
            id="djinni:1",
            source="djinni",
            url="https://example.com/dj1",
            title="Developer number 1",
            company="Company 1",
            category=None,
            description_text="Python and Django every day. Vacancy 1 is unique text 7919.",
        ),
        run_id="r",
        loaded_at=datetime(2026, 11, 1),
        source_file="x",
        fetched_at=datetime(2026, 11, 1),
    )
    apply_dedup(silver, run_id="d2")

    ids = [c.id for c in sample_candidates(silver, 100, seed=1)]

    assert len(ids) == 8 and not {"dou:1", "djinni:1"} <= set(ids)


CANDIDATES = [
    Candidate("dou:1", "Python Developer", "Acme", "Python, Django.\n- a bullet in the text", "h1"),
    Candidate("dou:2", "Data Engineer", "Beta", "Kafka and Docker", "h2"),
]


def test_a_blind_sheet_has_empty_labels_and_a_prefilled_one_lists_the_suggestions() -> None:
    blind = render_sheet(CANDIDATES)
    filled = render_sheet(CANDIDATES, {"dou:1": ["django", "python"], "dou:2": []})

    assert "## dou:1" in blind and "Labels:\n\n---" in blind
    assert "Labelling blind" in blind and "pre-filled" not in blind
    assert "Labels:\n- django\n- python" in filled and "pre-filled" in filled


def test_labels_survive_the_round_trip_and_description_bullets_are_not_labels() -> None:
    sheet = render_sheet(CANDIDATES, {"dou:1": ["python"], "dou:2": []}).replace(
        "Labels:\n\n---", "Labels:\n- kafka\n- docker\n+ Quantum basketry\n\n---"
    )

    parsed = parse_sheet(sheet, KNOWN)

    assert parsed.problems == []
    assert parsed.labels == {"dou:1": {"python"}, "dou:2": {"kafka", "docker"}}
    assert parsed.wanted == {"dou:2": ["Quantum basketry"]}


def test_an_unknown_id_is_reported_with_its_line_and_vacancy() -> None:
    sheet = render_sheet(CANDIDATES).replace("Labels:\n\n---", "Labels:\n- pyton\n\n---", 1)

    parsed = parse_sheet(sheet, KNOWN)

    assert (
        len(parsed.problems) == 1
        and "dou:1" in parsed.problems[0]
        and "'pyton'" in parsed.problems[0]
    )


def test_the_texts_are_kept_out_of_the_committed_gold_file(tmp_path: Path) -> None:
    gold_file, texts_file = tmp_path / "gold.yaml", tmp_path / "texts.yaml"

    write_gold(
        {"dou:1": {"python", "django"}}, {c.id: c for c in CANDIDATES}, gold_file, texts_file
    )

    assert "Python, Django" not in gold_file.read_text(encoding="utf-8")
    assert "Python, Django" in texts_file.read_text(encoding="utf-8")
    assert load_gold(gold_file) == {
        "dou:1": {"id": "dou:1", "content_hash": "h1", "skills": ["django", "python"]}
    }


def test_metrics_are_micro_averaged_pairs() -> None:
    gold = {"a": {"x", "y"}, "b": {"z"}, "c": set()}
    predicted = {"a": {"x", "w"}, "b": {"z"}}

    metrics = score(gold, predicted)

    assert (metrics.true_positives, metrics.false_positives, metrics.false_negatives) == (2, 1, 1)
    assert metrics.precision == pytest.approx(2 / 3) and metrics.recall == pytest.approx(2 / 3)
    assert metrics.f1 == pytest.approx(2 / 3) and metrics.vacancies == 3


def test_edge_cases_do_not_divide_by_zero() -> None:
    nothing = score({"a": {"x"}}, {})
    assert (nothing.precision, nothing.recall, nothing.f1) == (0.0, 0.0, 0.0)
    assert Metrics(0, 0, 0, 0).f1 == 0.0


def test_the_most_frequent_mistakes_are_listed() -> None:
    gold = {"a": {"x"}, "b": {"x", "y"}}
    predicted = {"a": {"w"}, "b": {"w"}}

    wrong, missed = top_errors(gold, predicted)

    assert wrong == [("w", 2)] and missed == [("x", 2), ("y", 1)]


def test_the_metrics_page_has_a_row_per_method_and_the_taxonomy_gaps() -> None:
    page = render_metrics(
        [("dictionary", Metrics(10, 8, 2, 2), 0.0), ("llm", Metrics(10, 9, 1, 1), 1.5)],
        [("quantum basketry", 3)],
        {"dictionary": ([("w", 2)], [("x", 1)])},
    )

    assert "| dictionary | 10 | 0.80 | 0.80 | 0.80 | $0.00 |" in page
    assert "| llm | 10 | 0.90 | 0.90 | 0.90 | $1.50 |" in page
    assert "quantum basketry (3)" in page and "Found wrongly: w (2)" in page


def test_an_existing_sheet_is_never_overwritten_without_force(
    silver: SilverStore, tmp_path: Path
) -> None:
    sheet = tmp_path / "sheet.md"
    sheet.write_text("hours of labelling", encoding="utf-8")

    assert make_sheet(silver, 3, 1, prefill=False, force=False, sheet=sheet) == 2
    assert sheet.read_text(encoding="utf-8") == "hours of labelling"
    assert make_sheet(silver, 3, 1, prefill=False, force=True, sheet=sheet) == 0
    assert "## " in sheet.read_text(encoding="utf-8")


def test_import_refuses_a_sheet_with_unknown_ids_and_writes_nothing(
    silver: SilverStore, tmp_path: Path
) -> None:
    sheet, gold_file, texts = tmp_path / "s.md", tmp_path / "g.yaml", tmp_path / "t.yaml"
    make_sheet(silver, 3, 1, prefill=False, force=True, sheet=sheet)
    sheet.write_text(
        sheet.read_text(encoding="utf-8").replace("Labels:\n", "Labels:\n- nonsense\n", 1),
        encoding="utf-8",
    )

    assert import_labels(silver, sheet=sheet, gold_file=gold_file, texts_file=texts) == 2
    assert not gold_file.exists() and not texts.exists()


def test_a_full_cycle_from_sheet_to_metrics(silver: SilverStore, tmp_path: Path) -> None:
    sheet, gold_file, texts, metrics_file = (
        tmp_path / n for n in ("s.md", "g.yaml", "t.yaml", "m.md")
    )
    make_sheet(silver, 4, 1, prefill=True, force=True, sheet=sheet)  # prefilled: python, django
    assert import_labels(silver, sheet=sheet, gold_file=gold_file, texts_file=texts) == 0
    # a method that has not run at all is left out, not shown with zeros
    assert evaluate(silver, gold_file=gold_file, out=metrics_file) == 0
    assert "| dictionary |" not in metrics_file.read_text(encoding="utf-8")

    insert = (
        "INSERT INTO silver_vacancy_skills VALUES "
        "(?, ?, 'required', 'dictionary', 1.0, NULL, NULL, 'r', now())"
    )
    for vid in load_gold(gold_file):
        for skill in ("python", "django"):
            silver._con.execute(insert, [vid, skill])

    assert evaluate(silver, gold_file=gold_file, out=metrics_file) == 0
    assert "| dictionary | 4 | 1.00 | 1.00 | 1.00 | $0.00 |" in metrics_file.read_text(
        encoding="utf-8"
    )


def test_a_vacancy_whose_text_changed_after_labelling_is_not_scored(
    silver: SilverStore, tmp_path: Path
) -> None:
    sheet, gold_file, texts = tmp_path / "s.md", tmp_path / "g.yaml", tmp_path / "t.yaml"
    make_sheet(silver, 2, 1, prefill=True, force=True, sheet=sheet)
    import_labels(silver, sheet=sheet, gold_file=gold_file, texts_file=texts)
    silver._con.execute("UPDATE silver_vacancies SET content_hash = 'changed'")

    assert evaluate(silver, gold_file=gold_file, out=tmp_path / "m.md") == 2  # nothing usable left
