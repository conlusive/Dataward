from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.rates import load_nbu_rates, missing_rate_dates, needed_rate_dates
from jobmarket.silver.store import SilverStore
from jobmarket.silver.usd import apply_usd, usd_factor
from tests.helpers import sample

RATE_DAY = date(2026, 11, 5)
USD_RATE, EUR_RATE = 45.5375, 51.2489  # UAH per unit, from the recorded NBU file


@pytest.fixture
def bronze(tmp_path: Path) -> BronzeStore:
    store = BronzeStore(tmp_path / "bronze")
    store.write(
        source="nbu_rates",
        run_date=RATE_DAY,
        url="https://bank.gov.ua/x?date=20261105",
        content=sample("nbu/rates_2026-11-05.json"),
        status=200,
        run_id="r1",
        fetched_at=datetime(2026, 11, 5, tzinfo=UTC),
        suffix=".json",
    )
    return store


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    return SilverStore(tmp_path / "test.duckdb")


def _vacancy(
    silver: SilverStore,
    vid: str,
    currency: str,
    low: float | None,
    high: float | None,
    published: date | None = RATE_DAY,
) -> None:
    silver.upsert(
        ParsedVacancy(
            id=vid,
            source="dou",
            url=f"https://jobs.dou.ua/companies/x/vacancies/{vid.split(':')[1]}/",
            title="Dev",
            company="Acme",
            category=None,
            description_text="text",
            published_at=published,
        ),
        run_id="parse-1",
        loaded_at=datetime(2026, 11, 6),
        source_file="dou/f.html",
        fetched_at=datetime(2026, 11, 6),
    )
    silver.set_salaries([(vid, "raw", low, high, currency)])


def _usd(silver: SilverStore, vid: str) -> tuple[object, ...]:
    return (
        silver._con.execute(
            "SELECT salary_usd_min, salary_usd_max FROM silver_vacancies WHERE id = ?", [vid]
        ).fetchone()
        or ()
    )


def test_rates_are_loaded_from_bronze_by_the_date_inside_the_file(
    bronze: BronzeStore, silver: SilverStore
) -> None:
    assert load_nbu_rates(bronze, silver) == 2

    rates = silver.rates(("USD", "EUR"))
    assert rates["USD"] == {RATE_DAY: USD_RATE}
    assert rates["EUR"] == {RATE_DAY: EUR_RATE}


def test_loading_rates_twice_does_not_duplicate(bronze: BronzeStore, silver: SilverStore) -> None:
    load_nbu_rates(bronze, silver)
    load_nbu_rates(bronze, silver)

    assert len(silver.rates(("USD",))["USD"]) == 1


def test_cross_rates_go_through_uah() -> None:
    rates = {"USD": {RATE_DAY: USD_RATE}, "EUR": {RATE_DAY: EUR_RATE}}

    assert usd_factor("USD", RATE_DAY, rates) == 1.0
    assert usd_factor("UAH", RATE_DAY, rates) == pytest.approx(1 / USD_RATE)
    assert usd_factor("EUR", RATE_DAY, rates) == pytest.approx(EUR_RATE / USD_RATE)


def test_usd_needs_no_rate_at_all() -> None:
    assert usd_factor("USD", date(2020, 1, 1), {"USD": {}, "EUR": {}}) == 1.0


def test_a_nearby_earlier_rate_is_used_but_a_stale_one_is_not() -> None:
    rates = {"USD": {RATE_DAY: USD_RATE}, "EUR": {}}

    assert usd_factor("UAH", date(2026, 11, 8), rates) == pytest.approx(1 / USD_RATE)
    assert usd_factor("UAH", date(2026, 11, 20), rates) is None
    assert usd_factor("UAH", date(2026, 11, 1), rates) is None  # earlier than any rate


def test_apply_usd_converts_each_currency(bronze: BronzeStore, silver: SilverStore) -> None:
    _vacancy(silver, "dou:1", "USD", 1000, 2000)
    _vacancy(silver, "dou:2", "UAH", USD_RATE * 2000, None)
    _vacancy(silver, "dou:3", "EUR", 1000, 1500)
    load_nbu_rates(bronze, silver)

    stats = apply_usd(silver)

    assert (stats.converted, stats.missing_rate) == (3, 0)
    assert _usd(silver, "dou:1") == (1000.0, 2000.0)
    assert _usd(silver, "dou:2") == (2000.0, None)
    assert _usd(silver, "dou:3") == (
        pytest.approx(1000 * EUR_RATE / USD_RATE, abs=0.01),
        pytest.approx(1500 * EUR_RATE / USD_RATE, abs=0.01),
    )


def test_missing_rate_leaves_usd_empty_and_reports_the_date(
    bronze: BronzeStore, silver: SilverStore
) -> None:
    _vacancy(silver, "dou:4", "UAH", 90000, 100000, published=date(2026, 9, 1))
    load_nbu_rates(bronze, silver)

    stats = apply_usd(silver)

    assert _usd(silver, "dou:4") == (None, None)
    assert stats.missing_rate == 1 and stats.missing_dates == {date(2026, 9, 1)}


def test_recomputing_is_stable_and_follows_a_changed_salary(
    bronze: BronzeStore, silver: SilverStore
) -> None:
    _vacancy(silver, "dou:5", "UAH", USD_RATE * 1000, None)
    load_nbu_rates(bronze, silver)
    apply_usd(silver)
    first = _usd(silver, "dou:5")
    apply_usd(silver)
    assert _usd(silver, "dou:5") == first

    silver.set_salaries([("dou:5", None, None, None, None)])  # salary no longer found
    apply_usd(silver)

    assert _usd(silver, "dou:5") == (None, None)


def test_publication_date_decides_which_rates_are_needed(
    bronze: BronzeStore, silver: SilverStore
) -> None:
    _vacancy(silver, "dou:6", "USD", 1000, None, published=date(2026, 10, 1))
    _vacancy(silver, "dou:7", "UAH", 50000, None, published=date(2026, 10, 2))
    _vacancy(silver, "dou:8", "EUR", 3000, None, published=RATE_DAY)

    needed = needed_rate_dates(silver)

    assert needed == {date(2026, 10, 2), RATE_DAY}  # USD salaries need no rate
    assert missing_rate_dates(bronze, needed) == [date(2026, 10, 2)]  # 5 Nov is already in bronze
