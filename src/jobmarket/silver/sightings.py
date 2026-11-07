"""Which vacancies were on a listing page on a given day, read from the stored bronze pages."""

import re
from datetime import date

from jobmarket.bronze import BronzeStore
from jobmarket.scrapers.djinni import parse_listing_urls as djinni_listing_urls
from jobmarket.scrapers.dou import parse_listing_urls as dou_listing_urls
from jobmarket.scrapers.dou import parse_xhr
from jobmarket.silver.parse_djinni import vacancy_id as djinni_id
from jobmarket.silver.parse_dou import vacancy_id as dou_id

_DOU_LISTING = (
    "https://jobs.dou.ua/vacancies/"  # category pages and xhr-load; vacancies live elsewhere
)
_DJINNI_LISTING = re.compile(r"^https://djinni\.co/jobs/\?")


def listed_vacancy_ids(bronze: BronzeStore, source: str, run_date: date) -> list[str]:
    """Ids of every vacancy that appears on a stored listing page of ``source`` for ``run_date``.

    Listing pages of a capped crawl (``--max-pages``) are incomplete, so a day built from one
    makes vacancies look absent; only full crawls give trustworthy sightings.
    """
    ids: set[str] = set()
    for record in bronze.records(source, run_date):
        meta = record.meta
        url: str = meta["url"]
        if meta["status"] != 200 or meta.get("redirected", False):
            continue
        urls: list[str]
        if source == "dou" and url.startswith(_DOU_LISTING):
            if meta["file"].endswith(".json"):
                urls = parse_xhr(record.content)[0]
            else:
                urls = dou_listing_urls(record.content.decode("utf-8"))
            to_id = dou_id
        elif source == "djinni" and _DJINNI_LISTING.match(url):
            urls = djinni_listing_urls(record.content.decode("utf-8"))
            to_id = djinni_id
        else:
            continue
        ids.update(i for i in map(to_id, urls) if i)
    return sorted(ids)
