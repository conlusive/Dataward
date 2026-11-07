from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.salary_step import apply_salaries
from jobmarket.silver.store import SilverStore


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    return SilverStore(tmp_path / "test.duckdb")


def _add(
    silver: SilverStore, vid: str, *, description: str, raw: str | None = None, title: str = "Dev"
) -> None:
    silver.upsert(
        ParsedVacancy(
            id=vid,
            source="dou",
            url=f"https://jobs.dou.ua/companies/x/vacancies/{vid.split(':')[1]}/",
            title=title,
            company="Acme",
            category="Python",
            description_text=description,
            salary_raw=raw,
        ),
        run_id="parse-1",
        loaded_at=datetime(2026, 11, 6),
        source_file="dou/f.html",
        fetched_at=datetime(2026, 11, 6, tzinfo=UTC).replace(tzinfo=None),
    )


def _salary(silver: SilverStore, vid: str) -> tuple[object, ...]:
    return (
        silver._con.execute(
            "SELECT salary_raw, salary_min, salary_max, salary_currency "
            "FROM silver_vacancies WHERE id = ?",
            [vid],
        ).fetchone()
        or ()
    )


def test_declared_range_is_parsed_without_needing_a_pay_word(silver: SilverStore) -> None:
    _add(silver, "dou:1", description="No money talk here.", raw="550-700 USD/MONTH")

    stats = apply_salaries(silver, "dou")

    assert _salary(silver, "dou:1") == ("550-700 USD/MONTH", 550.0, 700.0, "USD")
    assert (stats.declared, stats.from_text, stats.without) == (1, 0, 0)


def test_salary_in_description_is_found_and_its_fragment_is_kept(silver: SilverStore) -> None:
    _add(silver, "dou:2", description="We offer.\nSalary from $1000 with regular reviews.")

    stats = apply_salaries(silver, "dou")

    raw, low, high, currency = _salary(silver, "dou:2")
    assert (low, high, currency) == (1000.0, None, "USD") and "$1000" in str(raw)
    assert stats.from_text == 1


def test_amount_without_pay_word_in_description_is_ignored(silver: SilverStore) -> None:
    _add(silver, "dou:3", description="Referral bonus $500 for every hire.")

    stats = apply_salaries(silver, "dou")

    assert _salary(silver, "dou:3") == (None, None, None, None)
    assert stats.without == 1


def test_recomputing_gives_the_same_result_and_clears_stale_values(silver: SilverStore) -> None:
    _add(silver, "dou:4", description="Salary: $3000-4000")
    apply_salaries(silver, "dou")
    first = _salary(silver, "dou:4")
    apply_salaries(silver, "dou")
    assert _salary(silver, "dou:4") == first

    _add(silver, "dou:4", description="Salary is discussed at the interview")  # description changed
    apply_salaries(silver, "dou")

    assert _salary(silver, "dou:4") == (None, None, None, None)


def test_a_source_without_vacancies_is_a_no_op(silver: SilverStore) -> None:
    stats = apply_salaries(silver, "dou")

    assert stats.vacancies == 0
