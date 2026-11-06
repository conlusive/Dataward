"""Bronze -> silver_vacancies for one source and run_date."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from loguru import logger

from jobmarket.bronze import BronzeStore
from jobmarket.silver.model import ParsedVacancy, ParseError
from jobmarket.silver.parse_djinni import SOURCE as DJINNI
from jobmarket.silver.parse_djinni import parse_djinni_vacancy
from jobmarket.silver.parse_dou import SOURCE as DOU
from jobmarket.silver.parse_dou import parse_dou_vacancy
from jobmarket.silver.store import SilverStore

Parser = Callable[..., ParsedVacancy]

# source -> (pattern of vacancy-page URLs, parser). Listing pages and API files are not vacancies.
PARSERS: dict[str, tuple[re.Pattern[str], Parser]] = {
    DOU: (re.compile(r"/companies/[^/]+/vacancies/\d+/"), parse_dou_vacancy),
    DJINNI: (re.compile(r"/jobs/\d+-"), parse_djinni_vacancy),
}


@dataclass
class ParseStats:
    pages: int = 0  # vacancy pages found in bronze
    parsed: int = 0
    failed: int = 0  # markup does not match the parser
    unusable: int = 0  # non-200 or redirected: the content is not this vacancy


def _naive_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC).replace(tzinfo=None)


def parse_source(
    source: str, run_date: date, *, bronze: BronzeStore, silver: SilverStore, run_id: str
) -> ParseStats:
    vacancy_url, parse = PARSERS[source]
    stats = ParseStats()
    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    for record in bronze.records(source, run_date):
        meta = record.meta
        if not vacancy_url.search(meta["url"]):
            continue
        stats.pages += 1
        if meta["status"] != 200 or meta.get("redirected", False):
            stats.unusable += 1
            continue
        try:
            vacancy = parse(record.content.decode("utf-8"), meta["url"], fetched_on=run_date)
        except ParseError as exc:
            stats.failed += 1
            logger.warning("{}: {}", run_id, exc)
            continue
        silver.upsert(
            vacancy,
            run_id=run_id,
            loaded_at=loaded_at,
            source_file=f"{source}/dt={run_date.isoformat()}/{meta['file']}",
            fetched_at=_naive_utc(meta["fetched_at"]),
        )
        stats.parsed += 1
    return stats
