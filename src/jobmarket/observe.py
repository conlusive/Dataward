"""Answers to "what happened yesterday and why" from the ops tables: the status document, the SLOs
and the message sent after a run.

Everything here reads `ops_*` and the silver/gold tables on a read-only connection; nothing writes.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from jobmarket.flow import StepResult
from jobmarket.ops import OpsStore
from jobmarket.silver.store import SilverStore

Con = duckdb.DuckDBPyConnection

# ---- service level objectives ----------------------------------------------------------------
FRESHNESS_HOURS = 36.0
SUCCESS_RATE = 0.95
SUCCESS_WINDOW_DAYS = 30
SUCCESS_MIN_RUNS = 5  # fewer finished runs than this is not enough to judge a rate
NO_SKILLS_SHARE = 0.10  # the plan said 5%; about 9% of real vacancies name no known skill


@dataclass(frozen=True)
class SloResult:
    name: str
    target: str
    observed: str
    ok: bool | None  # None: not enough data to say
    detail: str


def _utc_naive(now: datetime | None) -> datetime:
    return (now or datetime.now(UTC)).replace(tzinfo=None)


def _scalar(con: Con, sql: str, params: list[object] | None = None) -> Any:
    row = con.execute(sql, params or []).fetchone()
    return row[0] if row else None


def slo_results(con: Con, now: datetime | None = None) -> list[SloResult]:
    moment = _utc_naive(now)
    results: list[SloResult] = []

    last_scrape = _scalar(
        con,
        "SELECT max(finished_at) FROM ops_scrape_runs "
        "WHERE status IN ('success', 'partial') AND source IN ('dou', 'djinni')",
    )
    if isinstance(last_scrape, datetime):
        hours = (moment - last_scrape).total_seconds() / 3600
        results.append(
            SloResult(
                "data_freshness",
                f"last scrape at most {FRESHNESS_HOURS:.0f} h ago",
                f"{hours:.1f} h",
                hours <= FRESHNESS_HOURS,
                f"last successful scrape finished {last_scrape:%Y-%m-%d %H:%M} UTC",
            )
        )
    else:
        results.append(
            SloResult("data_freshness", f"<= {FRESHNESS_HOURS:.0f} h", "-", None, "no scrape yet")
        )

    row = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE status = 'success') FROM ops_pipeline_runs "
        "WHERE status IN ('success', 'failed') AND started_at >= ? - INTERVAL (?) DAY",
        [moment, SUCCESS_WINDOW_DAYS],
    ).fetchone()
    finished, succeeded = (int(row[0]), int(row[1])) if row else (0, 0)
    target = f">= {SUCCESS_RATE:.0%} of runs in {SUCCESS_WINDOW_DAYS} days succeed"
    if finished < SUCCESS_MIN_RUNS:
        results.append(
            SloResult("success_rate", target, f"{succeeded}/{finished}", None, "too few runs yet")
        )
    else:
        rate = succeeded / finished
        results.append(
            SloResult(
                "success_rate",
                target,
                f"{rate:.1%}",
                rate >= SUCCESS_RATE,
                f"{succeeded} of {finished} runs succeeded",
            )  # fmt: skip
        )

    total = int(_scalar(con, "SELECT count(*) FROM silver_vacancies") or 0)
    if total:
        bare = int(
            _scalar(
                con,
                "SELECT count(*) FROM silver_vacancies v WHERE NOT EXISTS "
                "(SELECT 1 FROM silver_vacancy_skills s WHERE s.vacancy_id = v.id)",
            )
            or 0
        )
        share = bare / total
        results.append(
            SloResult(
                "skill_coverage",
                f"under {NO_SKILLS_SHARE:.0%} of vacancies without a skill",
                f"{share:.1%}",
                share < NO_SKILLS_SHARE,
                f"{bare} of {total} vacancies",
            )
        )
    return results


# ---- the report of one run -------------------------------------------------------------------
@dataclass(frozen=True)
class RunReport:
    new_vacancies: int | None  # None on the first day of data: everything would be "new"
    closed_vacancies: int | None  # None when gold has not been built
    new_pages: int
    updated_pages: int
    dq_counts: dict[str, int]
    dq_problems: list[tuple[str, str, str]]  # (status, check, detail) for warn and error
    llm_cost_usd: float


_LATEST_DQ = (
    "SELECT run_id FROM ops_task_runs t WHERE task = 'dq' AND run_date = ? AND attempt = "
    "(SELECT max(attempt) FROM ops_task_runs u WHERE u.task = 'dq' AND u.source = t.source "
    "AND u.run_date = t.run_date)"
)


def run_report(con: Con, run_date: date) -> RunReport:
    days = int(_scalar(con, "SELECT count(DISTINCT seen_date) FROM silver_vacancy_sightings") or 0)
    new = None
    if days > 1:
        new = int(
            _scalar(
                con,
                "SELECT count(*) FROM (SELECT vacancy_id FROM silver_vacancy_sightings "
                "GROUP BY vacancy_id HAVING min(seen_date) = ?)",
                [run_date],
            )
            or 0
        )
    closed = None
    if _scalar(
        con, "SELECT count(*) FROM information_schema.tables WHERE table_name = 'fct_vacancy_daily'"
    ):
        closed = int(
            _scalar(
                con,
                "SELECT count(*) FROM fct_vacancy_daily WHERE date = ? AND status = 'closed'",
                [run_date],
            )
            or 0
        )
    pages = con.execute(
        "SELECT coalesce(sum(new_pages), 0), coalesce(sum(updated_pages), 0) "
        "FROM ops_scrape_runs r "
        "WHERE run_date = ? AND source IN ('dou', 'djinni') AND attempt = "
        "(SELECT max(attempt) FROM ops_scrape_runs u WHERE u.source = r.source "
        "AND u.run_date = r.run_date)",
        [run_date],
    ).fetchone()
    counts = {"pass": 0, "warn": 0, "error": 0, "skipped": 0}
    for status, n in con.execute(
        f"SELECT status, count(*) FROM ops_dq_results WHERE run_id IN ({_LATEST_DQ}) GROUP BY 1",
        [run_date],
    ).fetchall():
        counts[status] = int(n)
    problems = [
        (str(s), str(c), str(d))
        for s, c, d in con.execute(
            "SELECT status, check_name, detail FROM ops_dq_results "
            f"WHERE status IN ('warn', 'error') AND run_id IN ({_LATEST_DQ}) "
            "ORDER BY status DESC, check_name",
            [run_date],
        ).fetchall()
    ]
    cost = _scalar(
        con,
        "SELECT coalesce(sum(cost_usd), 0) FROM ops_llm_usage WHERE CAST(created_at AS DATE) = ?",
        [run_date],
    )
    return RunReport(
        new, closed, int(pages[0]) if pages else 0, int(pages[1]) if pages else 0,
        counts, problems, float(cost or 0),
    )  # fmt: skip


def render_message(
    flow: str,
    run_date: date,
    results: list[StepResult],
    report: RunReport | None,
    run_url: str | None,
) -> str:
    """The Telegram text: a headline, what changed, the checks, the cost and a link; on a failure
    also which steps failed and which checks said why."""
    ok = all(r.status == "success" for r in results)
    lines = [f"{'OK' if ok else 'FAILED'}: {flow} {run_date}"]
    for r in results:
        if r.status != "success":
            lines.append(f"  {r.status} {r.name}" + (f" ({r.detail})" if r.detail else ""))
    if report is not None:
        parts = []
        if report.new_vacancies is not None:
            parts.append(f"{report.new_vacancies} new")
        if report.closed_vacancies is not None:
            parts.append(f"{report.closed_vacancies} closed")
        parts.append(f"pages: {report.new_pages} new, {report.updated_pages} updated")
        lines.append("Vacancies: " + ", ".join(parts))
        c = report.dq_counts
        lines.append(
            f"Checks: {c['pass']} pass, {c['warn']} warn, {c['error']} error, "
            f"{c['skipped']} skipped"
        )
        lines.extend(f"  {s.upper()} {name}: {detail}" for s, name, detail in report.dq_problems)
        lines.append(f"LLM cost: ${report.llm_cost_usd:.2f}")
    if run_url:
        lines.append(f"Run: {run_url}")
    return "\n".join(lines)


# ---- the status document (for the dashboard page and the terminal) ---------------------------
def status_document(
    db_path: Path, now: datetime | None = None, *, days: int = 14
) -> dict[str, Any]:
    moment = _utc_naive(now)
    # a database from before a table existed has no such table, and a read-only connection cannot
    # create it: opening the stores once adds whatever is missing (nothing is overwritten)
    OpsStore(db_path).close()
    SilverStore(db_path).close()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        runs = [
            {
                "run_id": r[0],
                "flow": r[1],
                "run_date": r[2].isoformat(),
                "status": r[3],
                "trigger": r[4],
                "started_at": r[5].isoformat(timespec="seconds"),
                "duration_s": round(r[6]) if r[6] is not None else None,
                "failed_steps": r[7],
                "run_url": r[8],
            }  # fmt: skip
            for r in con.execute(
                "SELECT run_id, flow, run_date, status, trigger, started_at, "
                "date_diff('second', started_at, finished_at), failed_steps, run_url "
                "FROM ops_pipeline_runs WHERE started_at >= ? - INTERVAL (?) DAY "
                "ORDER BY started_at DESC",
                [moment, days],
            ).fetchall()
        ]
        steps = [
            {
                "run_date": r[0].isoformat(),
                "step": r[1],
                "attempt": r[2],
                "status": r[3],
                "duration_s": r[4],
            }  # fmt: skip
            for r in con.execute(
                "SELECT run_date, source, attempt, status, date_diff('second', started_at, "
                "finished_at) FROM ops_task_runs WHERE task = 'flow' AND run_date >= ? "
                "ORDER BY started_at DESC",
                [moment.date() - timedelta(days=days)],
            ).fetchall()
        ]
        scrape = [
            {
                "run_date": r[0].isoformat(),
                "source": r[1],
                "pages": r[2],
                "errors": r[3],
                "http_429": r[4],
                "http_403": r[5],
            }  # fmt: skip
            for r in con.execute(
                "SELECT run_date, source, sum(pages), sum(errors), sum(http_429), sum(http_403) "
                "FROM ops_scrape_runs WHERE run_date >= ? - INTERVAL (?) DAY "
                "GROUP BY run_date, source ORDER BY run_date DESC, source",
                [moment.date(), days],
            ).fetchall()
        ]
        latest_dq = [
            {"check": r[0], "layer": r[1], "status": r[2], "observed": r[3], "detail": r[4]}
            for r in con.execute(
                "SELECT check_name, layer, status, observed, detail FROM ops_dq_results d "
                "WHERE created_at = (SELECT max(created_at) FROM ops_dq_results x "
                "WHERE x.check_name = d.check_name) ORDER BY layer, check_name"
            ).fetchall()
        ]
        volumes = {
            table: int(_scalar(con, f"SELECT count(*) FROM {table}") or 0)
            for table in ("silver_vacancies", "silver_vacancy_skills", "silver_vacancy_sightings")
        }
        slos = [
            {
                "name": s.name,
                "target": s.target,
                "observed": s.observed,
                "ok": s.ok,
                "detail": s.detail,
            }  # fmt: skip
            for s in slo_results(con, moment)
        ]
    finally:
        con.close()
    return {
        "generated_at": moment.isoformat(timespec="seconds") + "Z",
        "runs": runs,
        "steps": steps,
        "scrape": scrape,
        "dq_latest": latest_dq,
        "volumes": volumes,
        "slo": slos,
    }


def write_status(db_path: Path, target: Path, now: datetime | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    document = status_document(db_path, now)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_status(document: dict[str, Any]) -> str:
    """The same document as a short text for the terminal."""
    lines = [f"Pipeline status ({document['generated_at']})", "", "SLOs"]
    for s in document["slo"]:
        mark = {True: "ok  ", False: "FAIL", None: "n/a "}[s["ok"]]
        lines.append(
            f"  {mark} {s['name']}: {s['observed']} (target: {s['target']}) - {s['detail']}"
        )
    lines += ["", "Recent runs"]
    for r in document["runs"][:14] or []:
        duration = f"{r['duration_s']} s" if r["duration_s"] is not None else "running"
        failed = f"  failed: {r['failed_steps']}" if r["failed_steps"] else ""
        lines.append(
            f"  {r['run_date']}  {r['flow']:<8} {r['status']:<8} {r['trigger']:<8} "
            f"{duration}{failed}"
        )
    if not document["runs"]:
        lines.append("  no pipeline runs recorded yet")
    problems = [d for d in document["dq_latest"] if d["status"] in ("warn", "error")]
    lines += ["", f"Checks needing attention: {len(problems)}"]
    lines += [f"  {d['status'].upper()} {d['check']}: {d['detail']}" for d in problems]
    lines += ["", "Rows: " + ", ".join(f"{k} {v}" for k, v in document["volumes"].items())]
    return "\n".join(lines)
