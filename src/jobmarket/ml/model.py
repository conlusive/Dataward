"""CatBoost with three quantiles at once (p10, p50, p90): a range, not a single number."""

from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool

from jobmarket.ml.data import CATEGORICAL, FEATURES, QUANTILES, TARGET, WEIGHT

LOSS = "MultiQuantile:alpha=" + ",".join(str(q) for q in QUANTILES)


def to_pool(frame: pd.DataFrame, *, with_target: bool) -> Pool:
    features = frame[FEATURES].copy()
    for column in CATEGORICAL:
        features[column] = features[column].astype(str)
    return Pool(
        features,
        label=frame[TARGET].to_numpy() if with_target else None,
        weight=frame[WEIGHT].to_numpy() if with_target else None,
        cat_features=CATEGORICAL,
    )


def fit_model(
    train: pd.DataFrame,
    *,
    iterations: int = 600,
    depth: int = 6,
    learning_rate: float = 0.1,
    seed: int = 42,
) -> CatBoostRegressor:
    model = CatBoostRegressor(
        loss_function=LOSS,
        iterations=iterations,
        depth=depth,
        learning_rate=learning_rate,
        random_seed=seed,
        verbose=0,
        allow_writing_files=False,
    )
    model.fit(to_pool(train, with_target=True))
    return model


def predict_quantiles(model: CatBoostRegressor, frame: pd.DataFrame) -> np.ndarray:
    """Columns p10, p50, p90. The three outputs are trained separately and can cross, so they are
    sorted per row: the interval is never inverted."""
    raw = np.asarray(model.predict(to_pool(frame, with_target=False)), dtype=float)
    return np.sort(raw, axis=1)


def contributions(model: CatBoostRegressor, frame: pd.DataFrame) -> list[dict[str, Any]]:
    """For each row, how much each feature moved the median prediction from the average (USD)."""
    shap = np.asarray(
        model.get_feature_importance(to_pool(frame, with_target=False), type="ShapValues")
    )
    median = QUANTILES.index(0.5)
    return [
        {
            **dict(zip(FEATURES, map(float, row[median][:-1]), strict=True)),
            "base": float(row[median][-1]),
        }
        for row in shap
    ]
