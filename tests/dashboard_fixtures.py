"""A small made-up export (parquet + JSON) with answers that are easy to check by hand."""

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

NOV, OCT = date(2026, 11, 1), date(2026, 10, 1)


def tables() -> dict[str, pd.DataFrame]:
    return {
        "dim_skill": pd.DataFrame(
            {
                "skill_id": ["python", "django", "docker", "sql"],
                "canonical": ["Python", "Django", "Docker", "SQL"],
                "category": ["language", "framework", "devops", "database"],
                "parent_id": [None, "python", None, None],
            }
        ),
        "fct_skill_demand_monthly": pd.DataFrame(
            {
                "month": [NOV, NOV, NOV, NOV, OCT],
                "skill_id": ["python", "django", "docker", "sql", "python"],
                "vacancies": [2, 2, 2, 1, 1],
                "vacancies_required": [2, 1, 1, 1, 1],
                "month_vacancies": [3, 3, 3, 3, 2],
                "share": [0.6667, 0.6667, 0.6667, 0.3333, 0.5],
            }
        ),
        "fct_skill_pairs": pd.DataFrame(
            {
                "skill_a": ["django", "docker", "python"],
                "skill_b": ["docker", "python", "sql"],
                "vacancies_together": [2, 1, 1],
                "vacancies_total": [3, 3, 3],
                "lift": [1.5, 1.5, 1.0],
                "npmi": [1.0, 0.369, None],
            }
        ),
        "fct_salary_by_skill": pd.DataFrame(
            {
                "skill_id": ["python"],
                "vacancies_with_salary": [2],
                "salary_p25": [2500.0],
                "salary_median": [3000.0],
                "salary_p75": [3500.0],
            }
        ),
        "fct_salary_survey": pd.DataFrame(
            {
                "survey_year": [2025, 2024, 2025],
                "role": ["qa", "qa", "software_engineer"],
                "seniority": ["senior", "senior", "middle"],
                "respondents": [40.0, 30.0, 100.0],
                "salary_p25": [2000.0, 1800.0, 1500.0],
                "salary_median": [3000.0, 2700.0, 2200.0],
                "salary_p75": [4000.0, 3600.0, 3000.0],
            }
        ),
        "fct_vacancy_lifetime": pd.DataFrame(
            {
                "seniority": ["middle"],
                "closed_vacancies": [12],
                "lifetime_p25": [9.0],
                "lifetime_median": [14.0],
                "lifetime_p75": [21.0],
            }
        ),
        "fct_market_daily": pd.DataFrame(
            {
                "date": [
                    date(2026, 11, 1),
                    date(2026, 11, 1),
                    date(2026, 11, 2),
                    date(2026, 11, 2),
                ],
                "source": ["dou", "djinni", "dou", "djinni"],
                "category": ["Python", "QA", "Python", "QA"],
                "seniority": ["senior", "middle", "senior", "middle"],
                "open_vacancies": [10, 6, 12, 5],
                "new_vacancies": [10, 6, 3, 0],
                "closed_vacancies": [0, 0, 1, 1],
            }
        ),
        "skill_clusters": pd.DataFrame(
            {
                "skill_id": ["django", "docker", "python"],
                "cluster_id": [1, 1, 1],
                "cluster_size": [3, 3, 3],
                "cluster_label": ["python", "python", "python"],
            }
        ),
    }


