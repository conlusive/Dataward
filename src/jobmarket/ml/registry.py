"""MLflow tracking and the model registry on a local SQLite database (the file store is deprecated).

The model named `salary-model` has an alias `production`: the version the dashboard's grid is built
from. A new version gets that alias only when it is not worse than the current one (see train.py).
"""

import logging
import os
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")  # a hint for coding agents, noise in a log

import mlflow  # noqa: E402
from catboost import CatBoostRegressor  # noqa: E402
from mlflow import MlflowClient  # noqa: E402

logging.getLogger("mlflow").setLevel(logging.WARNING)

MODEL_NAME = "salary-model"
ALIAS = "production"
EXPERIMENT = "salary"
MODEL_FILE = "model.cbm"
DEFAULT_URI = "sqlite:///data/mlflow/mlflow.db"
ARTIFACT_DIR = Path("data/mlflow/artifacts")


def tracking_uri() -> str:
    return os.environ.get("MLFLOW_TRACKING_URI") or DEFAULT_URI


def connect(uri: str | None = None, artifact_dir: Path = ARTIFACT_DIR) -> MlflowClient:
    """Point MLflow at ``uri`` (a SQLite file is created if missing) and make sure the experiment
    exists with its artifacts under ``artifact_dir``."""
    uri = uri or tracking_uri()
    if uri.startswith("sqlite:///"):
        Path(uri.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(uri)
    client = MlflowClient(tracking_uri=uri)
    if client.get_experiment_by_name(EXPERIMENT) is None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        client.create_experiment(EXPERIMENT, artifact_location=artifact_dir.resolve().as_uri())
    mlflow.set_experiment(EXPERIMENT)
    return client


def production_run_id(client: MlflowClient) -> tuple[str, int] | None:
    """(run id, version) of the production model, or None when nothing is promoted yet."""
    try:
        version = client.get_model_version_by_alias(MODEL_NAME, ALIAS)
    except mlflow.exceptions.MlflowException:
        return None
    return str(version.run_id), int(version.version)


def load_model(client: MlflowClient, run_id: str) -> CatBoostRegressor:
    local = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path=MODEL_FILE)
    model = CatBoostRegressor()
    model.load_model(local)
    return model
