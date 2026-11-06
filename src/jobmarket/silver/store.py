"""silver_vacancies in DuckDB. Parser-owned columns are upserted; later steps own the rest."""

from datetime import datetime
from pathlib import Path

import duckdb

from jobmarket.silver.model import ParsedVacancy

_DDL = """
CREATE TABLE IF NOT EXISTS silver_vacancies (
    id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,
    url VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    company VARCHAR NOT NULL,
    category VARCHAR,
    locations VARCHAR[] NOT NULL,
    remote BOOLEAN,
    experience_years DOUBLE,
    english_level VARCHAR,
    salary_raw VARCHAR,
    salary_min DOUBLE,
    salary_max DOUBLE,
    salary_currency VARCHAR,
    salary_usd_min DOUBLE,
    salary_usd_max DOUBLE,
    published_at DATE,
    description_text VARCHAR NOT NULL,
    content_hash VARCHAR NOT NULL,
    dedup_group_id VARCHAR,
    _run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP NOT NULL,
    _source_file VARCHAR NOT NULL,
    _fetched_at TIMESTAMP NOT NULL
)
"""

# Columns written by the HTML parsers. english_level, salary_min/max/currency, salary_usd_* and
# dedup_group_id are filled by later steps and must survive a re-parse.
_PARSER_COLUMNS = (
    "source",
    "url",
    "title",
    "company",
    "category",
    "locations",
    "remote",
    "experience_years",
    "salary_raw",
    "published_at",
    "description_text",
    "content_hash",
    "_run_id",
    "_loaded_at",
    "_source_file",
    "_fetched_at",
)
_UPSERT = (
    f"INSERT INTO silver_vacancies (id, {', '.join(_PARSER_COLUMNS)}) "
    f"VALUES (?{', ?' * len(_PARSER_COLUMNS)}) "
    "ON CONFLICT (id) DO UPDATE SET "
    + ", ".join(f"{c} = excluded.{c}" for c in _PARSER_COLUMNS)
    # A backfill of an older date must not overwrite a newer version of the same vacancy.
    + " WHERE excluded._fetched_at >= silver_vacancies._fetched_at"
)


class SilverStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(db_path))
        self._con.execute(_DDL)

    def close(self) -> None:
        self._con.close()

    def upsert(
        self,
        vacancy: ParsedVacancy,
        *,
        run_id: str,
        loaded_at: datetime,
        source_file: str,
        fetched_at: datetime,
    ) -> None:
        self._con.execute(
            _UPSERT,
            [
                vacancy.id,
                vacancy.source,
                vacancy.url,
                vacancy.title,
                vacancy.company,
                vacancy.category,
                vacancy.locations,
                vacancy.remote,
                vacancy.experience_years,
                vacancy.salary_raw,
                vacancy.published_at,
                vacancy.description_text,
                vacancy.content_hash,
                run_id,
                loaded_at,
                source_file,
                fetched_at,
            ],
        )
