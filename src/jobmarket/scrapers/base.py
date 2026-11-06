"""BaseScraper: polite async fetching that persists every response into bronze."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from types import TracebackType
from typing import ClassVar, Self

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
)

from jobmarket.bronze import BronzeStore, WriteOutcome
from jobmarket.config import Settings
from jobmarket.ops import ScrapeStats
from jobmarket.robots import RobotsPolicy

Sleep = Callable[[float], Awaitable[None]]


class RetryableHTTPError(Exception):
    """5xx response: worth retrying with backoff."""


class RateLimited(RetryableHTTPError):
    """429 response: wait a long pause before retrying."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content: bytes
    from_cache: bool
    # True when the server redirected the request: the content belongs to another URL.
    redirected: bool = False


class BaseScraper:
    source: ClassVar[str]
    respect_robots: ClassVar[bool] = True

    def __init__(
        self,
        *,
        settings: Settings,
        store: BronzeStore,
        run_id: str,
        run_date: date,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._store = store
        self._run_id = run_id
        self._run_date = run_date
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout_s,
            follow_redirects=True,
        )
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(settings.concurrency)
        self._robots = RobotsPolicy(self._client, settings.user_agent)
        self.stats = ScrapeStats()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def run(self, *, refetch: bool = False) -> None:
        """Fetch everything this source owns for ``run_date`` into bronze."""
        raise NotImplementedError

    async def fetch_details(self, urls: Iterable[str], *, refetch: bool = False) -> None:
        """Fetch vacancy pages, skipping those already stored within the refresh window."""
        unique = list(dict.fromkeys(urls))
        known: set[str] = set()
        if not refetch:
            since = self._run_date - timedelta(days=self._settings.detail_refresh_days)
            known = self._store.known_urls(self.source, since)
        todo = [url for url in unique if url not in known]
        self.stats.skipped += len(unique) - len(todo)
        await asyncio.gather(*(self.fetch(url, refetch=refetch) for url in todo))

    async def fetch(
        self,
        url: str,
        *,
        refetch: bool = False,
        suffix: str = ".html",
        form: Mapping[str, str] | None = None,
    ) -> FetchResult | None:
        """Fetch ``url`` into bronze. Returns None when the page could not be obtained.

        With ``form`` the request is a POST; ``url`` is still the bronze key, so callers make it
        unique per request (e.g. by adding the pagination offset as a query parameter).
        """
        if not refetch:
            cached = self._store.read(self.source, self._run_date, url)
            if cached is not None:
                self.stats.pages += 1
                self.stats.skipped += 1
                return FetchResult(
                    url,
                    int(cached.meta["status"]),
                    cached.content,
                    True,
                    bool(cached.meta.get("redirected", False)),
                )

        if self.respect_robots and not await self._robots.allowed(url):
            logger.warning("robots.txt disallows {}", url)
            self.stats.errors += 1
            return None

        async with self._semaphore:
            try:
                response = await self._request_with_retry(url, form)
            except (httpx.HTTPError, RetryableHTTPError) as exc:
                logger.error("giving up on {}: {!r}", url, exc)
                self.stats.errors += 1
                return None
            await self._sleep(1.0 / self._settings.rate_limit_rps)

        if response.status_code == 403:
            self.stats.http_403 += 1
        outcome = self._store.write(
            source=self.source,
            run_date=self._run_date,
            url=url,
            content=response.content,
            status=response.status_code,
            run_id=self._run_id,
            fetched_at=datetime.now(UTC),
            suffix=suffix,
            redirected=bool(response.history),
        )
        self.stats.pages += 1
        match outcome:
            case WriteOutcome.NEW:
                self.stats.new += 1
            case WriteOutcome.UPDATED:
                self.stats.updated += 1
            case WriteOutcome.UNCHANGED:
                self.stats.unchanged += 1
        return FetchResult(
            url, response.status_code, response.content, False, bool(response.history)
        )

    async def _request_with_retry(self, url: str, form: Mapping[str, str] | None) -> httpx.Response:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._settings.max_attempts),
            wait=self._wait,
            retry=retry_if_exception_type((httpx.TransportError, RetryableHTTPError)),
            sleep=self._sleep,
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                if form is None:
                    response = await self._client.get(url)
                else:
                    response = await self._client.post(
                        url,
                        data=form,
                        headers={"X-Requested-With": "XMLHttpRequest", "Referer": url},
                    )
                if response.status_code == 429:
                    self.stats.http_429 += 1
                    raise RateLimited(url)
                if response.status_code >= 500:
                    raise RetryableHTTPError(f"{response.status_code} for {url}")
                return response
        raise AssertionError("unreachable: AsyncRetrying with reraise=True")

    def _wait(self, state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        if isinstance(exc, RateLimited):
            return self._settings.rate_limit_pause_s
        return min(self._settings.retry_base_s * 2.0**state.attempt_number, 30.0)
