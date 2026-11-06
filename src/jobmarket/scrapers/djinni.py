"""djinni.co: paginated listing per primary keyword, then public vacancy pages.

A vacancy page that answers 403 is kept in bronze with its status; the listing page already
holds the card, which is all we get for such vacancies.
"""

import re
from typing import ClassVar
from urllib.parse import quote

from loguru import logger
from selectolax.lexbor import LexborHTMLParser

from jobmarket.scrapers.base import BaseScraper

BASE_URL = "https://djinni.co"
KEYWORDS = (
    "Python",
    "Java",
    "Data Science",
    "DevOps",
    "QA Manual",
    "QA Automation",
    "Fullstack",
    "JavaScript",
    ".NET",
    "PHP",
    "C++",
    "Golang",
    "Ruby",
    "Scala",
    "Android",
    "iOS",
)
LIST_URL = BASE_URL + "/jobs/?primary_keyword={keyword}"
_VACANCY_PATH = re.compile(r"^/jobs/\d+-[^/]+/$")


def parse_listing_urls(html: str) -> list[str]:
    """Absolute vacancy URLs from a listing page, in page order, without duplicates."""
    urls: list[str] = []
    for link in LexborHTMLParser(html).css(".job-item a[href^='/jobs/']"):
        href = link.attributes.get("href") or ""
        if _VACANCY_PATH.match(href):
            urls.append(BASE_URL + href)
    return list(dict.fromkeys(urls))


class DjinniScraper(BaseScraper):
    source: ClassVar[str] = "djinni"

    async def run(self, *, refetch: bool = False) -> None:
        for keyword in KEYWORDS:
            urls = await self._keyword_urls(keyword, refetch=refetch)
            if urls:
                logger.info("djinni {}: {} vacancies listed", keyword, len(urls))
            else:
                logger.warning("djinni {}: no vacancies listed, is the keyword valid?", keyword)
            await self.fetch_details(urls, refetch=refetch)

    async def _keyword_urls(self, keyword: str, *, refetch: bool) -> list[str]:
        base_url = LIST_URL.format(keyword=quote(keyword, safe=""))
        seen: dict[str, None] = {}
        page_number = 1
        max_pages = self._settings.max_list_pages
        while max_pages is None or page_number <= max_pages:
            url = base_url if page_number == 1 else f"{base_url}&page={page_number}"
            page = await self.fetch(url, refetch=refetch)
            if page is None or page.status != 200:
                if page is None or page_number == 1:
                    self.stats.errors += 1
                break
            new_urls = [
                u for u in parse_listing_urls(page.content.decode("utf-8")) if u not in seen
            ]
            if not new_urls:  # past the last page, or the site repeats the previous one
                break
            seen.update(dict.fromkeys(new_urls))
            page_number += 1
        return list(seen)
