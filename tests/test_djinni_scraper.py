from datetime import date
from pathlib import Path

import httpx
import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.scrapers.djinni import DjinniScraper, parse_listing_urls
from tests.helpers import NoSleep, robots_allow_all, sample

EMPTY_PAGE = b"<html><body><ul></ul></body></html>"


def test_listing_urls_contain_only_vacancy_pages() -> None:
    urls = parse_listing_urls(sample("djinni/list_python.html").decode())

    assert len(urls) >= 10
    assert all(u.startswith("https://djinni.co/jobs/") for u in urls)
    assert "https://djinni.co/jobs/857083-python-spark-ai-developer_tt/" in urls
    assert not any("rss" in u or "europe-remote" in u or "primary_keyword" in u for u in urls)


class _Site:
    def __init__(self, *, vacancy_status: int = 200) -> None:
        self.vacancy_status = vacancy_status
        self.list_pages: list[str] = []
        self.vacancy_gets: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if (robots := robots_allow_all(request)) is not None:
            return robots
        if request.url.path == "/jobs/":
            page = request.url.params.get("page", "1")
            self.list_pages.append(page)
            body = sample("djinni/list_python.html") if page == "1" else EMPTY_PAGE
            return httpx.Response(200, content=body)
        self.vacancy_gets.append(request.url.path)
        return httpx.Response(self.vacancy_status, content=sample("djinni/detail.html"))


def _scraper(tmp_path: Path, site: _Site, settings: Settings | None = None) -> DjinniScraper:
    return DjinniScraper(
        settings=settings or Settings(bronze_dir=tmp_path),
        store=BronzeStore(tmp_path),
        run_id="run-1",
        run_date=date(2026, 11, 6),
        client=httpx.AsyncClient(transport=httpx.MockTransport(site)),
        sleep=NoSleep(),
    )


@pytest.fixture(autouse=True)
def _one_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jobmarket.scrapers.djinni.KEYWORDS", ("Python",))


async def test_run_stops_at_first_empty_page_and_fetches_each_vacancy_once(tmp_path: Path) -> None:
    site = _Site()

    async with _scraper(tmp_path, site) as scraper:
        await scraper.run()

    assert site.list_pages == ["1", "2"]
    expected = len(parse_listing_urls(sample("djinni/list_python.html").decode()))
    assert len(site.vacancy_gets) == expected
    assert scraper.stats.errors == 0


async def test_max_list_pages_limits_pagination(tmp_path: Path) -> None:
    site = _Site()
    settings = Settings(bronze_dir=tmp_path, max_list_pages=1)

    async with _scraper(tmp_path, site, settings) as scraper:
        await scraper.run()

    assert site.list_pages == ["1"]


async def test_forbidden_vacancy_is_stored_with_status_and_counted(tmp_path: Path) -> None:
    site = _Site(vacancy_status=403)

    async with _scraper(tmp_path, site) as scraper:
        await scraper.run()

    assert scraper.stats.http_403 == len(site.vacancy_gets) > 0
    url = "https://djinni.co/jobs/857083-python-spark-ai-developer_tt/"
    record = BronzeStore(tmp_path).read("djinni", date(2026, 11, 6), url)
    assert record is not None and record.meta["status"] == 403
