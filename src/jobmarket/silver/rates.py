"""NBU exchange rates: bronze JSON -> silver_nbu_rates, and which dates are still missing."""

import json
from datetime import date, datetime

from loguru import logger

from jobmarket.bronze import BronzeStore
from jobmarket.silver.store import SilverStore

SOURCE = "nbu_rates"
RATE_CURRENCIES = ("USD", "EUR")  # all that salaries are quoted in, besides UAH itself


def load_nbu_rates(bronze: BronzeStore, silver: SilverStore) -> int:
    """Read every stored NBU file and upsert the USD/EUR rates. Returns rows written."""
    rows: list[tuple[date, str, float]] = []
    for partition in bronze.partition_dates(SOURCE):
        for record in bronze.records(SOURCE, partition):
            if record.meta["status"] != 200:
                continue
            try:
                payload = json.loads(record.content)
                for item in payload:
                    if item["cc"] in RATE_CURRENCIES:
                        rate_date = datetime.strptime(item["exchangedate"], "%d.%m.%Y").date()
                        rows.append((rate_date, item["cc"], float(item["rate"])))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
                logger.warning("unreadable NBU file {}: {!r}", record.meta["file"], exc)
    silver.upsert_rates(rows)
    return len(rows)


def missing_rate_dates(bronze: BronzeStore, needed: set[date]) -> list[date]:
    """Dates that need a rate but have no NBU partition in bronze yet, oldest first."""
    have = set(bronze.partition_dates(SOURCE))
    return sorted(needed - have)


def needed_rate_dates(silver: SilverStore) -> set[date]:
    """Dates for which a non-USD salary needs an NBU rate."""
    return {day for _, currency, _, _, day in silver.salary_rows() if currency != "USD"}
