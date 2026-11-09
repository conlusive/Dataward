"""Runs the gold dbt models on a small made-up silver whose answers are worked out by hand."""

import json
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.store import SilverStore, SurveyRecord
from tests.test_dbt_lifecycle import DBT, _dbt

pytestmark = pytest.mark.skipif(not DBT.exists(), reason="dbt is not installed")

# Thresholds lowered so that a handful of rows is enough; the defaults are checked separately.
SMALL = json.dumps(
    {"min_pair_support": 1, "min_salary_n": 1, "min_survey_respondents": 4, "min_lifetime_n": 1}
)
NOW = datetime(2026, 11, 1)


def _add_vacancy(store: SilverStore, vid: str, published: date, seniority: str | None) -> None:
    store.upsert(
        ParsedVacancy(
            id=vid,
            source=vid.split(":")[0],
            url=f"https://example.com/{vid.replace(':', '/')}",
            title="Developer",
            company="Acme",
            category=None,
            published_at=published,
            description_text=f"text of {vid}",
        ),
        run_id="r1",
        loaded_at=NOW,
        source_file="x",
        fetched_at=NOW,
    )
    store._con.execute("UPDATE silver_vacancies SET seniority = ? WHERE id = ?", [seniority, vid])


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.duckdb"
    store = SilverStore(path)
    con = store._con
    store.replace_skills(
        [
            ("python", "Python", "language", None),
            ("django", "Django", "framework", "python"),
            ("docker", "Docker", "devops", None),
            ("sql", "SQL", "database", None),
        ]
    )

    nov, oct_ = date(2026, 11, 3), date(2026, 10, 15)
    _add_vacancy(store, "dou:1", nov, "senior")  # the same vacancy as djinni:1
    _add_vacancy(store, "djinni:1", nov, None)
    _add_vacancy(store, "dou:2", nov, "middle")
    _add_vacancy(store, "dou:3", nov, "middle")
    _add_vacancy(store, "dou:4", oct_, None)  # no group row at all, no skills

    # dou:1 and djinni:1 are one vacancy: text from dou:1, salary from djinni:1
    con.execute(
        "UPDATE silver_vacancies SET dedup_group_id = 'dou:1' WHERE id IN ('dou:1','djinni:1')"
    )
    con.execute(
        "UPDATE silver_vacancies SET salary_usd_min = 3000, salary_usd_max = 5000 "
        "WHERE id = 'djinni:1'"
    )
    con.execute(
        "UPDATE silver_vacancies SET dedup_group_id = id, salary_usd_min = 2000, "
        "salary_usd_max = 2000 WHERE id = 'dou:2'"
    )
    con.execute("UPDATE silver_vacancies SET dedup_group_id = id WHERE id = 'dou:3'")
    con.execute(
        "INSERT INTO silver_vacancy_groups VALUES "
        "('dou:1', 2, ['dou','djinni'], 'fuzzy', 'dou:1', 'djinni:1', 'r1', ?),"
        "('dou:2', 1, ['dou'], 'single', 'dou:2', 'dou:2', 'r1', ?),"
        "('dou:3', 1, ['dou'], 'single', 'dou:3', NULL, 'r1', ?)",
        [NOW, NOW, NOW],
    )

    skills = [
        ("dou:1", "django", "required"),
        ("dou:1", "docker", "nice"),
        ("djinni:1", "sql", "required"),  # not the group's text member: must be ignored
        ("dou:2", "python", "required"),
        ("dou:2", "django", "nice"),
        ("dou:2", "docker", "required"),
        ("dou:3", "sql", "required"),
    ]
    for vid, skill, importance in skills:
        con.execute(
            "INSERT INTO silver_vacancy_skills "
            "VALUES (?, ?, ?, 'dictionary', 1.0, NULL, NULL, 'r1', ?)",
            [vid, skill, importance, NOW],
        )

    # dou:1 is listed all week (open, first seen on day one); dou:2 closes on day 5; dou:3 on day 7
    for vid, days in {"dou:1": range(1, 8), "dou:2": (2, 3), "dou:3": (3, 4, 5)}.items():
        for day in days:
            store.add_sightings([vid], date(2026, 11, day))

    survey: list[
        SurveyRecord
    ] = [  # (row_no, position, experience, city, english, size, type, salary_usd, weight)
        (
            1,
            "Senior QA engineer",
            5.0,
            "Киев",
            " Upper-Intermediate ",
            "<=50",
            "Product",
            1000.0,
            1.0,
        ),
        (2, "Senior QA engineer", None, "Киев", None, None, None, 2000.0, 1.0),
        (3, "Senior QA engineer", None, "Київ", None, None, None, 3000.0, 1.0),
        (4, "Senior QA engineer", None, "Київ", None, None, None, 4000.0, 1.0),
        (5, "Middle", None, "Київ", None, None, None, 1000.0, 9.0),
        (6, "Middle", None, "Київ", None, None, None, 5000.0, 1.0),
        (7, "Всі", None, "Київ", None, None, None, 9000.0, 1.0),  # one respondent: too few
        (8, "Всі", 55.0, "Київ", None, None, None, 9100.0, 1.0),  # implausible experience
        (9, "Всі", -1.0, "Київ", None, None, None, 9200.0, 1.0),  # still below the minimum of 4
    ]
    store.replace_survey_file(
        "s.csv", "2024_june", date(2024, 6, 1), survey, run_id="r1", loaded_at=NOW
    )
    store.close()
    return path


