"""DOU salary survey waves (github.com/devua/csv) into bronze as raw CSV.

Surveys are published twice a year, so this source is run manually, not in the daily flow.
"""

import asyncio
import json
from collections import defaultdict
from collections.abc import Iterable
from typing import Any, ClassVar

from loguru import logger

from jobmarket.scrapers.base import BaseScraper

LISTING_URL = "https://api.github.com/repos/devua/csv/contents/salaries"
# One file per survey wave: the least processed variant that exists.
KIND_PREFERENCE = ("raw", "final", "clean", "mini")


def select_survey_files(names: Iterable[str]) -> list[str]:
    """Pick one CSV per wave (``YYYY_month``); waves without a known variant keep all files."""
    waves: dict[str, dict[str, str]] = defaultdict(dict)
    for name in names:
        if not name.endswith(".csv"):
            continue
        parts = name.removesuffix(".csv").split("_", 2)
        if len(parts) < 3:
            continue
        waves[f"{parts[0]}_{parts[1]}"][parts[2]] = name

    selected: list[str] = []
    for wave in sorted(waves):
        variants = waves[wave]
        preferred = next((variants[kind] for kind in KIND_PREFERENCE if kind in variants), None)
        selected.extend([preferred] if preferred else sorted(variants.values()))
    return selected


class DouSalariesScraper(BaseScraper):
    source: ClassVar[str] = "dou_salaries"
    respect_robots: ClassVar[bool] = False  # GitHub API and raw files, not a crawled site

    async def run(self, *, refetch: bool = False) -> None:
        listing = await self.fetch(LISTING_URL, refetch=refetch, suffix=".json")
        if listing is None or listing.status != 200:
            logger.error("cannot list DOU survey files (status {})", listing and listing.status)
            self.stats.errors += 1
            return

        items: list[dict[str, Any]] = json.loads(listing.content)
        urls = {item["name"]: item["download_url"] for item in items if item.get("download_url")}
        await asyncio.gather(
            *(
                self.fetch(urls[name], refetch=refetch, suffix=".csv")
                for name in select_survey_files(urls)
            )
        )
