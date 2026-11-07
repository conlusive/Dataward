"""silver_vacancies in DuckDB. Parser-owned columns are upserted; later steps own the rest."""

from datetime import date, datetime
from pathlib import Path

import duckdb

from jobmarket.silver.model import ParsedVacancy

# (row_no, position, experience_years, city, english, company_size, company_type, salary_usd,
# weight): one answer of a DOU survey as stored in silver_dou_salaries.
SurveyRecord = tuple[
    int, str | None, float | None, str | None, str | None, str | None, str | None, float, float
]

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
    experience_years DOUBLE,  -- declared by the page (Djinni JSON-LD)
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
    experience_years_text DOUBLE,  -- required years read from the description
    seniority VARCHAR,  -- from the title: intern / junior / middle / senior / lead
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

_SURVEY_DDL = """
CREATE TABLE IF NOT EXISTS silver_dou_salaries (
    survey_date DATE NOT NULL,  -- first day of the survey month
    wave VARCHAR NOT NULL,  -- e.g. 2024_june
    row_no INTEGER NOT NULL,  -- position of the answer in its file
    position VARCHAR,
    experience_years DOUBLE,
    city VARCHAR,
    english VARCHAR,
    company_size VARCHAR,
    company_type VARCHAR,
    salary_usd DOUBLE NOT NULL,  -- per month, net
    weight DOUBLE NOT NULL,  -- respondents this row stands for (aggregated waves)
    _run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP NOT NULL,
    _source_file VARCHAR NOT NULL,
    PRIMARY KEY (_source_file, row_no)
)
"""

_SKILLS_DDL = (
    """
    CREATE TABLE IF NOT EXISTS silver_skills (
        skill_id VARCHAR PRIMARY KEY,
        canonical VARCHAR NOT NULL,
        category VARCHAR NOT NULL,
        parent_id VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS silver_vacancy_skills (
        vacancy_id VARCHAR NOT NULL,
        skill_id VARCHAR NOT NULL,
        importance VARCHAR NOT NULL,  -- required | nice
        method VARCHAR NOT NULL,  -- dictionary | llm
        confidence DOUBLE NOT NULL,
        model VARCHAR,
        prompt_version VARCHAR,
        _run_id VARCHAR NOT NULL,
        _loaded_at TIMESTAMP NOT NULL,
        PRIMARY KEY (vacancy_id, skill_id, method)
    )
    """,
)

# Columns added after the first release; applied to databases created before them.
_MIGRATIONS = (
    "ALTER TABLE silver_vacancies ADD COLUMN IF NOT EXISTS experience_years_text DOUBLE",
    "ALTER TABLE silver_vacancies ADD COLUMN IF NOT EXISTS seniority VARCHAR",
)

# Columns written by the HTML parsers. english_level, salary_min/max/currency, salary_usd_* and
# dedup_group_id, experience_years_text and seniority are filled by later steps and must survive a
# re-parse.
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
        for migration in _MIGRATIONS:
            self._con.execute(migration)
        self._con.execute(_RATES_DDL)
        self._con.execute(_SURVEY_DDL)
        for statement in _SKILLS_DDL:
            self._con.execute(statement)

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

    def replace_survey_file(
        self,
        source_file: str,
        wave: str,
        survey_date: date,
        rows: list[SurveyRecord],
        *,
        run_id: str,
        loaded_at: datetime,
    ) -> None:
        """Replace everything loaded from one survey file, atomically.

        rows: (row_no, position, experience_years, city, english, company_size, company_type,
        salary_usd, weight).
        """
        self._con.execute("BEGIN TRANSACTION")
        try:
            self._con.execute(
                "DELETE FROM silver_dou_salaries WHERE _source_file = ?", [source_file]
            )
            if rows:
                # One statement per file: unnest() of equally long list parameters is ~100x
                # faster in DuckDB than executemany row by row (14k rows: 0.02 s vs 3.6 s).
                columns = [list(column) for column in zip(*rows, strict=True)]
                self._con.execute(
                    "INSERT INTO silver_dou_salaries "
                    "SELECT ?, ?, r.row_no, r.position, r.experience_years, r.city, r.english, "
                    "r.company_size, r.company_type, r.salary_usd, r.weight, ?, ?, ? FROM ("
                    "SELECT unnest(?::INTEGER[]) AS row_no, unnest(?::VARCHAR[]) AS position, "
                    "unnest(?::DOUBLE[]) AS experience_years, unnest(?::VARCHAR[]) AS city, "
                    "unnest(?::VARCHAR[]) AS english, unnest(?::VARCHAR[]) AS company_size, "
                    "unnest(?::VARCHAR[]) AS company_type, unnest(?::DOUBLE[]) AS salary_usd, "
                    "unnest(?::DOUBLE[]) AS weight) r",
                    [survey_date, wave, run_id, loaded_at, source_file, *columns],
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise

    def text_inputs(self, source: str) -> list[tuple[str, str, str]]:
        rows = self._con.execute(
            "SELECT id, title, description_text FROM silver_vacancies WHERE source = ? ORDER BY id",
            [source],
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def set_text_signals(
        self, rows: list[tuple[str, str | None, float | None, str | None]]
    ) -> None:
        """rows: (id, seniority, experience_years_text, english_level)."""
        if not rows:
            return
        self._con.executemany(
            "UPDATE silver_vacancies SET seniority = ?, experience_years_text = ?, "
            "english_level = ? WHERE id = ?",
            [(seniority, years, english, vid) for vid, seniority, years, english in rows],
        )

    def replace_skills(self, rows: list[tuple[str, str, str, str | None]]) -> None:
        """The taxonomy as loaded from YAML: (skill_id, canonical, category, parent_id)."""
        self._con.execute("BEGIN TRANSACTION")
        try:
            self._con.execute("DELETE FROM silver_skills")
            if rows:
                columns = [list(c) for c in zip(*rows, strict=True)]
                self._con.execute(
                    "INSERT INTO silver_skills SELECT unnest(?::VARCHAR[]), unnest(?::VARCHAR[]), "
                    "unnest(?::VARCHAR[]), unnest(?::VARCHAR[])",
                    columns,
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise

    def replace_vacancy_skills(
        self,
        source: str,
        method: str,
        rows: list[tuple[str, str, str, float]],
        *,
        run_id: str,
        loaded_at: datetime,
    ) -> None:
        """Replace one method's skills for every vacancy of ``source`` atomically.

        rows: (vacancy_id, skill_id, importance, confidence).
        """
        self._con.execute("BEGIN TRANSACTION")
        try:
            self._con.execute(
                "DELETE FROM silver_vacancy_skills WHERE method = ? AND vacancy_id IN "
                "(SELECT id FROM silver_vacancies WHERE source = ?)",
                [method, source],
            )
            if rows:
                columns = [list(c) for c in zip(*rows, strict=True)]
                self._con.execute(
                    "INSERT INTO silver_vacancy_skills "
                    "SELECT r.vacancy_id, r.skill_id, r.importance, ?, r.confidence, NULL, NULL, "
                    "?, ? FROM (SELECT unnest(?::VARCHAR[]) AS vacancy_id, "
                    "unnest(?::VARCHAR[]) AS skill_id, unnest(?::VARCHAR[]) AS importance, "
                    "unnest(?::DOUBLE[]) AS confidence) r",
                    [method, run_id, loaded_at, *columns],
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise
