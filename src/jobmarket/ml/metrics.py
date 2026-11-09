"""How a model is judged: the error of its median and whether the 10-90 interval is honest."""

import numpy as np

INTERVAL_TARGET = (
    0.75  # the 10-90 interval should hold the real salary in at least this share of cases
)


def evaluate(y: np.ndarray, predicted: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    """``predicted`` has columns p10, p50, p90. Everything is weighted by respondents."""
    error = np.abs(y - predicted[:, 1])
    inside = (y >= predicted[:, 0]) & (y <= predicted[:, 2])
    total = float(weights.sum())
    return {
        "mae": float((error * weights).sum() / total),
        "coverage_10_90": float((inside * weights).sum() / total),
        "interval_width": float(((predicted[:, 2] - predicted[:, 0]) * weights).sum() / total),
    }
