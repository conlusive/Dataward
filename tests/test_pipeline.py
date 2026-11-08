from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.ops import OpsStore
from jobmarket.silver.pipeline import run_parse
from jobmarket.silver.sightings import listed_vacancy_ids
from tests.helpers import sample

DOU_LIST = "https://jobs.dou.ua/vacancies/?category=Python"
DOU_XHR = "https://jobs.dou.ua/vacancies/xhr-load/?category=Python&count=20"
DOU_VACANCY = "https://jobs.dou.ua/companies/solid-software/vacancies/359220/"
DJINNI_LIST = "https://djinni.co/jobs/?primary_keyword=Python"
DJINNI_VACANCY = "https://djinni.co/jobs/857083-python-spark-ai-developer_tt/"


def _put(
    store: BronzeStore,
    source: str,
    day: date,
    url: str,
    content: bytes,
    *,
    status: int = 200,
    redirected: bool = False,
    suffix: str = ".html",
) -> None:
    store.write(
        source=source,
        run_date=day,
        url=url,
        content=content,
        status=status,
        run_id="r1",
        fetched_at=datetime(day.year, day.month, day.day, 8, tzinfo=UTC),
        suffix=suffix,
        redirected=redirected,
    )


def _dou_day(store: BronzeStore, day: date) -> None:
    _put(store, "dou", day, DOU_LIST, sample("dou/list_python.html"))
    _put(store, "dou", day, DOU_XHR, sample("dou/xhr_python_count20.json"), suffix=".json")
    _put(store, "dou", day, DOU_VACANCY, sample("dou/detail.html"))


def test_listing_pages_give_the_ids_of_everything_listed_that_day(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path / "bronze")
    day = date(2026, 11, 1)
    _dou_day(store, day)

    ids = listed_vacancy_ids(store, "dou", day)

    assert len(ids) == 60 and "dou:359220" in ids  # 20 from the page, 40 from the XHR batch
    assert all(i.startswith("dou:") for i in ids)


def test_djinni_listing_page_and_unusable_pages(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path / "bronze")
    day = date(2026, 11, 1)
    _put(store, "djinni", day, DJINNI_LIST, sample("djinni/list_python.html"))
    _put(store, "djinni", day, DJINNI_VACANCY, sample("djinni/detail.html"))  # not a listing
    _put(
        store,
        "djinni",
        day,
        DJINNI_LIST + "&page=2",
        sample("djinni/list_python.html"),
        redirected=True,
    )
    _put(
        store, "djinni", day, DJINNI_LIST + "&page=3", sample("djinni/list_python.html"), status=403
    )

    ids = listed_vacancy_ids(store, "djinni", day)

    assert len(ids) >= 10 and "djinni:857083" in ids
    assert all(i.startswith("djinni:") for i in ids)


def test_a_day_without_listing_pages_lists_nothing(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path / "bronze")
    _put(store, "dou", date(2026, 11, 1), DOU_VACANCY, sample("dou/detail.html"))

    assert listed_vacancy_ids(store, "dou", date(2026, 11, 1)) == []


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    store = BronzeStore(tmp_path / "bronze")
    _dou_day(store, date(2026, 11, 1))
    _dou_day(store, date(2026, 11, 2))
    return Settings(bronze_dir=tmp_path / "bronze", duckdb_path=tmp_path / "test.duckdb")


def _scalar(settings: Settings, sql: str) -> object:
    con = duckdb.connect(str(settings.duckdb_path), read_only=True)
    try:
        row = con.execute(sql).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def test_missing_days_are_parsed_once_and_everything_is_filled(settings: Settings) -> None:
    assert run_parse(settings, ["dou"], date(2026, 11, 2), missing=True) == 0

    assert _scalar(settings, "SELECT count(*) FROM silver_vacancies") == 1
    assert (
        _scalar(settings, "SELECT count(*) FROM silver_vacancy_sightings") == 120
    )  # 60 ids x 2 days
    assert _scalar(settings, "SELECT count(DISTINCT seen_date) FROM silver_vacancy_sightings") == 2
    assert (
        _scalar(
            settings, "SELECT count(*) FROM silver_vacancy_skills WHERE vacancy_id = 'dou:359220'"
        )
        != 0
    )
    assert _scalar(settings, "SELECT seniority FROM silver_vacancies") == "senior"
    assert _scalar(settings, "SELECT dedup_group_id FROM silver_vacancies") == "dou:359220"
    assert (
        _scalar(
            settings,
            "SELECT count(*) FROM ops_task_runs WHERE task = 'parse' AND status = 'success'",
        )
        == 2
    )


def test_running_it_again_does_not_parse_the_same_days_twice(settings: Settings) -> None:
    run_parse(settings, ["dou"], date(2026, 11, 2), missing=True)
    before = _scalar(settings, "SELECT count(*) FROM ops_task_runs WHERE task = 'parse'")

    run_parse(settings, ["dou"], date(2026, 11, 2), missing=True)

    assert _scalar(settings, "SELECT count(*) FROM ops_task_runs WHERE task = 'parse'") == before
    assert _scalar(settings, "SELECT count(*) FROM silver_vacancies") == 1
    assert _scalar(settings, "SELECT count(*) FROM silver_vacancy_sightings") == 120


