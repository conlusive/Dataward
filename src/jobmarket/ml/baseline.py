"""The baseline the model has to beat: weighted p10/p50/p90 salary by (role, experience bucket).

A group with too few answers falls back to the role, and a role with too few to everyone.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from jobmarket.ml.data import QUANTILES, TARGET, WEIGHT, experience_bucket

MIN_GROUP = 30  # answers (not weight) a group needs to have a quantile of its own


def weighted_quantiles(
    values: np.ndarray, weights: np.ndarray, quantiles: tuple[float, ...]
) -> list[float]:
    """The lowest value whose cumulative weight reaches each quantile of the total."""
    order = np.argsort(values, kind="stable")
    sorted_values, cumulative = values[order], np.cumsum(weights[order])
    total = cumulative[-1]
    return [
        float(sorted_values[np.searchsorted(cumulative, q * total, side="left")]) for q in quantiles
    ]


@dataclass(frozen=True)
class Baseline:
    by_group: dict[tuple[str, str], list[float]]
    by_role: dict[str, list[float]]
    overall: list[float]

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        rows = []
        for role, years in zip(frame["role"], frame["experience_years"], strict=True):
            key = (role, experience_bucket(years))
            rows.append(self.by_group.get(key) or self.by_role.get(role) or self.overall)
        return np.array(rows, dtype=float)


def fit_baseline(train: pd.DataFrame) -> Baseline:
    prepared = train.assign(bucket=[experience_bucket(y) for y in train["experience_years"]])

    def quantiles(group: pd.DataFrame) -> list[float]:
        return weighted_quantiles(group[TARGET].to_numpy(), group[WEIGHT].to_numpy(), QUANTILES)

    by_group = {
        (str(role), str(bucket)): quantiles(group)
        for (role, bucket), group in prepared.groupby(["role", "bucket"])
        if len(group) >= MIN_GROUP
    }
    by_role = {
        str(role): quantiles(group)
        for role, group in prepared.groupby("role")
        if len(group) >= MIN_GROUP
    }
    return Baseline(by_group, by_role, quantiles(prepared))
