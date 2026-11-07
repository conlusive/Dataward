"""silver_vacancies in DuckDB. Parser-owned columns are upserted; later steps own the rest."""

from datetime import date, datetime
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

_RATES_DDL = """
CREATE TABLE IF NOT EXISTS silver_nbu_rates (
    rate_date DATE NOT NULL,
    currency VARCHAR NOT NULL,
    rate DOUBLE NOT NULL,  -- UAH per 1 unit of currency
    PRIMARY KEY (rate_date, currency)
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
        self._con.execute(_RATES_DDL)

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

    def salary_inputs(self, source: str) -> list[tuple[str, str, str, str | None]]:
        rows = self._con.execute(
            "SELECT id, title, description_text, salary_raw FROM silver_vacancies "
            "WHERE source = ? ORDER BY id",
            [source],
        ).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]

    def set_salaries(
        self, rows: list[tuple[str, str | None, float | None, float | None, str | None]]
    ) -> None:
        """rows: (id, salary_raw, salary_min, salary_max, salary_currency)."""
        if not rows:
            return
        self._con.executemany(
            "UPDATE silver_vacancies SET salary_raw = ?, salary_min = ?, salary_max = ?, "
            "salary_currency = ? WHERE id = ?",
            [(raw, low, high, cur, vid) for vid, raw, low, high, cur in rows],
        )

    def upsert_rates(self, rows: list[tuple[date, str, float]]) -> None:
        if not rows:  # DuckDB rejects executemany with no parameter sets
            return
        self._con.executemany(
            "INSERT INTO silver_nbu_rates (rate_date, currency, rate) VALUES (?, ?, ?) "
            "ON CONFLICT (rate_date, currency) DO UPDATE SET rate = excluded.rate",
            rows,
        )

    def rates(self, currencies: tuple[str, ...]) -> dict[str, dict[date, float]]:
        found: dict[str, dict[date, float]] = {c: {} for c in currencies}
        placeholders = ", ".join("?" for _ in currencies)
        for rate_date, currency, rate in self._con.execute(
            "SELECT rate_date, currency, rate FROM silver_nbu_rates "
            f"WHERE currency IN ({placeholders})",
            list(currencies),
        ).fetchall():
            found[currency][rate_date] = rate
        return found

    def salary_rows(
        self, source: str | None = None
    ) -> list[tuple[str, str, float | None, float | None, date]]:
        """(id, currency, min, max, rate date) of vacancies with a salary; the rate date is the
        publication date, or the day the page was fetched when the page has none."""
        where = "salary_currency IS NOT NULL" + (" AND source = ?" if source else "")
        rows = self._con.execute(
            "SELECT id, salary_currency, salary_min, salary_max, "
            "coalesce(published_at, CAST(_fetched_at AS DATE)) "
            f"FROM silver_vacancies WHERE {where} ORDER BY id",
            [source] if source else [],
        ).fetchall()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]

    def set_usd(self, rows: list[tuple[str, float | None, float | None]]) -> None:
        """rows: (id, salary_usd_min, salary_usd_max)."""
        if not rows:
            return
        self._con.executemany(
            "UPDATE silver_vacancies SET salary_usd_min = ?, salary_usd_max = ? WHERE id = ?",
            [(low, high, vid) for vid, low, high in rows],
        )

    def clear_usd_without_salary(self, source: str | None = None) -> None:
        """A vacancy that lost its salary must not keep USD amounts computed from the old one."""
        self._con.execute(
            "UPDATE silver_vacancies SET salary_usd_min = NULL, salary_usd_max = NULL "
            "WHERE salary_currency IS NULL "
            "AND (salary_usd_min IS NOT NULL OR salary_usd_max IS NOT NULL)"
            + (" AND source = ?" if source else ""),
            [source] if source else [],
        )
