"""jobs.dou.ua: per-category listing (first page as HTML, the rest via XHR) and vacancy pages."""

import json
from typing import ClassVar
from urllib.parse import quote, urlsplit, urlunsplit

from loguru import logger
from selectolax.lexbor import LexborHTMLParser

from jobmarket.scrapers.base import BaseScraper

CATEGORIES = (
    "Python",
    "Java",
    "Data Science",
    "DevOps",
    "DBA",
    "QA",
    "Front End",
    ".NET",
    "Node.js",
    "PHP",
    "C++",
    "Golang",
    "Ruby",
    "Scala",
    "Android",
    "iOS",
)
LIST_URL = "https://jobs.dou.ua/vacancies/?category={category}"
XHR_URL = "https://jobs.dou.ua/vacancies/xhr-load/?category={category}&count={count}"
FIRST_XHR_COUNT = 20  # the HTML listing page already contains the first 20 vacancies


def parse_listing_urls(html: str) -> list[str]:
    """Vacancy page URLs from a listing fragment, without tracking query strings."""
    urls: list[str] = []
    for link in LexborHTMLParser(html).css("li.l-vacancy a.vt"):
        href = link.attributes.get("href")
        if href:
            parts = urlsplit(href)
            urls.append(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))
    return urls


def parse_xhr(content: bytes) -> tuple[list[str], int, bool]:
    """(vacancy URLs, number of vacancies in this batch, is_last) from an XHR response."""
    payload = json.loads(content)
    return parse_listing_urls(payload["html"]), int(payload["num"]), bool(payload["last"])


class DouScraper(BaseScraper):
    source: ClassVar[str] = "dou"

    async def run(self, *, refetch: bool = False) -> None:
        for category in CATEGORIES:
            urls = await self._category_urls(category, refetch=refetch)
            if urls:
                logger.info("dou {}: {} vacancies listed", category, len(urls))
            else:
                logger.warning("dou {}: no vacancies listed, is the category name valid?", category)
            await self.fetch_details(urls, refetch=refetch)

    async def _category_urls(self, category: str, *, refetch: bool) -> list[str]:
        encoded = quote(category, safe="")
        list_url = LIST_URL.format(category=encoded)
        refetch = refetch or self._settings.refresh_listings  # listings only: details stay skipped
        page = await self.fetch(list_url, refetch=refetch)
        if page is None or page.status != 200:
            logger.error("dou {}: listing unavailable", category)
            self.stats.errors += 1
            return []
        urls = parse_listing_urls(page.content.decode("utf-8"))

        count = FIRST_XHR_COUNT
        pages_loaded = 1
        max_pages = self._settings.max_list_pages
        while max_pages is None or pages_loaded < max_pages:
            xhr_url = XHR_URL.format(category=encoded, count=count)
            form = {"count": str(count)}
            if refetch or not self._store.exists(self.source, self._run_date, xhr_url):
                token = await self._csrf_token(list_url)
                if token is None:
                    self.stats.errors += 1
                    break
                form["csrfmiddlewaretoken"] = token
            result = await self.fetch(xhr_url, refetch=refetch, suffix=".json", form=form)
            if result is None or result.status != 200:
                break
            batch_urls, batch_size, is_last = parse_xhr(result.content)
            urls.extend(batch_urls)
            pages_loaded += 1
            if is_last or batch_size == 0:
                break
            count += batch_size
        return list(dict.fromkeys(urls))

    async def _csrf_token(self, list_url: str) -> str | None:
        """CSRF token from the cookie set by the listing page; primes the cookie if missing."""
        token = self._client.cookies.get("csrftoken")
        if token is None:
            await self._client.get(list_url)
            token = self._client.cookies.get("csrftoken")
        if token is None:
            logger.error("dou: no csrftoken cookie after loading {}", list_url)
        return token
