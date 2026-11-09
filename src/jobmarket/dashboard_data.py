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


# The vacancy catalog is optional too: it lists third-party vacancies, so it is exported for local
# use only and is absent from the public CI artifact (see `private_tables` in export.py).
CATALOG_FILE = "fct_vacancy_catalog.parquet"
CATALOG_COLUMNS = {
    "vacancy_id", "title", "company", "source", "category", "seniority", "remote", "locations",
    "english_level", "experience_years", "salary_usd_min", "salary_usd_max", "first_listed_on",
    "last_seen_on", "is_open", "members", "url", "url_other", "skills", "skills_required",
}  # fmt: skip

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


# ---- the vacancy catalog ---------------------------------------------------------------------
NO_LEVEL = "unknown"  # what the pipeline stores for a vacancy that names no level
SORTS = {
    "Нові спочатку": (["first_listed_on", "title"], [False, True]),
    "Зарплата: від більшої": (["salary_top", "title"], [False, True]),
    "Більше навичок": (["n_skills", "title"], [False, True]),
    "Назва А–Я": (["title"], [True]),
}


def read_catalog(directory: Path) -> pd.DataFrame | None:
    """The vacancy catalog, or None when this export has none (the CI artifact never has it)."""
    path = directory / CATALOG_FILE
    if not path.exists():
        return None
    frame = pd.read_parquet(path)
    missing = CATALOG_COLUMNS - set(frame.columns)
    if missing:
        raise DataError(f"{CATALOG_FILE} lacks the columns {sorted(missing)}: update the export")
    frame = frame.copy()
    frame["seniority"] = frame["seniority"].fillna(NO_LEVEL)
    frame["company"] = frame["company"].fillna("")
    frame["category"] = frame["category"].fillna("")
    frame["locations"] = frame["locations"].fillna("")
    frame["skills"] = frame["skills"].map(lambda items: list(items) if items is not None else [])
    frame["skills_required"] = frame["skills_required"].map(
        lambda items: list(items) if items is not None else []
    )
    frame["first_listed_on"] = pd.to_datetime(frame["first_listed_on"]).dt.date
    frame["salary_top"] = frame["salary_usd_max"].fillna(frame["salary_usd_min"])
    frame["salary_mid"] = frame[["salary_usd_min", "salary_usd_max"]].mean(axis=1)
    frame["n_skills"] = frame["skills"].map(len)
    return frame


def filter_catalog(
    catalog: pd.DataFrame,
    *,
    query: str = "",
    categories: list[str] | None = None,
    levels: list[str] | None = None,
    sources: list[str] | None = None,
    skills: list[str] | None = None,
    all_skills: bool = True,
    only_open: bool = False,
    with_salary: bool = False,
    min_salary: float = 0,
    remote_only: bool = False,
    listed_since: Any = None,
) -> pd.DataFrame:
    """The vacancies that pass every filter that is set; an unset filter lets everything through.

    ``query`` must be found in the title or the company (every word, any case). ``skills`` need
    all of the chosen skills by default, or any of them with ``all_skills=False``.
    ``min_salary`` is USD a month and is compared with the top of the vacancy's range.
    """
    keep = pd.Series(True, index=catalog.index)
    for word in query.lower().split():
        text = (catalog["title"].fillna("") + " " + catalog["company"]).str.lower()
        keep &= text.str.contains(word, regex=False)
    for column, values in (
        ("category", categories), ("seniority", levels), ("source", sources),
    ):  # fmt: skip
        if values:
            keep &= catalog[column].isin(values)
    if skills:
        wanted = set(skills)
        if all_skills:
            keep &= catalog["skills"].map(lambda have: wanted <= set(have))
        else:
            keep &= catalog["skills"].map(lambda have: bool(wanted & set(have)))
    if only_open:
        keep &= catalog["is_open"]
    if with_salary or min_salary > 0:
        keep &= catalog["salary_top"].notna()
    if min_salary > 0:
        keep &= catalog["salary_top"] >= min_salary
    if remote_only:
        keep &= catalog["remote"].fillna(False)
    if listed_since is not None:
        keep &= catalog["first_listed_on"] >= listed_since
    return catalog[keep]


def sort_catalog(catalog: pd.DataFrame, how: str) -> pd.DataFrame:
    """One of ``SORTS``; vacancies with no salary go last in the salary order."""
    columns, ascending = SORTS[how]
    return catalog.sort_values(columns, ascending=ascending, na_position="last", kind="stable")


