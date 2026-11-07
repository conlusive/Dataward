"""salary_usd_min/max from salary_min/max, using the NBU rate on the publication date."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from jobmarket.silver.rates import RATE_CURRENCIES
from jobmarket.silver.store import SilverStore

MAX_RATE_GAP_DAYS = 7  # NBU publishes daily; a bigger gap means the rate file is missing


@dataclass
class UsdStats:
    converted: int = 0
    missing_rate: int = 0
    missing_dates: set[date] = field(default_factory=set)


def _rate_on(rates: dict[date, float], day: date) -> float | None:
    """The rate for ``day``, or the latest earlier one within MAX_RATE_GAP_DAYS."""
    for back in range(MAX_RATE_GAP_DAYS + 1):
        found = rates.get(day - timedelta(days=back))
        if found is not None:
            return found
    return None


def usd_factor(currency: str, day: date, rates: dict[str, dict[date, float]]) -> float | None:
    """How many USD one unit of ``currency`` is worth; None when the needed rate is missing."""
    if currency == "USD":
        return 1.0
    usd = _rate_on(rates["USD"], day)
    if usd is None:
        return None
    if currency == "UAH":
        return 1.0 / usd
    if currency in RATE_CURRENCIES:
        other = _rate_on(rates[currency], day)
        return None if other is None else other / usd
    return None


def apply_usd(silver: SilverStore, source: str | None = None) -> UsdStats:
    """Recompute the USD columns (deterministic; clears values whose rate disappeared)."""
    silver.clear_usd_without_salary(source)
    rates = silver.rates(RATE_CURRENCIES)
    stats = UsdStats()
    updates: list[tuple[str, float | None, float | None]] = []
    for vacancy_id, currency, low, high, day in silver.salary_rows(source):
        factor = usd_factor(currency, day, rates)
        if factor is None:
            stats.missing_rate += 1
            stats.missing_dates.add(day)
            updates.append((vacancy_id, None, None))
            continue
        stats.converted += 1
        updates.append(
            (
                vacancy_id,
                round(low * factor, 2) if low is not None else None,
                round(high * factor, 2) if high is not None else None,
            )
        )
    silver.set_usd(updates)
    return stats
