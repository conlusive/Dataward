import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("catboost")
pytest.importorskip("mlflow")

from jobmarket import cli  # noqa: E402
from jobmarket import dashboard_data as dd  # noqa: E402
from jobmarket.ml import registry  # noqa: E402
from jobmarket.ml.baseline import MIN_GROUP, fit_baseline, weighted_quantiles  # noqa: E402
from jobmarket.ml.data import experience_bucket, split_by_year  # noqa: E402
from jobmarket.ml.metrics import evaluate  # noqa: E402
from jobmarket.ml.model import (  # noqa: E402
    contributions,
    fit_model,
    predict_quantiles,
    to_pool,
)
from jobmarket.ml.predict import (  # noqa: E402
    MIN_PAIR_ANSWERS,
    ModelError,
    build_grid,
    load_production,
    predict_profile,
    write_grid,
)
from jobmarket.ml.train import _decide, train_salary_model  # noqa: E402


def synthetic(
    rows_per_year: int = 300, years: tuple[int, ...] = (2019, 2020, 2021, 2022)
) -> pd.DataFrame:
    """Salaries that grow with experience, role and year, plus noise: a learnable structure."""
    rng = np.random.default_rng(7)
    frames = []
    for year in years:
        role = rng.choice(["qa", "dev"], rows_per_year)
        experience = rng.uniform(0, 10, rows_per_year)
        salary = 600 + 250 * experience + np.where(role == "dev", 700, 0) + 150 * (year - 2019)
        frames.append(
            pd.DataFrame(
                {
                    "survey_year": year,
                    "role": role,
                    "seniority": np.where(experience > 5, "senior", "middle"),
                    "experience_years": experience,
                    "english": rng.choice(["intermediate", "upper-intermediate"], rows_per_year),
                    "company_size": "unknown",
                    "company_type": "unknown",
                    "city_group": rng.choice(["ukraine", "abroad"], rows_per_year),
                    "salary_usd": salary + rng.normal(0, 150, rows_per_year),
                    "weight": 1.0,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


@pytest.fixture(scope="module")
def features_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("ml") / "ml_features_salary.parquet"
    frame = synthetic()
    # a (role, level) pair that is too rare to be in the grid
    rare = frame.head(5).assign(role="rare", seniority="intern")
    pd.concat([frame, rare]).to_parquet(path)
    return path


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory, features_file: Path):  # type: ignore[no-untyped-def]
    root = tmp_path_factory.mktemp("registry")
    uri, artifacts = f"sqlite:///{root / 'mlflow.db'}", root / "artifacts"
    result = train_salary_model(
        features_file, tracking_uri=uri, artifact_dir=artifacts, iterations=80
    )
    return result, uri, artifacts


# ---- features and the split ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("years", "bucket"),
    [(None, "unknown"), (float("nan"), "unknown"), (-1.0, "unknown"), (0.0, "0"), (2.5, "2"),
     (3.0, "3-4"), (4.9, "3-4"), (6.0, "5-6"), (9.9, "7-9"), (12.0, "10-14"), (15.0, "15+"),
     (30.0, "15+")],
)  # fmt: skip
def test_experience_is_bucketed(years: float | None, bucket: str) -> None:
    assert experience_bucket(years) == bucket


def test_the_last_year_is_the_test_set_and_the_earlier_years_train() -> None:
    train, test, year = split_by_year(synthetic())

    assert year == 2022 and set(train["survey_year"]) == {2019, 2020, 2021}
    assert set(test["survey_year"]) == {2022}


def test_a_split_without_earlier_years_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot split"):
        split_by_year(synthetic(years=(2022,)))


# ---- the baseline ----------------------------------------------------------------------------
def test_weighted_quantiles_are_the_lowest_value_reaching_the_share() -> None:
    assert weighted_quantiles(np.array([1.0, 2.0, 3.0, 4.0]), np.ones(4), (0.25, 0.5, 1.0)) == [
        1.0,
        2.0,
        4.0,
    ]
    heavy = weighted_quantiles(np.array([1000.0, 5000.0]), np.array([9.0, 1.0]), (0.5, 0.95))
    assert heavy == [1000.0, 5000.0]  # nine of ten respondents earn 1000


def _group(role: str, years: float, salary: float, n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "role": [role] * n,
            "experience_years": [years] * n,
            "salary_usd": [salary] * n,
            "weight": [1.0] * n,
        }
    )