def salary_label(low: float | None, high: float | None) -> str:
    """ "2 000–3 500 $", "від 2 000 $", "до 3 500 $" or "" when the vacancy states no salary."""
    first = None if low is None or pd.isna(low) else fmt_int(low)
    last = None if high is None or pd.isna(high) else fmt_int(high)
    if first and last:
        return f"{first}–{last} $" if first != last else f"{first} $"
    if first:
        return f"від {first} $"
    if last:
        return f"до {last} $"
    return ""


def skill_counts(catalog: pd.DataFrame, *, top: int = 15) -> pd.DataFrame:
    """Which skills the vacancies in ``catalog`` ask for: ``skill``, ``vacancies``, ``share``."""
    if catalog.empty:
        return pd.DataFrame(columns=["skill", "vacancies", "share"])
    counts = catalog["skills"].explode().dropna().value_counts()
    frame = counts.rename_axis("skill").reset_index(name="vacancies")
    frame["share"] = frame["vacancies"] / len(catalog)
    return frame.sort_values(["vacancies", "skill"], ascending=[False, True]).head(top)


def company_counts(catalog: pd.DataFrame, *, top: int = 15) -> pd.DataFrame:
    """The companies with the most vacancies in ``catalog``: ``company``, ``vacancies``."""
    named = catalog[catalog["company"] != ""]
    counts = named["company"].value_counts()
    frame = counts.rename_axis("company").reset_index(name="vacancies")
    return frame.sort_values(["vacancies", "company"], ascending=[False, True]).head(top)


def catalog_options(catalog: pd.DataFrame, column: str) -> list[str]:
    """The values of a column to offer in a filter, most frequent first (blank ones left out)."""
    counts = catalog[column].replace("", pd.NA).dropna().value_counts()
    ordered = sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
    return [str(value) for value, _ in ordered]


def skill_options(catalog: pd.DataFrame) -> list[str]:
    """Every skill that occurs in the catalog, most frequent first."""
    return [str(name) for name in skill_counts(catalog, top=10_000)["skill"]]


TABLE_SKILLS = 6  # skills named in a row of the table; the card shows all of them


def where_label(locations: str, remote: object) -> str:
    place = locations or ""
    if remote is True or remote == 1:
        return f"{place} · віддалено" if place else "віддалено"
    return place


def catalog_table(catalog: pd.DataFrame) -> pd.DataFrame:
    """The vacancies as the table shows them: readable columns, salary as text, the link last."""
    skills = catalog["skills"].map(
        lambda have: (
            ", ".join(have[:TABLE_SKILLS])
            + (f" +{len(have) - TABLE_SKILLS}" if len(have) > TABLE_SKILLS else "")
        )
    )
    return pd.DataFrame(
        {
            "Назва": catalog["title"].to_numpy(),
            "Компанія": catalog["company"].to_numpy(),
            "Напрямок": catalog["category"].to_numpy(),
            "Рівень": catalog["seniority"].replace({NO_LEVEL: "—"}).to_numpy(),
            "Зарплата": [
                salary_label(low, high)
                for low, high in zip(
                    catalog["salary_usd_min"], catalog["salary_usd_max"], strict=True
                )
            ],
            "Навички": skills.to_numpy(),
            "Де": [
                where_label(place, remote)
                for place, remote in zip(catalog["locations"], catalog["remote"], strict=True)
            ],
            "Джерело": catalog["source"].to_numpy(),
            "З'явилась": catalog["first_listed_on"].to_numpy(),
            "Посилання": catalog["url"].to_numpy(),
        }
    )


LIST_SKILLS = 3  # skills shown in a row of the compact list; the card shows all of them
PAGE_SIZE = 15  # vacancies on a page of the list


def list_table(catalog: pd.DataFrame) -> pd.DataFrame:
    """The compact table of the vacancy list: few columns, so it never scrolls sideways.

    The title and the company share one cell; everything else (direction, place, dates, both links)
    is in the card of the picked vacancy and in the CSV, which uses ``catalog_table``.
    """
    names = [
        f"{title} · {company}" if isinstance(company, str) and company.strip() else str(title)
        for title, company in zip(catalog["title"], catalog["company"], strict=True)
    ]
    skills = catalog["skills"].map(
        lambda have: (
            ", ".join(have[:LIST_SKILLS])
            + (f" +{len(have) - LIST_SKILLS}" if len(have) > LIST_SKILLS else "")
        )
    )
    return pd.DataFrame(
        {
            "Вакансія": names,
            "Рівень": catalog["seniority"].replace({NO_LEVEL: "—"}).to_numpy(),
            "Зарплата": [
                salary_label(low, high)
                for low, high in zip(
                    catalog["salary_usd_min"], catalog["salary_usd_max"], strict=True
                )
            ],
            "Навички": skills.to_numpy(),
            "Посилання": catalog["url"].to_numpy(),
        }
    )


