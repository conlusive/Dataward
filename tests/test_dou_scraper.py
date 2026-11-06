from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.scrapers.dou import DouScraper, parse_listing_urls, parse_xhr
from tests.helpers import NoSleep, robots_allow_all, sample, xhr_payload

TOKEN = "tok123"


def test_listing_urls_are_clean_vacancy_links() -> None:
    urls = parse_listing_urls(sample("dou/list_python.html").decode())

    assert len(urls) == 20
    assert all(u.startswith("https://jobs.dou.ua/companies/") and "?" not in u for u in urls)
    assert "https://jobs.dou.ua/companies/solid-software/vacancies/359220/" in urls


def test_xhr_response_gives_urls_batch_size_and_last_flag() -> None:
    urls, size, last = parse_xhr(sample("dou/xhr_python_count20.json"))

    assert len(urls) == 40 and size == 40 and last is False


class _Site:
    """Fake jobs.dou.ua that records what the scraper asked for."""

    def __init__(self, *, last_xhr: bool = True) -> None:
        self.last_xhr = last_xhr
        self.posts: list[dict[str, list[str]]] = []
        self.gets: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if (robots := robots_allow_all(request)) is not None:
            return robots
        if request.method == "POST":
            self.posts.append(parse_qs(request.content.decode()))
            return httpx.Response(200, content=xhr_payload(last=self.last_xhr))
        self.gets.append(str(request.url))
        if request.url.path == "/vacancies/":
            return httpx.Response(
                200,
                content=sample("dou/list_python.html"),
                headers={"Set-Cookie": f"csrftoken={TOKEN}; Domain=.dou.ua; Path=/"},
            )
        return httpx.Response(200, text="<html>vacancy</html>")


def _scraper(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    run_date: date,
    max_list_pages: int | None = None,
) -> DouScraper:
    return DouScraper(
        settings=Settings(bronze_dir=tmp_path, max_list_pages=max_list_pages),
        store=BronzeStore(tmp_path),
        run_id="run-1",
        run_date=run_date,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://jobs.dou.ua"
        ),
        sleep=NoSleep(),
    )


@pytest.fixture(autouse=True)
def _one_category(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jobmarket.scrapers.dou.CATEGORIES", ("Python",))


async def test_run_follows_xhr_with_csrf_and_fetches_every_vacancy(tmp_path: Path) -> None:
    site = _Site(last_xhr=True)

    async with _scraper(tmp_path, site, date(2026, 11, 6)) as scraper:
        await scraper.run()

    assert len(site.posts) == 1
    assert site.posts[0]["count"] == ["20"]
    assert site.posts[0]["csrfmiddlewaretoken"] == [TOKEN]
    vacancy_gets = [
        u for u in site.gets if "/vacancies/" in u and u.rstrip("/").split("/")[-1].isdigit()
    ]
    assert len(vacancy_gets) == 60  # 20 from the listing page + 40 from XHR
    assert scraper.stats.errors == 0


async def test_pagination_continues_with_offset_until_last(tmp_path: Path) -> None:
    site = _Site(last_xhr=False)

    async with _scraper(tmp_path, site, date(2026, 11, 6), max_list_pages=3) as scraper:
        await scraper.run()

    assert [p["count"] for p in site.posts] == [["20"], ["60"]]  # 20, then 20 + batch of 40


async def test_second_run_same_date_makes_no_network_calls(tmp_path: Path) -> None:
    first = _Site()
    async with _scraper(tmp_path, first, date(2026, 11, 6)) as scraper:
        await scraper.run()

    second = _Site()
    async with _scraper(tmp_path, second, date(2026, 11, 6)) as scraper:
        await scraper.run()

    assert second.gets == [] and second.posts == []


async def test_next_day_refetches_listing_but_skips_recent_vacancy_pages(tmp_path: Path) -> None:
    async with _scraper(tmp_path, _Site(), date(2026, 11, 6)) as scraper:
        await scraper.run()

    next_day = _Site()
    async with _scraper(tmp_path, next_day, date(2026, 11, 7)) as scraper:
        await scraper.run()

    vacancy_gets = [u for u in next_day.gets if u.rstrip("/").split("/")[-1].isdigit()]
    assert vacancy_gets == []
    assert scraper.stats.skipped == 60


async def test_missing_csrf_cookie_is_reported_as_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (robots := robots_allow_all(request)) is not None:
            return robots
        if request.url.path == "/vacancies/":
            return httpx.Response(200, content=sample("dou/list_python.html"))
        return httpx.Response(200, text="x")

    async with _scraper(tmp_path, handler, date(2026, 11, 6)) as scraper:
        await scraper.run()

    assert scraper.stats.errors == 1
