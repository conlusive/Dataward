from datetime import date
from pathlib import Path

import httpx
import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.config import Settings
from jobmarket.scrapers.dou_salaries import LISTING_URL, DouSalariesScraper
from tests.helpers import NoSleep

RAW = "https://raw.githubusercontent.com/devua/csv/master/salaries/2024_june_raw.csv"
LISTING = b'[{"name": "2024_june_raw.csv", "download_url": "' + RAW.encode() + b'"}]'


class _Site:
    def __init__(self) -> None:
        self.authorization: dict[str, str | None] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.authorization[request.url.host] = request.headers.get("Authorization")
        if str(request.url) == LISTING_URL:
            return httpx.Response(200, content=LISTING)
        return httpx.Response(200, content=b"a,b\n1,2\n")


async def _run(tmp_path: Path) -> _Site:
    site = _Site()
    scraper = DouSalariesScraper(
        settings=Settings(bronze_dir=tmp_path),
        store=BronzeStore(tmp_path),
        run_id="run-1",
        run_date=date(2026, 11, 20),
        client=httpx.AsyncClient(transport=httpx.MockTransport(site), follow_redirects=True),
        sleep=NoSleep(),
    )
    async with scraper:
        await scraper.run()
    return site


async def test_the_github_api_is_called_with_the_runs_token_and_the_file_host_never_sees_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")

    site = await _run(tmp_path)

    assert site.authorization["api.github.com"] == "Bearer t0ken"  # 5 000 an hour, not 60
    assert site.authorization["raw.githubusercontent.com"] is None  # the token stays at the API


async def test_without_a_token_the_listing_is_still_asked_for_anonymously(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    site = await _run(tmp_path)

    assert site.authorization["api.github.com"] is None