def test_an_explicit_day_is_parsed_again_as_a_new_attempt(settings: Settings) -> None:
    run_parse(settings, ["dou"], date(2026, 11, 1))
    run_parse(settings, ["dou"], date(2026, 11, 1))

    attempts = _scalar(
        settings,
        "SELECT max(attempt) FROM ops_task_runs "
        "WHERE task = 'parse' AND run_date = DATE '2026-11-01'",
    )
    assert attempts == 2
    assert _scalar(settings, "SELECT count(*) FROM silver_vacancy_sightings") == 60


def test_parsed_dates_only_count_runs_that_need_no_repeating(tmp_path: Path) -> None:
    ops = OpsStore(tmp_path / "ops.duckdb")
    today = date(2026, 11, 10)

    def run(day: date, status: str) -> None:
        task = ops.start_task("parse", "dou", day)
        ops.finish_task(task, status, rows_in=1, rows_out=1, rows_failed=0)

    run(date(2026, 11, 1), "success")
    run(date(2026, 11, 2), "failed")  # a crash is always tried again
    run(date(2026, 11, 3), "partial")  # old enough: pages that stay unreadable are left alone
    run(date(2026, 11, 8), "partial")  # recent: a parser fix gets another chance
    ops.start_task("parse", "dou", date(2026, 11, 4))  # still "running": it crashed midway

    assert ops.parsed_dates("dou", today=today) == {date(2026, 11, 1), date(2026, 11, 3)}
    assert ops.parsed_dates("djinni", today=today) == set()
    ops.close()


def _day_with_pages(tmp_path: Path, good: int, broken: int) -> Settings:
    store = BronzeStore(tmp_path / "bronze")
    day = date(2026, 11, 1)
    for i in range(good):
        _put(
            store,
            "dou",
            day,
            f"https://jobs.dou.ua/companies/acme/vacancies/{1000 + i}/",
            sample("dou/detail.html"),
        )
    for i in range(broken):
        _put(
            store,
            "dou",
            day,
            f"https://jobs.dou.ua/companies/acme/vacancies/{2000 + i}/",
            b"<html>new markup</html>",
        )
    return Settings(bronze_dir=tmp_path / "bronze", duckdb_path=tmp_path / "test.duckdb")


def test_a_few_unreadable_pages_do_not_fail_the_run(tmp_path: Path) -> None:
    settings = _day_with_pages(tmp_path, good=40, broken=1)  # 2.4% of the pages

    assert run_parse(settings, ["dou"], date(2026, 11, 1)) == 0
    assert _scalar(settings, "SELECT count(*) FROM silver_vacancies") == 40
    assert _scalar(settings, "SELECT status FROM ops_task_runs WHERE task = 'parse'") == "partial"


def test_many_unreadable_pages_mean_the_markup_changed_and_fail_the_run(tmp_path: Path) -> None:
    settings = _day_with_pages(tmp_path, good=10, broken=3)  # 23% of the pages

    assert run_parse(settings, ["dou"], date(2026, 11, 1)) == 1


def test_a_day_where_nothing_can_be_read_fails_the_run(tmp_path: Path) -> None:
    settings = _day_with_pages(tmp_path, good=0, broken=5)

    assert run_parse(settings, ["dou"], date(2026, 11, 1)) == 1


def test_a_recent_partial_day_is_parsed_again_and_picks_up_what_was_fixed(tmp_path: Path) -> None:
    settings = _day_with_pages(tmp_path, good=40, broken=1)
    assert run_parse(settings, ["dou"], date(2026, 11, 1), missing=True) == 0
    assert _scalar(settings, "SELECT count(*) FROM silver_vacancies") == 40

    # the "parser fix": the page that used to fail now looks like a normal vacancy
    store = BronzeStore(tmp_path / "bronze")
    _put(
        store,
        "dou",
        date(2026, 11, 1),
        "https://jobs.dou.ua/companies/acme/vacancies/2000/",
        sample("dou/detail.html"),
    )
    run_parse(settings, ["dou"], date(2026, 11, 2), missing=True)

    assert _scalar(settings, "SELECT count(*) FROM silver_vacancies") == 41


def test_a_backfill_reparses_exactly_the_stored_days_in_its_range(tmp_path: Path) -> None:
    store = BronzeStore(tmp_path / "bronze")
    for day in (date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)):
        _dou_day(store, day)
    settings = Settings(bronze_dir=tmp_path / "bronze", duckdb_path=tmp_path / "test.duckdb")
    run_parse(settings, ["dou"], date(2026, 11, 3), missing=True)  # all three days are parsed

    # the range covers two stored days and one day that was never stored (Nov 10)
    code = run_parse(
        settings, ["dou"], date(2026, 11, 10), date_range=(date(2026, 11, 2), date(2026, 11, 10))
    )

    assert code == 0
    days = _scalar(
        settings,
        "SELECT list(run_date ORDER BY run_date) FROM ops_task_runs "
        "WHERE task = 'parse' AND attempt = 2",
    )
    assert [d.isoformat() for d in days] == ["2026-11-02", "2026-11-03"]  # type: ignore[attr-defined]