STATUS = {
    "generated_at": "2026-11-09T12:00:00Z",
    "runs": [
        {
            "run_id": "flow-daily-2026-11-09-1",
            "flow": "daily",
            "run_date": "2026-11-09",
            "status": "success",
            "trigger": "cron",
            "started_at": "2026-11-09T04:00:00",
            "duration_s": 840,
            "failed_steps": None,
            "run_url": "https://example.com/run/1",
        },
        {
            "run_id": "flow-daily-2026-11-08-1",
            "flow": "daily",
            "run_date": "2026-11-08",
            "status": "failed",
            "trigger": "cron",
            "started_at": "2026-11-08T04:00:00",
            "duration_s": 60,
            "failed_steps": "parse",
            "run_url": None,
        },
    ],  # fmt: skip
    "steps": [
        {
            "run_date": "2026-11-09",
            "step": "scrape",
            "attempt": 1,
            "status": "success",
            "duration_s": 600,
        },
        {
            "run_date": "2026-11-09",
            "step": "dbt",
            "attempt": 1,
            "status": "success",
            "duration_s": 120,
        },
    ],  # fmt: skip
    "scrape": [
        {
            "run_date": "2026-11-09",
            "source": "dou",
            "pages": 800,
            "errors": 2,
            "http_429": 0,
            "http_403": 0,
        },
    ],  # fmt: skip
    "dq_latest": [
        {
            "check": "fresh_data",
            "layer": "silver",
            "status": "pass",
            "observed": 3.0,
            "detail": "newest page fetched 3.0 h ago",
        },
        {
            "check": "references",
            "layer": "silver",
            "status": "warn",
            "observed": 1.0,
            "detail": "1 orphan",
        },
    ],  # fmt: skip
    "volumes": {
        "silver_vacancies": 100,
        "silver_vacancy_skills": 900,
        "silver_vacancy_sightings": 400,
    },
    "slo": [
        {
            "name": "data_freshness",
            "target": "last scrape at most 36 h ago",
            "observed": "3.0 h",
            "ok": True,
            "detail": "fine",
        },
        {
            "name": "success_rate",
            "target": ">= 95%",
            "observed": "1/2",
            "ok": None,
            "detail": "too few runs yet",
        },
    ],  # fmt: skip
}

LAST_UPDATE = {
    "exported_at": "2026-11-09T04:15:00+00:00",
    "tables": {"dim_skill": {"rows": 4, "bytes": 100, "sha256": "x"}},
}


GRID = pd.DataFrame(
    {
        "role": ["qa"] * 6,
        "seniority": ["senior"] * 6,
        "experience_years": [3.0, 5.0, 10.0, 3.0, 5.0, 10.0],
        "english": ["intermediate"] * 3 + ["upper-intermediate"] * 3,
        "city_group": ["ukraine"] * 6,
        "survey_year": [2026] * 6,
        "salary_p10": [1500.0, 1800.0, 2400.0, 1700.0, 2000.0, 2600.0],
        "salary_p50": [2500.0, 3000.0, 4000.0, 2800.0, 3300.0, 4300.0],
        "salary_p90": [3800.0, 4400.0, 6000.0, 4100.0, 4800.0, 6500.0],
    }
)
GRID_INFO = {
    "version": 3,
    "tested_on_year": 2026,
    "model": {"mae": 1245.0, "coverage_10_90": 0.795, "interval_width": 3900.0},
    "baseline": {"mae": 1405.0, "coverage_10_90": 0.752, "interval_width": 3600.0},
}


def write_grid(directory: Path) -> None:
    """The salary model's grid and description, which only exist after `make train`."""
    con = duckdb.connect()
    con.register("frame", GRID)
    target = directory / "salary_model_grid.parquet"
    con.execute(f"COPY (SELECT * FROM frame) TO '{target}' (FORMAT parquet)")
    (directory / "salary_model.json").write_text(json.dumps(GRID_INFO), encoding="utf-8")


def write_export(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for name, frame in tables().items():
        con.register("frame", frame)
        con.execute(
            f"COPY (SELECT * FROM frame) TO '{directory / (name + '.parquet')}' (FORMAT parquet)"
        )
        con.unregister("frame")
    (directory / "status.json").write_text(json.dumps(STATUS), encoding="utf-8")
    (directory / "last_update.json").write_text(json.dumps(LAST_UPDATE), encoding="utf-8")
    return directory
