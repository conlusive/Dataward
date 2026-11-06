"""NBU official exchange rates (all currencies for the run date) into bronze as raw JSON."""

from typing import ClassVar

from jobmarket.scrapers.base import BaseScraper

RATES_URL = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date={date}&json"


class NbuRatesScraper(BaseScraper):
    source: ClassVar[str] = "nbu_rates"
    respect_robots: ClassVar[bool] = False  # documented public API

    async def run(self, *, refetch: bool = False) -> None:
        url = RATES_URL.format(date=self._run_date.strftime("%Y%m%d"))
        await self.fetch(url, refetch=refetch, suffix=".json")