def _rows(db: Path, query: str) -> list[tuple]:  # type: ignore[type-arg]
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


def test_the_gold_models_build_and_pass_their_tests_and_contracts(db: Path) -> None:
    _dbt(db, "build", "--vars", SMALL)


def test_a_vacancy_on_both_sites_counts_once_with_text_from_dou_and_salary_from_djinni(
    db: Path,
) -> None:
    _dbt(db, "build", "--vars", SMALL)

    rows = _rows(
        db,
        "SELECT vacancy_group_id, text_vacancy_id, members, salary_usd_mid "
        "FROM int_vacancies_deduped ORDER BY 1",
    )

    assert rows == [
        ("dou:1", "dou:1", 2, 4000.0),
        ("dou:2", "dou:2", 1, 2000.0),
        ("dou:3", "dou:3", 1, None),
        ("dou:4", "dou:4", 1, None),  # no group row: the vacancy stands for itself
    ]


def test_a_child_skill_counts_for_its_parent_and_shares_use_all_vacancies_of_the_month(
    db: Path,
) -> None:
    _dbt(db, "build", "--vars", SMALL)

    rows = _rows(
        db,
        "SELECT month, skill_id, vacancies, vacancies_direct, vacancies_required, share "
        "FROM fct_skill_demand_monthly ORDER BY skill_id",
    )

    nov = date(2026, 11, 1)
    # November has three real vacancies. python: dou:2 names it, dou:1 only through django (which
    # it requires). docker is `nice` in dou:1 and `required` in dou:2.
    assert rows == [
        (nov, "django", 2, 2, 1, pytest.approx(0.6667)),
        (nov, "docker", 2, 2, 1, pytest.approx(0.6667)),
        (nov, "python", 2, 1, 2, pytest.approx(0.6667)),
        (nov, "sql", 1, 1, 1, pytest.approx(0.3333)),
    ]


def test_skill_pairs_have_lift_and_npmi_and_leave_out_a_skill_with_its_own_parent(
    db: Path,
) -> None:
    _dbt(db, "build", "--vars", SMALL)

    rows = _rows(
        db,
        "SELECT skill_a, skill_b, vacancies_together, vacancies_total, lift, npmi "
        "FROM fct_skill_pairs ORDER BY skill_a, skill_b",
    )

    # skills were found in 3 vacancies; django+python are in one vacancy but are parent and child
    assert rows == [
        ("django", "docker", 2, 3, pytest.approx(1.5), pytest.approx(1.0)),
        ("docker", "python", 1, 3, pytest.approx(1.5), pytest.approx(0.36907, abs=1e-4)),
    ]


