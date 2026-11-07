import random
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from jobmarket.silver.dedup import (
    DedupInput,
    VacancyGroup,
    group_vacancies,
    match_kind,
    normalize_company,
)
from jobmarket.silver.dedup_step import apply_dedup
from jobmarket.silver.model import ParsedVacancy, text_hash
from jobmarket.silver.store import SilverStore

JD = (
    "We are building a payments platform and looking for an engineer who writes clean code, "
    "reviews pull requests, designs APIs and works closely with product managers. You will own "
    "services end to end, from design to production support, and mentor teammates. "
) * 6


def _v(
    vid: str,
    title: str = "Senior Python Developer",
    company: str = "Acme",
    description: str = JD,
    source: str = "dou",
    day: int = 1,
    salary: bool = False,
) -> DedupInput:
    return DedupInput(
        id=vid,
        source=source,
        title=title,
        company=company,
        description=description,
        content_hash=text_hash(description),
        published_at=date(2026, 11, day),
        fetched_at=datetime(2026, 11, day, tzinfo=UTC).replace(tzinfo=None),
        has_salary=salary,
    )


def _by_members(groups: list[VacancyGroup]) -> dict[tuple[str, ...], VacancyGroup]:
    return {g.members: g for g in groups}


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Edsson Ukraine LLC", "Edsson Ukraine"),
        ("Digis (a Fiverr company)", "Digis"),
        ("AppRecode", "Apprecode"),
        ("N-iX", "N-iX Ltd."),
        ('ТОВ "Нова Пошта"', "Нова Пошта"),
    ],
)
def test_company_names_are_compared_without_legal_forms_and_notes(a: str, b: str) -> None:
    assert normalize_company(a) == normalize_company(b)
    assert normalize_company(a) != ""


def test_different_companies_stay_different() -> None:
    assert normalize_company("Ajax Systems") != normalize_company("Luxoft")


def test_the_same_posting_on_both_sites_becomes_one_group_with_the_best_parts() -> None:
    dou = _v("dou:1", source="dou", day=2)
    djinni = _v("djinni:9", source="djinni", day=1, salary=True)

    (group,) = group_vacancies([dou, djinni])

    assert group.members == ("djinni:9", "dou:1")  # oldest first
    assert group.group_id == "djinni:9"
    assert group.match_kind == "exact"
    assert group.text_id == "dou:1"  # DOU is trusted for the text
    assert group.salary_id == "djinni:9"  # Djinni is trusted for the salary
    assert group.sources == ("djinni", "dou")


def test_a_group_without_any_salary_has_no_salary_member() -> None:
    (group,) = group_vacancies([_v("dou:1"), _v("djinni:1", source="djinni")])

    assert group.salary_id is None


def test_salary_comes_from_dou_when_only_dou_has_one() -> None:
    (group,) = group_vacancies([_v("dou:1", salary=True), _v("djinni:1", source="djinni")])

    assert group.salary_id == "dou:1"


def test_an_identical_description_alone_is_not_enough() -> None:
    smart_home = _v("dou:1", title="Senior Java Developer (Smart Home)")
    business = _v("dou:2", title="Senior Java Developer (Business Express Center)")

    assert match_kind(smart_home, business) is None
    assert len(group_vacancies([smart_home, business])) == 2


def test_similar_title_and_similar_description_match_fuzzily() -> None:
    first = _v("dou:1", title="Python Game Developer (Panda3D)")
    second = _v(
        "djinni:1",
        title="Python Game Developer (Panda3D)",
        source="djinni",
        description=JD + "Extra paragraph about the company culture.",
    )

    assert match_kind(first, second) == "fuzzy"


def test_seniority_dropped_from_the_title_of_an_identical_text_still_matches() -> None:
    assert (
        match_kind(
            _v("dou:1", title="Senior Java Backend Engineer"),
            _v(
                "djinni:1",
                title="Java Backend Engineer",
                source="djinni",
                description=JD + "Also: Kafka.",
            ),
        )
        == "fuzzy"
    )


def test_two_levels_sharing_a_template_are_two_vacancies() -> None:
    middle = _v("dou:1", title="Middle Data Science Engineer")
    senior = _v("dou:2", title="Senior Data Science Engineer", description=JD + "Plus: Spark.")

    assert match_kind(middle, senior) is None
    assert len(group_vacancies([middle, senior])) == 2


def test_an_identical_text_with_conflicting_levels_is_two_vacancies() -> None:
    middle = _v("dou:1", title="Middle Data Science Engineer")
    senior = _v("dou:2", title="Senior Data Science Engineer")  # the very same description

    assert middle.content_hash == senior.content_hash
    assert match_kind(middle, senior) is None


def test_an_identical_text_with_a_slightly_different_title_is_one_vacancy() -> None:
    first = _v("dou:1", title="Junior PHP developer (payment team/Kyiv)")
    second = _v("djinni:1", title="Junior PHP developer (payment team)", source="djinni")

    assert first.content_hash == second.content_hash
    assert match_kind(first, second) == "exact"


def test_the_same_text_in_two_companies_is_not_a_duplicate() -> None:
    groups = group_vacancies([_v("dou:1", company="Acme"), _v("dou:2", company="Other")])

    assert len(groups) == 2


def test_a_repost_on_the_same_site_is_grouped_and_the_oldest_id_is_the_group_id() -> None:
    old = _v("djinni:10", source="djinni", day=1)
    repost = _v("djinni:99", source="djinni", day=5)

    (group,) = group_vacancies([repost, old])

    assert group.group_id == "djinni:10"