def page_of(total: int, page: int, size: int = PAGE_SIZE) -> tuple[int, int, int]:
    """(page, first, last) for a list of ``total`` rows: the page is kept inside the list.

    ``first`` is the index of the first row and ``last`` one past the last, so ``rows[first:last]``
    is the page; an empty list has one empty page.
    """
    pages = max(1, -(-total // size))
    page = min(max(page, 0), pages - 1)
    return page, page * size, min(total, (page + 1) * size)


def median_salary(catalog: pd.DataFrame) -> float | None:
    """The median mid-range salary (USD a month), or None when no vacancy states a salary."""
    mids = catalog["salary_mid"].dropna()
    return float(mids.median()) if len(mids) else None


def listed_within(catalog: pd.DataFrame, days: int) -> int:
    """How many vacancies first appeared in the last ``days`` days before the newest one."""
    if catalog.empty:
        return 0
    cutoff = catalog["first_listed_on"].max() - pd.Timedelta(days=days)
    return int((catalog["first_listed_on"] > cutoff).sum())


# ---- the home page: breakdowns, directions, runs ------------------------------------------------
METRICS = {
    "Відкриті": "open_vacancies", "Нові": "new_vacancies", "Закриті": "closed_vacancies",
}  # fmt: skip
BREAKDOWNS = {"Джерело": "source", "Рівень": "seniority", "Напрямок": "category"}
OTHER = "Інші"


def daily_breakdown(
    market: pd.DataFrame, metric: str, by: str, *, top: int = 4
) -> tuple[pd.DataFrame, list[str]]:
    """A metric per day split by ``by``: (``date``, ``series``, ``value``) and the stack order.

    The ``top`` biggest values stay as they are; the rest are folded into "Інші" so that a chart
    never needs more than ``top`` + 1 colours. A source is never folded (there are two).
    """
    renamed = market.assign(**{by: market[by].replace({NO_LEVEL: "не вказано"})})
    totals = renamed.groupby(by)[metric].sum().sort_values(ascending=False)
    keep = list(totals.index) if by == "source" else list(totals.head(top).index)
    series = renamed[by].where(renamed[by].isin(keep), OTHER)
    daily = (
        renamed.assign(series=series)
        .groupby(["date", "series"], as_index=False)[metric]
        .sum()
        .rename(columns={metric: "value"})
    )
    order = [name for name in keep if name in set(daily["series"])]
    if OTHER in set(daily["series"]):
        order.append(OTHER)
    return daily, order


def direction_stats(
    market: pd.DataFrame, catalog: pd.DataFrame | None = None, *, top: int = 8
) -> pd.DataFrame:
    """The biggest directions on the latest day: ``category``, ``open``, ``share`` of all open
    vacancies and, when a catalog is at hand, the three skills its open vacancies ask for most."""
    if market.empty:
        return pd.DataFrame(columns=["category", "open", "share", "skills"])
    latest = market[market["date"] == market["date"].max()]
    counts = latest.groupby("category")["open_vacancies"].sum().sort_values(ascending=False)
    total = float(counts.sum()) or 1.0
    rows = []
    for category, open_now in counts.head(top).items():
        skills: list[str] = []
        if catalog is not None:
            here = catalog[(catalog["category"] == category) & catalog["is_open"]]
            skills = skill_counts(here, top=3)["skill"].tolist()
        rows.append(
            {"category": str(category), "open": int(open_now), "share": open_now / total,
             "skills": skills}
        )  # fmt: skip
    return pd.DataFrame(rows, columns=["category", "open", "share", "skills"])


def run_states(status: dict[str, Any], *, last: int = 14) -> list[tuple[str, str]]:
    """The last pipeline runs, oldest first, as (label, tone) for the squares of a pulse strip."""
    tones = {"success": "ok", "failed": "bad"}
    runs = status.get("runs", [])[:last]
    return [
        (f"{run['run_date']}: {run['status']}", tones.get(run["status"], "warn"))
        for run in reversed(runs)
    ]


def short_list(values: list[str], limit: int = 2) -> str:
    """ "a, b" for up to ``limit`` values, "a, b +3" for more: a long selection in a small tag."""
    shown = ", ".join(values[:limit])
    return f"{shown} +{len(values) - limit}" if len(values) > limit else shown


# ---- analysing one vacancy ----------------------------------------------------------------------
PEER_MIN = 5  # fewer comparable salaries than this say nothing about a direction


def skill_shares(demand: pd.DataFrame, skills: pd.DataFrame, *, month: Any) -> dict[str, float]:
    """Skill name -> the share of that month's vacancies that ask for it (0-1)."""
    rows = demand[demand["month"] == month].merge(skills[["skill_id", "canonical"]], on="skill_id")
    return {
        str(name): float(share)
        for name, share in zip(rows["canonical"], rows["share"], strict=True)
    }


def vacancy_analysis(row: Any, catalog: pd.DataFrame, shares: dict[str, float]) -> dict[str, Any]:
    """What a reader wants to know about one vacancy next to the market.

    ``skills``: each skill of the vacancy with its share of the whole market and whether it is
    required; ``salary``: the vacancy's mid-range against the median of the open vacancies of the
    same direction (None when too few state a salary); ``days_listed`` and ``similar`` (open
    vacancies of the same direction and level, not counting this one).
    """
    required = set(row["skills_required"])
    skills = sorted(
        (
            {"skill": name, "share": shares.get(name), "required": name in required}
            for name in row["skills"]
        ),
        key=lambda item: (-(item["share"] or 0.0), item["skill"]),
    )
    peers = catalog[(catalog["category"] == row["category"]) & catalog["is_open"]]
    paid = peers["salary_mid"].dropna()
    mid = row["salary_mid"] if pd.notna(row["salary_mid"]) else None
    listed = pd.Timestamp(row["last_seen_on"]) - pd.Timestamp(row["first_listed_on"])
    same_level = peers[peers["seniority"] == row["seniority"]]
    return {
        "skills": skills,
        "salary": {
            "mid": None if mid is None else float(mid),
            "peer_median": float(paid.median()) if len(paid) >= PEER_MIN else None,
            "peers": len(paid),
        },
        "days_listed": int(listed.days) + 1 if pd.notna(listed) else None,
        "similar": max(0, len(same_level) - 1),
    }


# ---- parts of a whole and activity ---------------------------------------------------------------
ACTIVITY_STEPS = (1, 3, 5, 10)  # answers a day that start the levels 1, 2, 3 and 4 of the grid
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд")


def latest_shares(market: pd.DataFrame, by: str, *, top: int = 4) -> pd.DataFrame:
    """Open vacancies on the latest day split by ``by``: ``label``, ``value``, ``share``.

    The ``top`` biggest stay as they are and the rest are folded into "Інші", so a ring never has
    more than ``top`` + 1 parts.
    """
    if market.empty:
        return pd.DataFrame(columns=["label", "value", "share"])
    latest = market[market["date"] == market["date"].max()]
    named = latest.assign(**{by: latest[by].replace({NO_LEVEL: "не вказано"})})
    counts = named.groupby(by)["open_vacancies"].sum().sort_values(ascending=False)
    keep = counts.head(top)
    rest = int(counts.iloc[top:].sum())
    rows = [{"label": str(name), "value": int(n)} for name, n in keep.items()]
    if rest:
        rows.append({"label": OTHER, "value": rest})
    frame = pd.DataFrame(rows)
    frame["share"] = frame["value"] / frame["value"].sum()
    return frame


def activity_grid(activity: dict[str, int], today: Any, *, weeks: int = 20) -> pd.DataFrame:
    """A GitHub-style grid of the last ``weeks`` weeks: one row per day, the newest day is today.

    Columns: ``date``, ``week`` (0 is the oldest), ``weekday`` (0 is Monday), ``count`` and
    ``level`` (0 for no answers, 1-4 by ``ACTIVITY_STEPS``).
    """
    end = pd.Timestamp(today).normalize()
    start = end - pd.Timedelta(days=end.weekday()) - pd.Timedelta(weeks=weeks - 1)
    days = pd.date_range(start, end, freq="D")
    counts = [int(activity.get(day.date().isoformat(), 0)) for day in days]
    levels = [sum(1 for step in ACTIVITY_STEPS if n >= step) for n in counts]
    return pd.DataFrame(
        {
            "date": [day.date() for day in days],
            "week": [(day - start).days // 7 for day in days],
            "weekday": [day.weekday() for day in days],
            "count": counts,
            "level": levels,
        }
    )
