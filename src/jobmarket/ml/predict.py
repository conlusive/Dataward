"""Predictions from the production model: one profile, explained, and the dashboard's grid.

The dashboard never loads CatBoost: `salary_model_grid.parquet` holds the model's p10/p50/p90 for
every realistic profile, written here after each promotion, and the dashboard looks the profile up.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import duckdb
import mlflow
import pandas as pd
from catboost import CatBoostRegressor

from jobmarket.ml import registry
from jobmarket.ml.data import FEATURES, TARGET, load_features
from jobmarket.ml.model import contributions, predict_quantiles

GRID_FILE = "salary_model_grid.parquet"
INFO_FILE = "salary_model.json"
EXPERIENCE_GRID = (0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0)
MIN_PAIR_ANSWERS = 30  # a (role, level) pair needs this many answers to appear in the grid
SKIP_ENGLISH = {"none", "unknown"}


class ModelError(Exception):
    """There is no production model to predict with."""


@dataclass(frozen=True)
class ProductionModel:
    model: CatBoostRegressor
    version: int
    run_id: str
    report: dict[str, Any]


def load_production(
    tracking_uri: str | None = None, artifact_dir: Path = registry.ARTIFACT_DIR
) -> ProductionModel:
    client = registry.connect(tracking_uri, artifact_dir)
    current = registry.production_run_id(client)
    if current is None:
        raise ModelError("no production model yet: run `make train` first")
    run_id, version = current
    report_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="report.json")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    return ProductionModel(registry.load_model(client, run_id), version, run_id, report)


def predict_profile(
    production: ProductionModel, profile: dict[str, Any], survey_year: int
) -> dict[str, Any]:
    """p10/p50/p90 in USD per month and how much each feature moved the median."""
    row = {"company_size": "unknown", "company_type": "unknown", "seniority": "unknown",
           "english": "unknown", "city_group": "ukraine", "experience_years": float("nan"),
           **profile, "survey_year": survey_year}  # fmt: skip
    missing = set(FEATURES) - set(row)
    if missing:
        raise ValueError(f"missing features: {sorted(missing)}")
    frame = pd.DataFrame([row])
    p10, p50, p90 = (float(v) for v in predict_quantiles(production.model, frame)[0])
    return {
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "contributions": contributions(production.model, frame)[0],
    }


def build_grid(production: ProductionModel, features: pd.DataFrame) -> pd.DataFrame:
    """The model's range for every realistic (role, level) x experience x English x city profile."""
    pairs = (
        features.groupby(["role", "seniority"])
        .size()
        .loc[lambda counts: counts >= MIN_PAIR_ANSWERS]
        .index
    )
    english = sorted(set(features["english"]) - SKIP_ENGLISH)
    cities = sorted(set(features["city_group"]))
    year = int(features["survey_year"].max())
    rows = [
        {
            "role": role,
            "seniority": level,
            "experience_years": exp,
            "english": eng,
            "city_group": city,
            "company_size": "unknown",
            "company_type": "unknown",
            "survey_year": year,
        }  # fmt: skip
        for (role, level), exp, eng, city in product(pairs, EXPERIENCE_GRID, english, cities)
    ]
    frame = pd.DataFrame(rows)
    predicted = predict_quantiles(production.model, frame)
    frame["salary_p10"], frame["salary_p50"], frame["salary_p90"] = (
        predicted[:, 0], predicted[:, 1], predicted[:, 2],
    )  # fmt: skip
    return frame[["role", "seniority", "experience_years", "english", "city_group", "survey_year",
                  "salary_p10", "salary_p50", "salary_p90"]]  # fmt: skip


def write_grid(production: ProductionModel, features_path: Path, out_dir: Path) -> int:
    """Write the grid and `salary_model.json` (version, test year, metrics) into ``out_dir``."""
    features = load_features(features_path)
    grid = build_grid(production, features)
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.register("grid", grid)
    con.execute(f"COPY (SELECT * FROM grid) TO '{out_dir / GRID_FILE}' (FORMAT parquet)")
    report = production.report
    info = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "version": production.version,
        "run_id": production.run_id,
        "predicts_for_year": int(features["survey_year"].max()),
        "tested_on_year": report["test_year"],
        "model": report["model"],
        "baseline": report["baseline"],
        "target": TARGET,
    }
    (out_dir / INFO_FILE).write_text(
        json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return len(grid)