def test_the_baseline_falls_back_from_the_group_to_the_role_to_everyone() -> None:
    train = pd.concat(
        [
            _group("qa", 0.5, 1000.0, MIN_GROUP + 10),
            _group("qa", 8.0, 2000.0, 5),
            _group("dev", 3.0, 3000.0, MIN_GROUP),
        ]
    )
    baseline = fit_baseline(train)

    def p50(role: str, years: float) -> float:
        frame = pd.DataFrame({"role": [role], "experience_years": [years]})
        return float(baseline.predict(frame)[0, 1])

    assert p50("qa", 0.2) == 1000.0  # its own group
    assert p50("qa", 8.0) == 1000.0  # (qa, 7-9) has only 5 answers: the qa median
    assert p50("dev", 3.5) == 3000.0
    assert p50("designer", 2.0) == 1000.0  # unknown role: everyone (qa makes up most of the rows)


# ---- the metrics -----------------------------------------------------------------------------
def test_mae_and_interval_coverage_are_weighted_by_respondents() -> None:
    y = np.array([100.0, 200.0, 400.0])
    predicted = np.array([[50.0, 90.0, 150.0], [150.0, 210.0, 250.0], [100.0, 300.0, 350.0]])
    weights = np.array([1.0, 1.0, 2.0])

    scores = evaluate(y, predicted, weights)

    assert scores["mae"] == pytest.approx((10 + 10 + 2 * 100) / 4)
    assert scores["coverage_10_90"] == pytest.approx(
        2 / 4
    )  # the first two are inside, the third is not
    assert scores["interval_width"] == pytest.approx((100 + 100 + 2 * 250) / 4)


# ---- the model -------------------------------------------------------------------------------
def test_quantiles_are_never_inverted_and_grow_with_experience() -> None:
    train, test, _ = split_by_year(synthetic())
    model = fit_model(train, iterations=80)

    predicted = predict_quantiles(model, test)

    assert (predicted[:, 0] <= predicted[:, 1]).all() and (predicted[:, 1] <= predicted[:, 2]).all()
    junior = test.assign(experience_years=1.0)
    senior = test.assign(experience_years=9.0)
    assert (
        predict_quantiles(model, senior)[:, 1].mean()
        > predict_quantiles(model, junior)[:, 1].mean() + 1000
    )


def test_the_model_beats_the_baseline_on_the_year_it_did_not_see(trained) -> None:  # type: ignore[no-untyped-def]
    result, _, _ = trained

    assert result.model["mae"] < result.baseline["mae"]
    assert result.test_year == 2022 and result.rows_test == 300


def test_contributions_add_up_to_the_median_prediction() -> None:
    train, test, _ = split_by_year(synthetic())
    model = fit_model(train, iterations=40)
    row = test.head(1)

    shap = contributions(model, row)[0]
    median = float(model.predict(to_pool(row, with_target=False))[0][1])

    assert sum(shap.values()) == pytest.approx(median, rel=1e-6, abs=1e-3)


# ---- promotion -------------------------------------------------------------------------------
BASELINE = {"mae": 1000.0}


@pytest.mark.parametrize(
    ("mae", "production", "promoted"),
    [
        (1100.0, None, False),  # worse than the baseline: never, even with nothing in production
        (1000.0, None, False),  # equal to the baseline is not "beats"
        (900.0, None, True),  # nothing in production and it beats the baseline
        (900.0, 900.0, True),  # not worse than production
        (900.0, 800.0, False),  # worse than production
        (900.0, 950.0, True),  # better than production
    ],
)
def test_promotion_needs_to_beat_the_baseline_and_not_lose_to_production(
    mae: float, production: float | None, promoted: bool
) -> None:
    decision, reason = _decide(
        {"mae": mae}, BASELINE, None if production is None else {"mae": production}
    )

    assert decision is promoted and reason.startswith("promoted" if promoted else "not promoted")


