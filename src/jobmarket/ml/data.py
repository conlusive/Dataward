"""The features of the salary model and how the rows are split in time.

Training and prediction read the same exported table (`ml_features_salary.parquet`), whose columns
come from one dbt model, so the two cannot disagree about what a feature means.
"""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

FEATURES_FILE = "ml_features_salary.parquet"
TARGET = "salary_usd"
WEIGHT = "weight"
CATEGORICAL = ["role", "seniority", "english", "company_size", "company_type", "city_group"]
NUMERIC = ["experience_years", "survey_year"]
FEATURES = CATEGORICAL + NUMERIC
QUANTILES = (0.1, 0.5, 0.9)
# Experience is also bucketed for the baseline: a median for "qa, 3-4 years".
EXPERIENCE_EDGES = (0, 1, 2, 3, 5, 7, 10, 15)


def load_features(path: Path) -> pd.DataFrame:
    frame: pd.DataFrame = (
        duckdb.connect().execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
    )
    missing = set(FEATURES + [TARGET, WEIGHT]) - set(frame.columns)
    if missing:
        raise ValueError(f"{path} lacks the columns {sorted(missing)}")
    return frame


def experience_bucket(years: float | None) -> str:
    """'0', '1', '2', '3-4', '5-6', '7-9', '10-14', '15+', or 'unknown'."""
    if years is None or np.isnan(years) or years < 0:
        return "unknown"
    edges = EXPERIENCE_EDGES
    for low, high in zip(edges, edges[1:], strict=False):
        if low <= years < high:
            return str(low) if high - low == 1 else f"{low}-{high - 1}"
    return f"{edges[-1]}+"


def split_by_year(
    frame: pd.DataFrame, test_year: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Train on the earlier years, test on the last one (or ``test_year``): the model is judged on
    a period it has not seen, like a real prediction, not on a random sample of the same waves."""
    year = int(frame["survey_year"].max()) if test_year is None else test_year
    train, test = frame[frame["survey_year"] < year], frame[frame["survey_year"] == year]
    if train.empty or test.empty:
        raise ValueError(f"cannot split at {year}: {len(train)} rows before it, {len(test)} in it")
    return train.reset_index(drop=True), test.reset_index(drop=True), year