def test_salary_percentiles_per_skill_include_parents_and_skip_vacancies_without_salary(
    db: Path,
) -> None:
    _dbt(db, "build", "--vars", SMALL)

    rows = _rows(
        db,
        "SELECT skill_id, vacancies_with_salary, salary_p25, salary_median, salary_p75 "
        "FROM fct_salary_by_skill ORDER BY skill_id",
    )

    # salaries 4000 (dou:1 via djinni) and 2000 (dou:2); sql has no salaried vacancy
    assert rows == [
        ("django", 2, 2500.0, 3000.0, 3500.0),
        ("docker", 2, 2500.0, 3000.0, 3500.0),
        ("python", 2, 2500.0, 3000.0, 3500.0),
    ]


def test_survey_percentiles_are_weighted_and_small_groups_are_not_published(db: Path) -> None:
    _dbt(db, "build", "--vars", SMALL)

    rows = _rows(
        db,
        "SELECT survey_year, role, seniority, respondents, salary_p25, salary_median, salary_p75 "
        "FROM fct_salary_survey ORDER BY role",
    )

    assert rows == [
        (2024, "qa", "senior", 4.0, 1000.0, 2000.0, 3000.0),
        # 9 of 10 respondents earn 1000, so every percentile is 1000
        (2024, "software_engineer", "middle", 10.0, 1000.0, 1000.0, 1000.0),
    ]  # the lone "Всі" answer (role other) is below the minimum of 4


def test_the_salary_model_features_are_normalised_and_keep_every_answer(db: Path) -> None:
    _dbt(db, "build", "--vars", SMALL)

    rows = _rows(
        db,
        "SELECT role, seniority, experience_years, english, company_size, company_type, "
        "city_group, salary_usd FROM ml_features_salary ORDER BY salary_usd, role",
    )

    assert len(rows) == 9  # no answer is dropped
    # case and spaces are normalised, a stated experience is kept
    assert rows[0] == (
        "qa",
        "senior",
        5.0,
        "upper-intermediate",
        "<=50",
        "product",
        "ukraine",
        1000.0,
    )
    # a missing value becomes "unknown" (not null), so the model sees it as a category
    assert rows[1][3:6] == ("unknown", "unknown", "unknown")
    # experience over 40 years or below 0 is blanked, the salary stays
    implausible = [r for r in rows if r[7] in (9100.0, 9200.0)]
    assert [r[2] for r in implausible] == [None, None]


def test_lifetime_counts_only_closed_vacancies_that_were_not_open_before_the_data_began(
    db: Path,
) -> None:
    _dbt(db, "build", "--vars", SMALL)

    rows = _rows(
        db,
        "SELECT seniority, closed_vacancies, lifetime_p25, lifetime_median, lifetime_p75 "
        "FROM fct_vacancy_lifetime",
    )

    # dou:2 lived 2 days, dou:3 lived 3 days; dou:1 is still open and was already listed on day one
    assert rows == [("middle", 2, 2.25, 2.5, 2.75)]


def test_the_market_overview_counts_open_new_and_closed_vacancies_per_day_and_level(
    db: Path,
) -> None:
    _dbt(db, "build", "--vars", SMALL)

    def day(d: int) -> list[tuple]:  # type: ignore[type-arg]
        return _rows(
            db,
            "SELECT source, category, seniority, open_vacancies, new_vacancies, closed_vacancies "
            f"FROM fct_market_daily WHERE date = DATE '2026-11-0{d}' ORDER BY seniority",
        )

    # day 3: dou:1 (senior) and dou:2 (middle) are active, dou:3 (middle) is new
    assert day(3) == [
        ("dou", "unknown", "middle", 2, 1, 0),
        ("dou", "unknown", "senior", 1, 0, 0),
    ]
    # day 5: dou:2 is found closed (missing two days), dou:3 is still listed
    assert day(5) == [
        ("dou", "unknown", "middle", 1, 0, 1),
        ("dou", "unknown", "senior", 1, 0, 0),
    ]


def test_with_the_default_thresholds_these_few_rows_publish_nothing(db: Path) -> None:
    _dbt(db, "build")

    for table in (
        "fct_skill_pairs",
        "fct_salary_by_skill",
        "fct_salary_survey",
        "fct_vacancy_lifetime",
    ):
        assert _rows(db, f"SELECT count(*) FROM {table}") == [(0,)], table
