"""Train the salary model, compare it with the baseline and production, and promote if it earns it.

Judged on the last survey year, which the model never saw. A model is promoted only if it beats the
baseline and is not worse than the production model *on the same test rows* (the production model is
re-evaluated on them, so a test set that grew does not make the comparison unfair).
"""

import contextlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd

from jobmarket.ml import registry
from jobmarket.ml.baseline import fit_baseline
from jobmarket.ml.data import FEATURES, TARGET, WEIGHT, load_features, split_by_year
from jobmarket.ml.metrics import evaluate
from jobmarket.ml.model import fit_model, predict_quantiles


@dataclass(frozen=True)
class TrainResult:
    run_id: str
    version: int
    promoted: bool
    reason: str
    test_year: int
    rows_train: int
    rows_test: int
    model: dict[str, float]
    baseline: dict[str, float]
    production: dict[str, float] | None = None
    importance: dict[str, float] = field(default_factory=dict)


def _score(predicted: np.ndarray, test: pd.DataFrame) -> dict[str, float]:
    return evaluate(test[TARGET].to_numpy(), predicted, test[WEIGHT].to_numpy())


def train_salary_model(
    features_path: Path,
    *,
    tracking_uri: str | None = None,
    artifact_dir: Path = registry.ARTIFACT_DIR,
    iterations: int = 600,
    seed: int = 42,
    test_year: int | None = None,
) -> TrainResult:
    frame = load_features(features_path)
    train, test, year = split_by_year(frame, test_year)

    baseline = _score(fit_baseline(train).predict(test), test)
    model = fit_model(train, iterations=iterations, seed=seed)
    scores = _score(predict_quantiles(model, test), test)
    importance = dict(zip(FEATURES, map(float, model.get_feature_importance()), strict=True))

    client = registry.connect(tracking_uri, artifact_dir)
    current = registry.production_run_id(client)
    production_scores: dict[str, float] | None = None
    if current is not None:
        production = registry.load_model(client, current[0])
        production_scores = _score(predict_quantiles(production, test), test)

    promote, reason = _decide(scores, baseline, production_scores)

    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "iterations": iterations,
                "seed": seed,
                "test_year": year,
                "rows_train": len(train),
                "rows_test": len(test),
                "loss": "MultiQuantile",
            }
        )
        mlflow.log_metrics({**scores, **{f"baseline_{k}": v for k, v in baseline.items()}})
        with tempfile.TemporaryDirectory() as folder:
            model.save_model(str(Path(folder) / registry.MODEL_FILE))
            report: dict[str, Any] = {
                "test_year": year, "model": scores, "baseline": baseline,
                "production": production_scores, "importance": importance,
                "promoted": promote, "reason": reason,
            }  # fmt: skip
            (Path(folder) / "report.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            mlflow.log_artifacts(folder)
        run_id = run.info.run_id

    _ensure_registered(client)
    version = client.create_model_version(
        registry.MODEL_NAME, source=f"runs:/{run_id}/", run_id=run_id
    )
    if promote:
        client.set_registered_model_alias(registry.MODEL_NAME, registry.ALIAS, version.version)
    return TrainResult(
        run_id=run_id, version=int(version.version), promoted=promote, reason=reason,
        test_year=year, rows_train=len(train), rows_test=len(test), model=scores,
        baseline=baseline, production=production_scores, importance=importance,
    )  # fmt: skip


def _ensure_registered(client: mlflow.MlflowClient) -> None:
    with contextlib.suppress(mlflow.exceptions.MlflowException):  # already registered
        client.create_registered_model(registry.MODEL_NAME)


def _decide(
    scores: dict[str, float], baseline: dict[str, float], production: dict[str, float] | None
) -> tuple[bool, str]:
    if scores["mae"] >= baseline["mae"]:
        return False, (
            f"not promoted: MAE {scores['mae']:.0f} is not better than the baseline's "
            f"{baseline['mae']:.0f}"
        )
    if production is None:
        return True, "promoted: no production model yet and it beats the baseline"
    if scores["mae"] <= production["mae"]:
        return True, (
            f"promoted: MAE {scores['mae']:.0f} is not worse than production's "
            f"{production['mae']:.0f}"
        )
    return False, (
        f"not promoted: MAE {scores['mae']:.0f} is worse than production's {production['mae']:.0f}"
    )
