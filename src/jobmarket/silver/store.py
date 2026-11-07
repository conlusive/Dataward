"""silver_vacancies in DuckDB. Parser-owned columns are upserted; later steps own the rest."""

from datetime import date, datetime
from pathlib import Path

import duckdb

from jobmarket.silver.dedup import DedupInput, VacancyGroup
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

_SIGHTINGS_DDL = """
CREATE TABLE IF NOT EXISTS silver_vacancy_sightings (
    vacancy_id VARCHAR NOT NULL,
    seen_date DATE NOT NULL,  -- a day the vacancy was on a listing page
    PRIMARY KEY (vacancy_id, seen_date)
)
"""

_LLM_DDL = (
    """
    CREATE TABLE IF NOT EXISTS llm_cache (
        cache_key VARCHAR PRIMARY KEY,  -- title + description hash, prompt version/text, model
        content_hash VARCHAR NOT NULL,
        model VARCHAR NOT NULL,
        prompt_version VARCHAR NOT NULL,
        raw_json VARCHAR NOT NULL,  -- the model's answer exactly as returned
        prompt_tokens INTEGER NOT NULL,
        completion_tokens INTEGER NOT NULL,
        cost_usd DOUBLE NOT NULL,
        created_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS silver_llm_terms (
        vacancy_id VARCHAR NOT NULL,
        term VARCHAR NOT NULL,  -- the model's skill name, cleaned (lower-case)
        importance VARCHAR NOT NULL,
        model VARCHAR NOT NULL,
        prompt_version VARCHAR NOT NULL,
        PRIMARY KEY (vacancy_id, term)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS silver_unknown_skills (
        term VARCHAR PRIMARY KEY,
        vacancies INTEGER NOT NULL,
        first_seen DATE NOT NULL,
        last_seen DATE NOT NULL,
        suggested_canonical VARCHAR,
        status VARCHAR NOT NULL  -- new | accepted | rejected
    )
    """,
)