def test_the_group_id_does_not_change_when_a_newer_repost_appears() -> None:
    before = group_vacancies([_v("dou:1", day=1), _v("djinni:1", source="djinni", day=2)])
    after = group_vacancies(
        [_v("dou:1", day=1), _v("djinni:1", source="djinni", day=2), _v("dou:7", day=9)]
    )

    assert before[0].group_id == after[0].group_id == "dou:1"
    assert len(after[0].members) == 3


def test_matches_chain_into_one_group() -> None:
    a = _v("dou:1", title="Python Developer", description=JD)
    b = _v("dou:2", title="Python Developer", description=JD + "Bonus: Go.")
    c = _v("dou:3", title="Python Developer", description=JD + "Bonus: Go. Bonus: Rust.")

    (group,) = group_vacancies([a, b, c])

    assert len(group.members) == 3


def test_a_unique_vacancy_is_a_group_of_one() -> None:
    (group,) = group_vacancies([_v("dou:1", salary=True)])

    assert (group.group_id, group.match_kind, group.text_id, group.salary_id) == (
        "dou:1",
        "single",
        "dou:1",
        "dou:1",
    )


def test_the_result_does_not_depend_on_the_input_order() -> None:
    items = [
        _v("dou:1", day=1),
        _v("djinni:1", source="djinni", day=2),
        _v("dou:2", title="Go Developer", description="Go services. " * 40, day=3),
        _v("dou:3", company="Other", day=4),
    ]
    shuffled = items[:]
    random.Random(1).shuffle(shuffled)

    assert group_vacancies(items) == group_vacancies(shuffled)


def test_an_empty_input_gives_no_groups() -> None:
    assert group_vacancies([]) == []


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    return SilverStore(tmp_path / "test.duckdb")


def _add(silver: SilverStore, vid: str, source: str, title: str, description: str = JD) -> None:
    silver.upsert(
        ParsedVacancy(
            id=vid,
            source=source,
            url=f"https://example.com/{vid.replace(':', '/')}",
            title=title,
            company="Acme",
            category=None,
            published_at=date(2026, 11, 1),
            description_text=description,
        ),
        run_id="parse-1",
        loaded_at=datetime(2026, 11, 6),
        source_file="x.html",
        fetched_at=datetime(2026, 11, 6),
    )


def _group_of(silver: SilverStore, vid: str) -> Any:
    row = silver._con.execute(
        "SELECT dedup_group_id FROM silver_vacancies WHERE id = ?", [vid]
    ).fetchone()
    return row[0] if row else None


def test_every_vacancy_gets_a_group_and_duplicates_share_it(silver: SilverStore) -> None:
    _add(silver, "dou:1", "dou", "Senior Python Developer")
    _add(silver, "djinni:1", "djinni", "Senior Python Developer")
    _add(silver, "dou:2", "dou", "Go Developer", "Go services and gRPC. " * 40)

    stats = apply_dedup(silver, run_id="dedup-1")

    assert _group_of(silver, "dou:1") == _group_of(silver, "djinni:1")
    assert _group_of(silver, "dou:2") == "dou:2"
    assert (stats.vacancies, stats.groups, stats.merged_groups, stats.duplicates) == (3, 2, 1, 1)
    groups = silver._con.execute("SELECT count(*), sum(size) FROM silver_vacancy_groups").fetchone()
    assert groups == (2, 3)


def test_recomputing_gives_the_same_groups_and_follows_changes(silver: SilverStore) -> None:
    _add(silver, "dou:1", "dou", "Senior Python Developer")
    _add(silver, "djinni:1", "djinni", "Senior Python Developer")
    apply_dedup(silver, run_id="dedup-1")
    first = silver._con.execute(
        "SELECT * EXCLUDE (_run_id, _loaded_at) FROM silver_vacancy_groups"
    ).fetchall()
    apply_dedup(silver, run_id="dedup-2")
    assert (
        silver._con.execute(
            "SELECT * EXCLUDE (_run_id, _loaded_at) FROM silver_vacancy_groups"
        ).fetchall()
        == first
    )

    _add(
        silver, "djinni:1", "djinni", "Accountant", "Books and invoices. " * 60
    )  # the posting changed
    apply_dedup(silver, run_id="dedup-3")

    assert _group_of(silver, "dou:1") != _group_of(silver, "djinni:1")


def test_the_group_survives_a_reparse_of_the_vacancy(silver: SilverStore) -> None:
    _add(silver, "dou:1", "dou", "Senior Python Developer")
    _add(silver, "djinni:1", "djinni", "Senior Python Developer")
    apply_dedup(silver, run_id="dedup-1")
    group = _group_of(silver, "dou:1")

    _add(silver, "dou:1", "dou", "Senior Python Developer")  # the parser upsert runs again

    assert _group_of(silver, "dou:1") == group


def test_a_failing_write_keeps_the_previous_groups(silver: SilverStore) -> None:
    _add(silver, "dou:1", "dou", "Senior Python Developer")
    apply_dedup(silver, run_id="dedup-1")
    broken = VacancyGroup("dou:1", ("dou:1",), ("dou",), "single", None, None)  # type: ignore[arg-type]

    with pytest.raises(duckdb.Error):
        silver.replace_groups([broken], run_id="dedup-2", loaded_at=datetime(2026, 11, 7))

    assert silver._con.execute("SELECT _run_id FROM silver_vacancy_groups").fetchone() == (
        "dedup-1",
    )
    assert _group_of(silver, "dou:1") == "dou:1"
