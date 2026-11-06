"""Source registry: the single place that knows which scrapers exist and which run daily."""

from jobmarket.scrapers.base import BaseScraper
from jobmarket.scrapers.djinni import DjinniScraper
from jobmarket.scrapers.dou import DouScraper
from jobmarket.scrapers.dou_salaries import DouSalariesScraper
from jobmarket.scrapers.nbu import NbuRatesScraper

SOURCES: dict[str, type[BaseScraper]] = {
    scraper.source: scraper
    for scraper in (NbuRatesScraper, DouScraper, DjinniScraper, DouSalariesScraper)
}

# Sources included in ``scrape all``. Survey waves are manual (published twice a year).
DAILY_SOURCES: tuple[str, ...] = (
    NbuRatesScraper.source,
    DouScraper.source,
    DjinniScraper.source,
)
