import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.scrapers.dou_salaries import LISTING_URL, DouSalariesScraper, select_survey_files
from jobmarket.scrapers.nbu import NbuRatesScraper

RUN_DATE = date(2026, 11, 6)


class _NoSleep:
    async def __call__(self, seconds: float) -> None:
        return None


def _scraper_args(
    tmp_path: Path, handler: Callable[[httpx.Request], httpx.Response]
) -> dict[str, object]:
    return {
        "settings": Settings(bronze_dir=tmp_path),
        "store": BronzeStore(tmp_path),
        "run_id": "run-1",
        "run_date": RUN_DATE,
        "client": httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        "sleep": _NoSleep(),
    }


def test_select_prefers_raw_then_final_then_mini() -> None:
    names = [
        "2019_dec_mini.csv",
        "2019_dec_raw.csv",
        "2018_june_final.csv",
        "2018_june_mini.csv",
        "2020_june_mini.csv",
    ]

    assert select_survey_files(names) == [
        "2018_june_final.csv",
        "2019_dec_raw.csv",
        "2020_june_mini.csv",
    ]


def test_select_keeps_all_files_of_wave_without_known_variant() -> None:
    names = ["2022_june_dev.csv", "2022_june_qa.csv", "2022_june_other.csv", "README.md"]

    assert select_survey_files(names) == [
        "2022_june_dev.csv",
        "2022_june_other.csv",
        "2022_june_qa.csv",
    ]


async def test_nbu_scraper_requests_run_date_rates_as_json(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=[{"cc": "USD", "rate": 45.5}])

    async with NbuRatesScraper(**_scraper_args(tmp_path, handler)) as scraper:  # type: ignore[arg-type]
        await scraper.run()

    assert seen == [
        "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date=20261106&json"
    ]
    assert scraper.stats.new == 1
    assert list((tmp_path / "nbu_rates" / "dt=2026-11-06").glob("*.json"))


async def test_dou_salaries_downloads_one_file_per_wave(tmp_path: Path) -> None:
    listing = [
        {"name": "2019_dec_raw.csv", "download_url": "https://raw.example/2019_dec_raw.csv"},
        {"name": "2019_dec_mini.csv", "download_url": "https://raw.example/2019_dec_mini.csv"},
    ]
    downloaded: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == LISTING_URL:
            return httpx.Response(200, text=json.dumps(listing))
        downloaded.append(request.url.path)
        return httpx.Response(200, text="a,b\n1,2\n")

    async with DouSalariesScraper(**_scraper_args(tmp_path, handler)) as scraper:  # type: ignore[arg-type]
        await scraper.run()

    assert downloaded == ["/2019_dec_raw.csv"]
    assert scraper.stats.errors == 0
    assert scraper.stats.pages == 2  # listing + one csv


async def test_dou_salaries_reports_error_when_listing_fails(tmp_path: Path) -> None:
    scraper_args = _scraper_args(tmp_path, lambda r: httpx.Response(404))

    async with DouSalariesScraper(**scraper_args) as scraper:  # type: ignore[arg-type]
        await scraper.run()

    assert scraper.stats.errors == 1