_GROUPS_DDL = """
CREATE TABLE IF NOT EXISTS silver_vacancy_groups (
    dedup_group_id VARCHAR PRIMARY KEY,  -- id of the oldest member
    size INTEGER NOT NULL,
    sources VARCHAR[] NOT NULL,
    match_kind VARCHAR NOT NULL,  -- single | exact | fuzzy
    text_id VARCHAR NOT NULL,  -- member whose title and description represent the group
    salary_id VARCHAR,  -- member whose salary represents the group
    _run_id VARCHAR NOT NULL,
    _loaded_at TIMESTAMP NOT NULL
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
        self._con.execute(_GROUPS_DDL)
        for statement in _LLM_DDL:
            self._con.execute(statement)
        self._con.execute(_SIGHTINGS_DDL)

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

    def dedup_inputs(self) -> list[DedupInput]:
        rows = self._con.execute(
            "SELECT id, source, title, company, description_text, content_hash, published_at, "
            "_fetched_at, (salary_min IS NOT NULL OR salary_max IS NOT NULL) "
            "FROM silver_vacancies ORDER BY id"
        ).fetchall()
        return [DedupInput(*row) for row in rows]

    def replace_groups(
        self, groups: list[VacancyGroup], *, run_id: str, loaded_at: datetime
    ) -> None:
        """Store the groups and point every vacancy at its group, atomically."""
        self._con.execute("BEGIN TRANSACTION")
        try:
            self._con.execute("DELETE FROM silver_vacancy_groups")
            if groups:
                self._con.execute(
                    "INSERT INTO silver_vacancy_groups SELECT g.id, g.size, g.sources, g.kind, "
                    "g.text_id, g.salary_id, ?, ? FROM (SELECT unnest(?::VARCHAR[]) AS id, "
                    "unnest(?::INTEGER[]) AS size, unnest(?::VARCHAR[][]) AS sources, "
                    "unnest(?::VARCHAR[]) AS kind, unnest(?::VARCHAR[]) AS text_id, "
                    "unnest(?::VARCHAR[]) AS salary_id) g",
                    [
                        run_id,
                        loaded_at,
                        [g.group_id for g in groups],
                        [len(g.members) for g in groups],
                        [list(g.sources) for g in groups],
                        [g.match_kind for g in groups],
                        [g.text_id for g in groups],
                        [g.salary_id for g in groups],
                    ],
                )
                members = [(m, g.group_id) for g in groups for m in g.members]
                self._con.execute(
                    "UPDATE silver_vacancies SET dedup_group_id = m.group_id FROM "
                    "(SELECT unnest(?::VARCHAR[]) AS id, unnest(?::VARCHAR[]) AS group_id) m "
                    "WHERE silver_vacancies.id = m.id",
                    [[m for m, _ in members], [g for _, g in members]],
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise

    def add_sightings(self, vacancy_ids: list[str], seen_date: date) -> None:
        """Record that these vacancies were listed on ``seen_date`` (repeating it is harmless)."""
        if not vacancy_ids:
            return
        self._con.execute(
            "INSERT INTO silver_vacancy_sightings SELECT unnest(?::VARCHAR[]), ? "
            "ON CONFLICT DO NOTHING",
            [vacancy_ids, seen_date],
        )

    # ---- LLM extraction (method B)
    def llm_inputs(self, source: str | None = None) -> list[tuple[str, str, str, str]]:
        """(id, title, description, content_hash) of the vacancies to extract skills from."""
        where, params = ("WHERE source = ?", [source]) if source else ("", [])
        rows = self._con.execute(
            "SELECT id, title, description_text, content_hash FROM silver_vacancies "
            f"{where} ORDER BY id",
            params,
        ).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]

    def cache_get_many(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        rows = self._con.execute(
            "SELECT cache_key, raw_json FROM llm_cache WHERE cache_key IN "
            "(SELECT unnest(?::VARCHAR[]))",
            [keys],
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def cache_put(
        self,
        key: str,
        *,
        content_hash: str,
        model: str,
        prompt_version: str,
        raw_json: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        created_at: datetime,
    ) -> None:
        self._con.execute(
            "INSERT INTO llm_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            [
                key,
                content_hash,
                model,
                prompt_version,
                raw_json,
                prompt_tokens,
                completion_tokens,
                cost_usd,
                created_at,
            ],
        )

    def replace_llm_results(
        self,
        vacancy_ids: list[str],
        terms: list[tuple[str, str, str, str, str]],
        skills: list[tuple[str, str, str, float, str, str]],
        *,
        run_id: str,
        loaded_at: datetime,
    ) -> None:
        """Replace the LLM terms and skills of exactly these vacancies, atomically.

        terms: (vacancy_id, term, importance, model, prompt_version)
        skills: (vacancy_id, skill_id, importance, confidence, model, prompt_version)
        """
        if not vacancy_ids:
            return
        self._con.execute("BEGIN TRANSACTION")
        try:
            self._con.execute(
                "DELETE FROM silver_llm_terms WHERE vacancy_id IN (SELECT unnest(?::VARCHAR[]))",
                [vacancy_ids],
            )
            self._con.execute(
                "DELETE FROM silver_vacancy_skills WHERE method = 'llm' AND vacancy_id IN "
                "(SELECT unnest(?::VARCHAR[]))",
                [vacancy_ids],
            )
            if terms:
                columns = [list(c) for c in zip(*terms, strict=True)]
                self._con.execute(
                    "INSERT INTO silver_llm_terms SELECT unnest(?::VARCHAR[]), "
                    "unnest(?::VARCHAR[]), unnest(?::VARCHAR[]), unnest(?::VARCHAR[]), "
                    "unnest(?::VARCHAR[])",
                    columns,
                )
            if skills:
                columns = [list(c) for c in zip(*skills, strict=True)]
                self._con.execute(
                    "INSERT INTO silver_vacancy_skills SELECT r.vacancy_id, r.skill_id, "
                    "r.importance, 'llm', r.confidence, r.model, r.prompt_version, ?, ? FROM ("
                    "SELECT unnest(?::VARCHAR[]) AS vacancy_id, unnest(?::VARCHAR[]) AS skill_id, "
                    "unnest(?::VARCHAR[]) AS importance, unnest(?::DOUBLE[]) AS confidence, "
                    "unnest(?::VARCHAR[]) AS model, unnest(?::VARCHAR[]) AS prompt_version) r",
                    [run_id, loaded_at, *columns],
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise

    def llm_terms(self) -> list[tuple[str, str, str, str, str]]:
        rows = self._con.execute(
            "SELECT vacancy_id, term, importance, model, prompt_version FROM silver_llm_terms "
            "ORDER BY vacancy_id, term"
        ).fetchall()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]

    def term_dates(self) -> dict[str, tuple[int, date, date]]:
        """term -> (vacancies, first seen, last seen), from when the vacancies were fetched."""
        rows = self._con.execute(
            "SELECT t.term, count(DISTINCT t.vacancy_id), min(CAST(v._fetched_at AS DATE)), "
            "max(CAST(v._fetched_at AS DATE)) FROM silver_llm_terms t "
            "JOIN silver_vacancies v ON v.id = t.vacancy_id GROUP BY t.term"
        ).fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    def unknown_statuses(self) -> dict[str, str]:
        rows = self._con.execute("SELECT term, status FROM silver_unknown_skills").fetchall()
        return {r[0]: r[1] for r in rows}

    def replace_unknown_skills(
        self, rows: list[tuple[str, int, date, date, str | None, str]]
    ) -> None:
        """rows: (term, vacancies, first_seen, last_seen, suggested_canonical, status)."""
        self._con.execute("BEGIN TRANSACTION")
        try:
            self._con.execute("DELETE FROM silver_unknown_skills")
            if rows:
                columns = [list(c) for c in zip(*rows, strict=True)]
                self._con.execute(
                    "INSERT INTO silver_unknown_skills SELECT unnest(?::VARCHAR[]), "
                    "unnest(?::INTEGER[]), unnest(?::DATE[]), unnest(?::DATE[]), "
                    "unnest(?::VARCHAR[]), unnest(?::VARCHAR[])",
                    columns,
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise
