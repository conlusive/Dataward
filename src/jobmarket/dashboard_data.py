"""What the dashboard shows, as plain functions over the exported parquet files (no Streamlit here).

The dashboard reads only `data/export/*.parquet` and `status.json`, never the database. Each table
is checked against what the dashboard needs (`REQUIRED`), so a producer that renames a column gives
a clear message instead of a stack trace; a test keeps `REQUIRED` inside the dbt contracts.
"""

import json
import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

DEFAULT_DIR = Path("data/export")

# Consumer side of the contract: the columns each page reads.
REQUIRED: dict[str, set[str]] = {
    "dim_skill": {"skill_id", "canonical", "category", "parent_id"},
    "fct_skill_demand_monthly": {
        "month",
        "skill_id",
        "vacancies",
        "vacancies_required",
        "month_vacancies",
        "share",
    },  # fmt: skip
    "fct_skill_pairs": {
        "skill_a",
        "skill_b",
        "vacancies_together",
        "vacancies_total",
        "lift",
        "npmi",
    },  # fmt: skip
    "fct_salary_by_skill": {
        "skill_id",
        "vacancies_with_salary",
        "salary_p25",
        "salary_median",
        "salary_p75",
    },  # fmt: skip
    "fct_salary_survey": {
        "survey_year",
        "role",
        "seniority",
        "respondents",
        "salary_p25",
        "salary_median",
        "salary_p75",
    },  # fmt: skip
    "fct_vacancy_lifetime": {
        "seniority",
        "closed_vacancies",
        "lifetime_p25",
        "lifetime_median",
        "lifetime_p75",
    },  # fmt: skip
    "fct_market_daily": {
        "date",
        "source",
        "category",
        "seniority",
        "open_vacancies",
        "new_vacancies",
        "closed_vacancies",
    },  # fmt: skip
    "skill_clusters": {"skill_id", "cluster_id", "cluster_size", "cluster_label"},
}


# The salary model's grid is optional: it exists only after `make train`.
GRID_FILE = "salary_model_grid.parquet"
GRID_INFO_FILE = "salary_model.json"
GRID_COLUMNS = {
    "role", "seniority", "experience_years", "english", "city_group", "survey_year",
    "salary_p10", "salary_p50", "salary_p90",
}  # fmt: skip


class DataError(Exception):
    """A file is missing or lacks a column the dashboard needs."""


def data_dir() -> Path:
    return Path(os.environ.get("DASHBOARD_DATA_DIR") or DEFAULT_DIR)


def read_table(directory: Path, name: str) -> pd.DataFrame:
    path = directory / f"{name}.parquet"
    if not path.exists():
        raise DataError(f"{path} not found: run the pipeline (`make pipeline`) to create it")
    frame = duckdb.connect().execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
    missing = REQUIRED.get(name, set()) - set(frame.columns)
    if missing:
        raise DataError(f"{name}.parquet lacks the columns {sorted(missing)}: update the export")
    return frame


def read_json(directory: Path, name: str) -> dict[str, Any]:
    path = directory / name
    if not path.exists():
        raise DataError(f"{path} not found: run the pipeline (`make pipeline`) to create it")
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


# ---- salary calculator ---------------------------------------------------------------------------
def read_grid(directory: Path) -> tuple[pd.DataFrame, dict[str, Any]] | None:
    """The model's grid and its description, or None when no model has been trained yet."""
    path = directory / GRID_FILE
    if not path.exists():
        return None
    grid = duckdb.connect().execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
    missing = GRID_COLUMNS - set(grid.columns)
    if missing:
        raise DataError(f"{GRID_FILE} lacks the columns {sorted(missing)}: run `make train` again")
    return grid, read_json(directory, GRID_INFO_FILE)


def grid_lookup(
    grid: pd.DataFrame,
    *,
    role: str,
    seniority: str,
    experience: float,
    english: str,
    city_group: str,
) -> dict[str, float] | None:
    """The range for a profile, at the grid's experience closest to ``experience``; None if the
    profile is not in the grid."""
    rows = grid[
        (grid["role"] == role)
        & (grid["seniority"] == seniority)
        & (grid["english"] == english)
        & (grid["city_group"] == city_group)
    ]
    if rows.empty:
        return None
    nearest = rows.iloc[(rows["experience_years"] - experience).abs().argsort().iloc[0]]
    return {
        "p10": float(nearest["salary_p10"]),
        "p50": float(nearest["salary_p50"]),
        "p90": float(nearest["salary_p90"]),
        "experience_used": float(nearest["experience_years"]),
    }


# ---- market overview -------------------------------------------------------------------------
def filter_market(
    market: pd.DataFrame,
    *,
    sources: list[str] | None = None,
    categories: list[str] | None = None,
    seniorities: list[str] | None = None,
) -> pd.DataFrame:
    keep = pd.Series(True, index=market.index)
    for column, values in (
        ("source", sources), ("category", categories), ("seniority", seniorities),
    ):  # fmt: skip
        if values:
            keep &= market[column].isin(values)
    return market[keep]


def open_by_day(market: pd.DataFrame) -> pd.DataFrame:
    """Open vacancies per day, one column per source (ready for a line chart)."""
    grouped = market.groupby(["date", "source"], as_index=False)["open_vacancies"].sum()
    return grouped.pivot(index="date", columns="source", values="open_vacancies").fillna(0)


def open_by_category(market: pd.DataFrame, *, top: int = 15) -> pd.DataFrame:
    """Open vacancies by category on the latest day in ``market``, most first."""
    if market.empty:
        return pd.DataFrame(columns=["category", "open_vacancies"])
    latest = market[market["date"] == market["date"].max()]
    counts = latest.groupby("category", as_index=False)["open_vacancies"].sum()
    return counts.sort_values("open_vacancies", ascending=False).head(top).reset_index(drop=True)


def market_totals(market: pd.DataFrame) -> pd.DataFrame:
    """One row per day: open, new and closed vacancies summed over the selected slice."""
    daily = market.groupby("date", as_index=False)[
        ["open_vacancies", "new_vacancies", "closed_vacancies"]
    ].sum()
    return daily.sort_values("date").reset_index(drop=True)


def open_by_seniority(market: pd.DataFrame) -> pd.DataFrame:
    """Open vacancies by level on the latest day in ``market``, most first.

    A vacancy that names no level is stored as "unknown"; it is shown as "не вказано".
    """
    if market.empty:
        return pd.DataFrame(columns=["seniority", "open_vacancies"])
    latest = market[market["date"] == market["date"].max()]
    counts = latest.groupby("seniority", as_index=False)["open_vacancies"].sum()
    counts["seniority"] = counts["seniority"].replace({"unknown": "не вказано"})
    return counts.sort_values("open_vacancies", ascending=False).reset_index(drop=True)


# ---- skills ----------------------------------------------------------------------------------
MIN_MONTH_VACANCIES = 200  # fewer new vacancies than this and a share is mostly noise


def latest_month(demand: pd.DataFrame, *, min_vacancies: int = MIN_MONTH_VACANCIES) -> Any:
    """The newest month with enough vacancies to give meaningful shares.

    A month that has only just begun holds a handful of vacancies, and a skill in one of three is
    "33%". When no month is big enough (a young dataset) the newest month is used as it is.
    """
    sizes = demand.groupby("month")["month_vacancies"].max()
    enough = sizes[sizes >= min_vacancies]
    return enough.index.max() if len(enough) else demand["month"].max()


def top_skills(
    demand: pd.DataFrame,
    skills: pd.DataFrame,
    *,
    month: Any,
    n: int = 20,
    category: str | None = None,
) -> pd.DataFrame:
    """The skills most often asked for in ``month`` with their share of that month's vacancies."""
    rows = demand[demand["month"] == month].merge(skills, on="skill_id", how="left")
    if category:
        rows = rows[rows["category"] == category]
    columns = ["canonical", "category", "vacancies", "share"]
    return (
        rows.sort_values(["share", "canonical"], ascending=[False, True])
        .head(n)[columns]
        .reset_index(drop=True)
    )


def month_options(demand: pd.DataFrame, *, min_vacancies: int = MIN_MONTH_VACANCIES) -> list[Any]:
    """Months to choose from, newest first; those with too few vacancies for a share are left out
    unless that would leave nothing (a young dataset)."""
    sizes = demand.groupby("month")["month_vacancies"].max()
    enough = sizes[sizes >= min_vacancies]
    chosen = enough if len(enough) else sizes
    return sorted(chosen.index, reverse=True)


def skill_ranking(
    demand: pd.DataFrame,
    skills: pd.DataFrame,
    salary: pd.DataFrame,
    *,
    month: Any,
    previous: Any = None,
) -> pd.DataFrame:
    """Every skill seen in ``month`` with what an analyst compares: share, how often it is a hard
    requirement, the change against ``previous`` (percentage points) and the declared salary.

    ``change_pp`` is empty when there is no earlier month or the skill was not seen then.
    """
    rows = demand[demand["month"] == month].merge(skills, on="skill_id", how="left")
    rows["required_share"] = rows["vacancies_required"] / rows["month_vacancies"]
    if previous is not None:
        before = demand.loc[demand["month"] == previous, ["skill_id", "share"]]
        rows = rows.merge(
            before.rename(columns={"share": "share_before"}), on="skill_id", how="left"
        )
        rows["change_pp"] = (rows["share"] - rows["share_before"]) * 100
    else:
        rows["change_pp"] = float("nan")
    paid = salary[["skill_id", "vacancies_with_salary", "salary_median"]]
    rows = rows.merge(paid, on="skill_id", how="left")
    columns = [
        "skill_id", "canonical", "category", "vacancies", "share", "required_share",
        "change_pp", "salary_median", "vacancies_with_salary",
    ]  # fmt: skip
    ranked = rows.sort_values(["share", "canonical"], ascending=[False, True])[columns]
    return ranked.reset_index(drop=True)


def salary_ranking(
    salary: pd.DataFrame, skills: pd.DataFrame, *, min_vacancies: int = 1
) -> pd.DataFrame:
    """Declared-salary percentiles per skill, highest median first (the mart already hides skills
    with too few vacancies; ``min_vacancies`` lets the reader ask for more)."""
    rows = salary[salary["vacancies_with_salary"] >= min_vacancies].merge(
        skills[["skill_id", "canonical", "category"]], on="skill_id", how="left"
    )
    columns = [
        "canonical", "category", "vacancies_with_salary", "salary_p25", "salary_median",
        "salary_p75",
    ]  # fmt: skip
    return rows.sort_values("salary_median", ascending=False)[columns].reset_index(drop=True)


def skill_trend(demand: pd.DataFrame, skill_id: str) -> pd.DataFrame:
    rows = demand[demand["skill_id"] == skill_id].sort_values("month")
    return rows[["month", "share", "vacancies", "month_vacancies"]].reset_index(drop=True)


def related_skills(
    pairs: pd.DataFrame, skills: pd.DataFrame, skill_id: str, *, top: int = 10
) -> pd.DataFrame:
    """Skills that appear with ``skill_id`` most strongly (by NPMI), from either side of a pair."""
    as_a = pairs[pairs["skill_a"] == skill_id].rename(columns={"skill_b": "other"})
    as_b = pairs[pairs["skill_b"] == skill_id].rename(columns={"skill_a": "other"})
    both = pd.concat([as_a, as_b])
    both = both[both["npmi"].notna()].merge(
        skills[["skill_id", "canonical"]], left_on="other", right_on="skill_id", how="left"
    )
    columns = ["canonical", "vacancies_together", "lift", "npmi"]
    return both.sort_values("npmi", ascending=False).head(top)[columns].reset_index(drop=True)


def skill_salary(salary: pd.DataFrame, skill_id: str) -> dict[str, float] | None:
    """The declared-salary percentiles of the skill, or None when too few vacancies state one."""
    row = salary[salary["skill_id"] == skill_id]
    if row.empty:
        return None
    first = row.iloc[0]
    return {
        "vacancies": float(first["vacancies_with_salary"]),
        "p25": float(first["salary_p25"]),
        "median": float(first["salary_median"]),
        "p75": float(first["salary_p75"]),
    }


def skill_cluster(
    clusters: pd.DataFrame, skills: pd.DataFrame, skill_id: str
) -> dict[str, Any] | None:
    row = clusters[clusters["skill_id"] == skill_id]
    if row.empty:
        return None
    cluster_id = int(row.iloc[0]["cluster_id"])
    members = clusters[clusters["cluster_id"] == cluster_id].merge(
        skills, on="skill_id", how="left"
    )
    return {
        "cluster_id": cluster_id,
        "size": int(row.iloc[0]["cluster_size"]),
        "label": str(row.iloc[0]["cluster_label"]),
        "members": sorted(members["canonical"].dropna().tolist()),
    }


# ---- stacks ----------------------------------------------------------------------------------
def cluster_overview(clusters: pd.DataFrame, skills: pd.DataFrame) -> pd.DataFrame:
    """One row per cluster: id, size, label and its members."""
    names = clusters.merge(skills[["skill_id", "canonical"]], on="skill_id", how="left")
    rows = []
    for cluster_id, group in names.groupby("cluster_id"):
        rows.append(
            {
                "cluster_id": int(cluster_id),
                "size": len(group),
                "label": str(group["cluster_label"].iloc[0]),
                "members": ", ".join(sorted(group["canonical"].dropna())),
            }
        )
    return pd.DataFrame(rows, columns=["cluster_id", "size", "label", "members"])


STACK_EDGE_LIMIT = 60  # more lines than this turn a graph into a hairball nobody can read


def stack_edges(
    pairs: pd.DataFrame, clusters: pd.DataFrame, cluster_id: int, *, min_npmi: float = 0.3
) -> tuple[pd.DataFrame, int]:
    """The strongest links of one cluster: (at most STACK_EDGE_LIMIT edges, how many qualified)."""
    members = set(clusters.loc[clusters["cluster_id"] == cluster_id, "skill_id"])
    edges = pairs[
        pairs["skill_a"].isin(members)
        & pairs["skill_b"].isin(members)
        & (pairs["npmi"] >= min_npmi)
    ].sort_values("npmi", ascending=False)
    return edges.head(STACK_EDGE_LIMIT), len(edges)