def test_the_first_good_model_becomes_production(trained) -> None:  # type: ignore[no-untyped-def]
    result, uri, artifacts = trained

    client = registry.connect(uri, artifacts)

    assert result.promoted and registry.production_run_id(client) == (result.run_id, 1)


def test_a_worse_model_is_recorded_but_does_not_replace_production(  # type: ignore[no-untyped-def]
    trained, features_file: Path
) -> None:
    first, uri, artifacts = trained

    worse = train_salary_model(
        features_file, tracking_uri=uri, artifact_dir=artifacts, iterations=1
    )

    client = registry.connect(uri, artifacts)
    assert not worse.promoted and worse.version == first.version + 1
    assert worse.production is not None and worse.model["mae"] > worse.production["mae"]
    assert registry.production_run_id(client) == (first.run_id, first.version)


# ---- predictions and the grid ----------------------------------------------------------------
def test_without_a_production_model_prediction_says_to_train(tmp_path: Path) -> None:
    with pytest.raises(ModelError, match="make train"):
        load_production(f"sqlite:///{tmp_path / 'empty.db'}", tmp_path / "artifacts")


def test_a_profile_gets_an_ordered_range_and_an_explanation(trained) -> None:  # type: ignore[no-untyped-def]
    _, uri, artifacts = trained
    production = load_production(uri, artifacts)

    senior = predict_profile(
        production, {"role": "dev", "seniority": "senior", "experience_years": 9.0}, 2022
    )
    junior = predict_profile(
        production, {"role": "dev", "seniority": "middle", "experience_years": 1.0}, 2022
    )

    assert senior["p10"] <= senior["p50"] <= senior["p90"]
    assert senior["p50"] > junior["p50"]
    assert {"role", "experience_years", "base"} <= set(senior["contributions"])


def test_the_grid_covers_only_realistic_role_and_level_pairs(trained, features_file: Path) -> None:  # type: ignore[no-untyped-def]
    _, uri, artifacts = trained
    production = load_production(uri, artifacts)
    features = pd.read_parquet(features_file)

    grid = build_grid(production, features)

    assert "rare" not in set(grid["role"])  # 5 answers < MIN_PAIR_ANSWERS
    assert set(zip(grid["role"], grid["seniority"], strict=True)) == {
        ("qa", "middle"), ("qa", "senior"), ("dev", "middle"), ("dev", "senior"),
    }  # fmt: skip
    assert len(grid) == 4 * 8 * 2 * 2 and MIN_PAIR_ANSWERS == 30
    assert set(grid.columns) == dd.GRID_COLUMNS  # what the dashboard reads is what is written
    assert (grid["salary_p10"] <= grid["salary_p90"]).all() and set(grid["survey_year"]) == {2022}


def test_the_grid_and_its_description_are_written_for_the_dashboard(  # type: ignore[no-untyped-def]
    trained, features_file: Path, tmp_path: Path
) -> None:
    result, uri, artifacts = trained
    production = load_production(uri, artifacts)

    rows = write_grid(production, features_file, tmp_path / "out")

    info = json.loads((tmp_path / "out" / "salary_model.json").read_text())
    assert rows == len(pd.read_parquet(tmp_path / "out" / "salary_model_grid.parquet"))
    assert info["version"] == production.version and info["tested_on_year"] == 2022
    assert info["model"]["mae"] == pytest.approx(result.model["mae"])
    assert info["model"]["mae"] < info["baseline"]["mae"]


# ---- the commands ----------------------------------------------------------------------------
def test_commands_without_the_exported_features_say_what_to_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert cli.main(["train-salary"]) == 1
    assert cli.main(["salary-grid"]) == 1


def test_prediction_without_a_model_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'none.db'}")

    assert cli.main(["predict-salary", "--role", "qa"]) == 1
