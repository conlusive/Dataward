"""Bronze survey CSVs -> silver_dou_salaries (every wave, newest bronze copy of each file)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger

from jobmarket.bronze import BronzeRecord, BronzeStore
from jobmarket.silver.dou_salaries import load_schemas, parse_wave, wave_date
from jobmarket.silver.store import SilverStore, SurveyRecord

SOURCE = "dou_salaries"


@dataclass
class SurveyStats:
    files: int = 0
    loaded: int = 0
    failed: int = 0  # file does not match its mapping (renamed column, wrong encoding, ...)
    unmapped: int = 0  # a CSV in bronze that the YAML mapping does not know
    rows_kept: int = 0
    rows_subtotals: int = 0
    rows_no_salary: int = 0
    rows_outliers: int = 0


def _latest_csv_records(bronze: BronzeStore) -> dict[str, BronzeRecord]:
    """File stem -> the most recently stored copy of that CSV."""
    latest: dict[str, BronzeRecord] = {}
    for partition in reversed(bronze.partition_dates(SOURCE)):
        for record in bronze.records(SOURCE, partition):
            url: str = record.meta["url"]
            if record.meta["status"] != 200 or not url.endswith(".csv"):
                continue
            latest.setdefault(url.rsplit("/", 1)[1].removesuffix(".csv"), record)
    return latest


def load_surveys(bronze: BronzeStore, silver: SilverStore, *, run_id: str) -> SurveyStats:
    schemas = load_schemas()
    stats = SurveyStats()
    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    for stem, record in sorted(_latest_csv_records(bronze).items()):
        stats.files += 1
        schema = schemas.get(stem)
        if schema is None:
            stats.unmapped += 1
            logger.warning("{}: no column mapping for {}", run_id, stem)
            continue
        try:
            rows, wave_stats = parse_wave(record.content, schema)
        except (KeyError, UnicodeDecodeError, IndexError) as exc:
            stats.failed += 1
            logger.error("{}: {} does not match its mapping: {!r}", run_id, stem, exc)
            continue
        records: list[SurveyRecord] = [
            (
                r.row_no,
                r.position,
                r.experience_years,
                r.city,
                r.english,
                r.company_size,
                r.company_type,
                r.salary_usd,
                r.weight,
            )
            for r in rows
        ]
        silver.replace_survey_file(
            f"{SOURCE}/{record.meta['file']}",
            stem,
            wave_date(stem),
            records,
            run_id=run_id,
            loaded_at=loaded_at,
        )
        stats.loaded += 1
        stats.rows_kept += wave_stats.kept
        stats.rows_subtotals += wave_stats.subtotals
        stats.rows_no_salary += wave_stats.no_salary
        stats.rows_outliers += wave_stats.outliers
    return stats
