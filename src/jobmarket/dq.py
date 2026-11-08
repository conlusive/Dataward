"""Data-quality checks. A `warn` is reported and the run goes on; an `error` stops the run.

Every check measures one number (`observed`) and compares it with two thresholds. The thresholds are
the constants below, in one place, so tuning a check never means reading its query. All results,
also the passing ones, are written to `ops_dq_results` so that a slow drift is visible over time.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median

import duckdb

from jobmarket.contracts import SILVER_CONTRACT, load_contracts, violations

# ---- thresholds (a value at or beyond the limit trips the level) ------------------------------
# latest day's listings / median of the days before; trips when it falls to the limit or below
LISTING_RATIO_WARN, LISTING_RATIO_ERROR = 0.6, 0.3
LISTING_HISTORY_DAYS, LISTING_MIN_HISTORY = 14, 3
FRESH_HOURS_WARN, FRESH_HOURS_ERROR = 30.0, 36.0
NO_SKILLS_WARN, NO_SKILLS_ERROR = 0.15, 0.30
SALARY_USD_MIN, SALARY_USD_MAX = 100.0, 30_000.0
SALARY_RANGE_WARN, SALARY_RANGE_ERROR = 0.02, 0.10
# fall of the parsed share of salary strings, in absolute terms (0.10 = ten percentage points)
SALARY_DROP_WARN, SALARY_DROP_ERROR = 0.10, 0.20
SALARY_RECENT_DAYS, SALARY_MIN_SAMPLE = 7, 20
SIGHTING_GAP_WARN, SIGHTING_GAP_ERROR = 0.10, 0.30
PARSE_FAILED_WARN, PARSE_FAILED_ERROR = 0.01, 0.05


@dataclass(frozen=True)
class CheckResult:
    name: str
    layer: str
    observed: float | None
    warn: float | None
    error: float | None
    status: str  # pass | warn | error | skipped
    detail: str


Con = duckdb.DuckDBPyConnection


def _judge(
    name: str,
    layer: str,
    observed: float,
    *,
    warn: float,
    error: float,
    detail: str,
    higher_is_bad: bool = True,
) -> CheckResult:
    def tripped(limit: float) -> bool:
        return observed >= limit if higher_is_bad else observed <= limit

    status = "error" if tripped(error) else ("warn" if tripped(warn) else "pass")
    return CheckResult(name, layer, observed, warn, error, status, detail)


def _skipped(name: str, layer: str, why: str) -> CheckResult:
    return CheckResult(name, layer, None, None, None, "skipped", why)


def _count(con: Con, sql: str, params: list[object] | None = None) -> int:
    row = con.execute(sql, params or []).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


# ---- checks -----------------------------------------------------------------------------------
def check_schema_contract(con: Con, now: datetime) -> CheckResult:
    problems = violations(con, load_contracts(SILVER_CONTRACT))
    return _judge(
        "schema_contract",
        "silver",
        float(len(problems)),
        warn=1,
        error=1,
        detail="; ".join(problems[:5]) or "silver tables match contracts/silver.yml",
    )


def check_listing_volume(con: Con, now: datetime) -> CheckResult:
    rows = con.execute(
        "SELECT seen_date, count(DISTINCT vacancy_id) FROM silver_vacancy_sightings "
        "GROUP BY seen_date ORDER BY seen_date DESC LIMIT ?",
        [LISTING_HISTORY_DAYS + 1],
    ).fetchall()
    if len(rows) - 1 < LISTING_MIN_HISTORY:
        return _skipped(
            "listing_volume", "silver", f"fewer than {LISTING_MIN_HISTORY} earlier days"
        )
    latest_day, latest = rows[0]
    typical = median(r[1] for r in rows[1:])
    return _judge(
        "listing_volume",
        "silver",
        latest / typical,
        warn=LISTING_RATIO_WARN,
        error=LISTING_RATIO_ERROR,
        higher_is_bad=False,
        detail=f"{latest} vacancies listed on {latest_day}; the days before: median {typical:.0f}",
    )


def check_freshness(con: Con, now: datetime) -> CheckResult:
    row = con.execute("SELECT max(_fetched_at) FROM silver_vacancies").fetchone()
    newest = row[0] if row else None
    if not isinstance(newest, datetime):
        detail = "silver has no vacancies"
        return CheckResult(
            "fresh_data", "silver", None, FRESH_HOURS_WARN, FRESH_HOURS_ERROR, "error", detail
        )
    hours = (now - newest).total_seconds() / 3600
    return _judge(
        "fresh_data",
        "silver",
        hours,
        warn=FRESH_HOURS_WARN,
        error=FRESH_HOURS_ERROR,
        detail=f"newest page fetched {hours:.1f} h ago ({newest:%Y-%m-%d %H:%M} UTC)",
    )


def check_vacancies_without_skills(con: Con, now: datetime) -> CheckResult:
    total = _count(con, "SELECT count(*) FROM silver_vacancies")
    if total == 0:
        return _skipped("vacancies_without_skills", "silver", "no vacancies")
    bare = _count(
        con,
        "SELECT count(*) FROM silver_vacancies v WHERE NOT EXISTS "
        "(SELECT 1 FROM silver_vacancy_skills s WHERE s.vacancy_id = v.id)",
    )
    return _judge(
        "vacancies_without_skills",
        "silver",
        bare / total,
        warn=NO_SKILLS_WARN,
        error=NO_SKILLS_ERROR,
        detail=f"{bare} of {total} vacancies have no skill",
    )


def check_empty_key_fields(con: Con, now: datetime) -> CheckResult:
    empty = _count(
        con,
        "SELECT count(*) FROM silver_vacancies WHERE trim(title) = '' OR trim(company) = '' "
        "OR trim(url) = '' OR trim(id) = ''",
    )
    return _judge(
        "empty_key_fields",
        "silver",
        float(empty),
        warn=1,
        error=1,
        detail=f"{empty} vacancies with an empty id, url, title or company",
    )


def check_salary_range(con: Con, now: datetime) -> CheckResult:
    salaried = _count(
        con,
        "SELECT count(*) FROM silver_vacancies "
        "WHERE salary_usd_min IS NOT NULL OR salary_usd_max IS NOT NULL",
    )
    if not salaried:
        return _skipped("salary_in_range", "silver", "no vacancy with a USD salary")
    outside = _count(
        con,
        "SELECT count(*) FROM silver_vacancies WHERE salary_usd_min < ? OR salary_usd_max > ? "
        "OR salary_usd_max < ? OR salary_usd_min > ?",
        [SALARY_USD_MIN, SALARY_USD_MAX, SALARY_USD_MIN, SALARY_USD_MAX],
    )
    return _judge(
        "salary_in_range",
        "silver",
        outside / salaried,
        warn=SALARY_RANGE_WARN,
        error=SALARY_RANGE_ERROR,
        detail=(
            f"{outside} of {salaried} salaries outside "
            f"{SALARY_USD_MIN:.0f}-{SALARY_USD_MAX:.0f} USD"
        ),
    )


def check_salary_parse_rate(con: Con, now: datetime) -> CheckResult:
    row = con.execute("SELECT max(CAST(_fetched_at AS DATE)) FROM silver_vacancies").fetchone()
    newest = row[0] if row else None
    if not isinstance(newest, date):
        return _skipped("salary_parse_rate", "silver", "no vacancies")
    rows = con.execute(
        "SELECT CAST(_fetched_at AS DATE) > ? - INTERVAL (?) DAY AS recent, count(*), "
        "count(*) FILTER (WHERE salary_min IS NOT NULL OR salary_max IS NOT NULL) "
        "FROM silver_vacancies WHERE salary_raw IS NOT NULL AND trim(salary_raw) <> '' "
        "GROUP BY 1",
        [newest, SALARY_RECENT_DAYS],
    ).fetchall()
    by_window = {bool(recent): (total, parsed) for recent, total, parsed in rows}
    recent_total, recent_parsed = by_window.get(True, (0, 0))
    earlier_total, earlier_parsed = by_window.get(False, (0, 0))
    if recent_total < SALARY_MIN_SAMPLE or earlier_total < SALARY_MIN_SAMPLE:
        return _skipped("salary_parse_rate", "silver", "too few salary strings to compare")
    recent_share, earlier_share = recent_parsed / recent_total, earlier_parsed / earlier_total
    return _judge(
        "salary_parse_rate",
        "silver",
        earlier_share - recent_share,
        warn=SALARY_DROP_WARN,
        error=SALARY_DROP_ERROR,
        detail=(
            f"parsed {recent_share:.0%} of recent salary strings, "
            f"{earlier_share:.0%} of earlier ones"
        ),
    )


def check_references(con: Con, now: datetime) -> CheckResult:
    orphans = {
        "skill rows with an unknown skill id": "SELECT count(*) FROM silver_vacancy_skills s "
        "WHERE NOT EXISTS (SELECT 1 FROM silver_skills k WHERE k.skill_id = s.skill_id)",
        "vacancies in a missing group": "SELECT count(*) FROM silver_vacancies v "
        "WHERE v.dedup_group_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM silver_vacancy_groups g WHERE g.dedup_group_id = v.dedup_group_id)",
        "groups whose text vacancy is gone": "SELECT count(*) FROM silver_vacancy_groups g "
        "WHERE NOT EXISTS (SELECT 1 FROM silver_vacancies v WHERE v.id = g.text_id)",
    }
    counts = {label: _count(con, sql) for label, sql in orphans.items()}
    return _judge(
        "references",
        "silver",
        float(sum(counts.values())),
        warn=1,
        error=1,
        detail="; ".join(f"{n} {label}" for label, n in counts.items() if n) or "no orphan rows",
    )


def check_sightings_have_pages(con: Con, now: datetime) -> CheckResult:
    latest = "(SELECT max(seen_date) FROM silver_vacancy_sightings)"
    listed = _count(
        con,
        "SELECT count(DISTINCT vacancy_id) FROM silver_vacancy_sightings "
        f"WHERE seen_date = {latest}",
    )
    if not listed:
        return _skipped("sightings_have_pages", "silver", "no sightings")
    missing = _count(
        con,
        "SELECT count(DISTINCT s.vacancy_id) FROM silver_vacancy_sightings s "
        "WHERE s.seen_date = " + latest + " AND NOT EXISTS "
        "(SELECT 1 FROM silver_vacancies v WHERE v.id = s.vacancy_id)",
    )
    return _judge(
        "sightings_have_pages",
        "silver",
        missing / listed,
        warn=SIGHTING_GAP_WARN,
        error=SIGHTING_GAP_ERROR,
        detail=f"{missing} of {listed} vacancies listed on the latest day have no parsed page",
    )


def check_parse_failures(con: Con, now: datetime) -> CheckResult:
    row = con.execute(
        # vacancy pages only: the survey loader also logs `parse` tasks, with rows, not pages
        "SELECT sum(rows_in), sum(rows_failed) FROM ops_task_runs t WHERE task = 'parse' "
        "AND source IN ('dou', 'djinni') AND status IN ('success', 'partial') AND run_date >= "
        "(SELECT max(run_date) FROM ops_task_runs WHERE task = 'parse' "
        "AND source IN ('dou', 'djinni')) - INTERVAL 3 DAY "
        "AND attempt = (SELECT max(attempt) FROM ops_task_runs u WHERE u.task = t.task "
        "AND u.source = t.source AND u.run_date = t.run_date)"
    ).fetchone()
    pages, failed = (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)
    if not pages:
        return _skipped("parse_failures", "silver", "no finished parse runs")
    return _judge(
        "parse_failures",
        "silver",
        failed / pages,
        warn=PARSE_FAILED_WARN,
        error=PARSE_FAILED_ERROR,
        detail=f"{failed} of {pages} pages did not match the parser in the last parse runs",
    )


def check_gold_built(con: Con, now: datetime) -> CheckResult:
    exists = _count(
        con,
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_name = 'fct_skill_demand_monthly'",
    )
    if not exists:
        detail = "gold marts are missing: run `make dbt-build`"
        return CheckResult("gold_built", "gold", 0.0, None, 1.0, "error", detail)
    if not _count(con, "SELECT count(*) FROM silver_vacancy_skills"):
        return _skipped("gold_built", "gold", "no skills in silver")
    rows = _count(con, "SELECT count(*) FROM fct_skill_demand_monthly")
    return _judge(
        "gold_built",
        "gold",
        float(rows),
        warn=0,
        error=0,
        higher_is_bad=False,
        detail=f"fct_skill_demand_monthly has {rows} rows",
    )


CHECKS: tuple[Callable[[Con, datetime], CheckResult], ...] = (
    check_schema_contract,
    check_freshness,
    check_listing_volume,
    check_empty_key_fields,
    check_references,
    check_vacancies_without_skills,
    check_salary_range,
    check_salary_parse_rate,
    check_sightings_have_pages,
    check_parse_failures,
    check_gold_built,
)


def run_checks(db_path: Path, *, now: datetime | None = None) -> list[CheckResult]:
    """Run every check on a read-only connection; a check that crashes is an `error`, not a skip."""
    moment = (now or datetime.now(UTC)).replace(tzinfo=None)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        results: list[CheckResult] = []
        for check in CHECKS:
            try:
                results.append(check(con, moment))
            except duckdb.Error as exc:
                name = check.__name__.removeprefix("check_")
                results.append(CheckResult(name, "unknown", None, None, None, "error", repr(exc)))
        return results
    finally:
        con.close()