def stack_dot(
    pairs: pd.DataFrame, clusters: pd.DataFrame, skills: pd.DataFrame, cluster_id: int,
    *, min_npmi: float = 0.3,
) -> str:  # fmt: skip
    """The pair graph of one cluster as Graphviz DOT; edge width grows with NPMI.

    Only the strongest links are drawn and only the skills they touch, so the graph stays readable.
    """
    edges, _ = stack_edges(pairs, clusters, cluster_id, min_npmi=min_npmi)
    names = dict(zip(skills["skill_id"], skills["canonical"], strict=False))
    touched = set(edges["skill_a"]) | set(edges["skill_b"])

    def quote(text: str) -> str:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = [
        "graph G {",
        '  bgcolor="transparent"; layout=neato; overlap=false; sep="+8";',
        '  node [shape=ellipse, style=filled, fillcolor="#28282A", color="#AAA8FF",'
        ' fontcolor="#ECECF1", fontname="Helvetica", fontsize=14];',
        '  edge [color="#8481F5"];',
    ]
    lines += [f"  {quote(names.get(m, m))};" for m in sorted(touched)]
    for _, e in edges.iterrows():
        width = 0.5 + 3.5 * float(e["npmi"])
        a, b = names.get(e["skill_a"], e["skill_a"]), names.get(e["skill_b"], e["skill_b"])
        lines.append(f"  {quote(a)} -- {quote(b)} [penwidth={width:.2f}];")
    lines.append("}")
    return "\n".join(lines)


# ---- salary and lifetime ---------------------------------------------------------------------
def survey_benchmark(
    survey: pd.DataFrame, *, role: str, seniority: str | None = None
) -> pd.DataFrame:
    """Survey percentiles for a role by year (and by level when given), newest year first."""
    rows = survey[survey["role"] == role]
    if seniority:
        rows = rows[rows["seniority"] == seniority]
    columns = [
        "survey_year",
        "seniority",
        "respondents",
        "salary_p25",
        "salary_median",
        "salary_p75",
    ]
    return rows.sort_values(["survey_year", "seniority"], ascending=[False, True])[
        columns
    ].reset_index(drop=True)


# ---- status and about ------------------------------------------------------------------------
def slo_table(status: dict[str, Any]) -> pd.DataFrame:
    marks = {True: "✓ виконано", False: "✕ порушено", None: "… замало даних"}
    return pd.DataFrame(
        [
            {
                "SLO": s["name"],
                "ціль": s["target"],
                "зараз": s["observed"],
                "стан": marks[s["ok"]],
                "деталі": s["detail"],
            }  # fmt: skip
            for s in status["slo"]
        ]
    )


def runs_table(status: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "дата": r["run_date"],
                "потік": r["flow"],
                "статус": r["status"],
                "тригер": r["trigger"],
                "тривалість, с": r["duration_s"],
                "впали кроки": r["failed_steps"] or "",
            }  # fmt: skip
            for r in status["runs"]
        ]
    )


def health(status: dict[str, Any]) -> tuple[str, str, str]:
    """The pipeline in one line: (tone, headline, detail); tone is ok, warn, bad or neutral."""
    slos = status["slo"]
    broken = [s for s in slos if s["ok"] is False]
    checks = status.get("dq_latest", [])
    errors = [c for c in checks if c["status"] == "error"]
    warnings = [c for c in checks if c["status"] == "warn"]
    kept = sum(1 for s in slos if s["ok"] is True)
    if broken or errors:
        return (
            "bad",
            "Є порушення",
            f"SLO порушено: {len(broken)}, перевірок із помилкою: {len(errors)}",
        )
    if warnings:
        return "warn", "Є зауваження", f"перевірок із попередженням: {len(warnings)}"
    if slos and kept == 0:
        return "neutral", "Замало даних", "SLO ще не мають достатньо запусків"
    return "ok", "Усе в нормі", f"SLO виконано: {kept} з {len(slos)}"


def fmt_int(number: float) -> str:
    """1234567 -> "1 234 567" (a no-break space, as in Ukrainian typography)."""
    return f"{int(round(number)):,}".replace(",", "\u00a0")


def stamp(iso: str) -> str:
    """An ISO time as "09.11.2026 00:19 UTC" (the exports are written in UTC)."""
    moment = pd.Timestamp(iso)
    moment = moment.tz_localize("UTC") if moment.tzinfo is None else moment.tz_convert("UTC")
    return str(moment.strftime("%d.%m.%Y %H:%M UTC"))
