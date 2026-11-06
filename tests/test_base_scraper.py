from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import ClassVar

import httpx

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.scrapers.base import BaseScraper

RUN_DATE = date(2026, 11, 6)
PAGE = "https://example.com/page"
ROBOTS_ALLOW = httpx.Response(200, text="User-agent: *\nAllow: /\n")


class DummyScraper(BaseScraper):
    source: ClassVar[str] = "dummy"


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _make(
    tmp_path: Path, handler: Callable[[httpx.Request], httpx.Response], sleeps: Sleeps
) -> DummyScraper:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DummyScraper(
        settings=Settings(bronze_dir=tmp_path, rate_limit_rps=2.0, rate_limit_pause_s=60.0),
        store=BronzeStore(tmp_path),
        run_id="run-1",
        run_date=RUN_DATE,
        client=client,
        sleep=sleeps,
    )


def _router(
    page: Callable[[httpx.Request], httpx.Response],
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return ROBOTS_ALLOW
        return page(request)

    return handler


async def test_fetch_stores_page_and_counts_it_as_new(tmp_path: Path) -> None:
    sleeps = Sleeps()
    scraper = _make(tmp_path, _router(lambda r: httpx.Response(200, text="hello")), sleeps)

    result = await scraper.fetch(PAGE)

    assert result is not None and result.content == b"hello" and not result.from_cache
    assert scraper.stats.pages == 1 and scraper.stats.new == 1
    assert sleeps.calls == [0.5]  # 1 / rate_limit_rps


async def test_second_fetch_same_date_uses_bronze_without_network(tmp_path: Path) -> None:
    hits: list[str] = []

    def page(request: httpx.Request) -> httpx.Response:
        hits.append(str(request.url))
        return httpx.Response(200, text="hello")

    scraper = _make(tmp_path, _router(page), Sleeps())
    await scraper.fetch(PAGE)
    again = await scraper.fetch(PAGE)

    assert again is not None and again.from_cache
    assert hits == [PAGE]
    assert scraper.stats.skipped == 1


async def test_refetch_forces_download_and_detects_change(tmp_path: Path) -> None:
    bodies = iter(["v1", "v2"])
    scraper = _make(tmp_path, _router(lambda r: httpx.Response(200, text=next(bodies))), Sleeps())

    await scraper.fetch(PAGE)
    await scraper.fetch(PAGE, refetch=True)

    assert scraper.stats.updated == 1


async def test_server_error_is_retried_then_succeeds(tmp_path: Path) -> None:
    statuses = iter([500, 502, 200])
    sleeps = Sleeps()
    scraper = _make(tmp_path, _router(lambda r: httpx.Response(next(statuses), text="ok")), sleeps)

    result = await scraper.fetch(PAGE)

    assert result is not None and result.status == 200
    assert scraper.stats.errors == 0


async def test_gives_up_after_max_attempts_and_counts_error(tmp_path: Path) -> None:
    calls = 0

    def page(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    scraper = _make(tmp_path, _router(page), Sleeps())

    assert await scraper.fetch(PAGE) is None
    assert calls == 4
    assert scraper.stats.errors == 1 and scraper.stats.pages == 0


async def test_429_pauses_for_a_minute_and_is_counted(tmp_path: Path) -> None:
    statuses = iter([429, 200])
    sleeps = Sleeps()
    scraper = _make(tmp_path, _router(lambda r: httpx.Response(next(statuses), text="ok")), sleeps)

    result = await scraper.fetch(PAGE)

    assert result is not None and result.status == 200
    assert 60.0 in sleeps.calls
    assert scraper.stats.http_429 == 1


async def test_403_is_stored_with_status_and_counted_without_retry(tmp_path: Path) -> None:
    calls = 0

    def page(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403, text="forbidden")

    scraper = _make(tmp_path, _router(page), Sleeps())

    result = await scraper.fetch(PAGE)

    assert result is not None and result.status == 403
    assert calls == 1
    assert scraper.stats.http_403 == 1
    record = BronzeStore(tmp_path).read("dummy", RUN_DATE, PAGE)
    assert record is not None and record.meta["status"] == 403


async def test_robots_disallow_blocks_the_request(tmp_path: Path) -> None:
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /page\n")
        hits.append(request.url.path)
        return httpx.Response(200)

    scraper = _make(tmp_path, handler, Sleeps())

    assert await scraper.fetch(PAGE) is None
    assert hits == []
    assert scraper.stats.errors == 1


async def test_robots_5xx_means_disallow_everything(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    scraper = _make(tmp_path, handler, Sleeps())

    assert await scraper.fetch(PAGE) is None


async def test_redirect_is_recorded_in_bronze_and_visible_from_cache(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return ROBOTS_ALLOW
        if request.url.path == "/page":
            return httpx.Response(302, headers={"Location": "/other"})
        return httpx.Response(200, text="elsewhere")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    scraper = DummyScraper(
        settings=Settings(bronze_dir=tmp_path),
        store=BronzeStore(tmp_path),
        run_id="run-1",
        run_date=RUN_DATE,
        client=client,
        sleep=Sleeps(),
    )

    first = await scraper.fetch(PAGE)
    again = await scraper.fetch(PAGE)

    assert first is not None and first.redirected
    assert again is not None and again.from_cache and again.redirected
