"""`docs/ml_report.md`: what the last training run found, in a form a reader can check."""

from jobmarket.ml.metrics import INTERVAL_TARGET
from jobmarket.ml.train import TrainResult


def render_report(result: TrainResult) -> str:
    m, b = result.model, result.baseline
    rows = [
        ("MAE of the median (USD/month)", f"{m['mae']:.0f}", f"{b['mae']:.0f}"),
        (
            "Share of salaries inside p10-p90",
            f"{m['coverage_10_90']:.0%}",
            f"{b['coverage_10_90']:.0%}",
        ),
        ("Mean width of p10-p90 (USD)", f"{m['interval_width']:.0f}", f"{b['interval_width']:.0f}"),
    ]
    table = "\n".join(f"| {name} | {model} | {base} |" for name, model, base in rows)
    importance = "\n".join(
        f"| {name} | {value:.1f} |"
        for name, value in sorted(result.importance.items(), key=lambda kv: -kv[1])
    )
    production = ""
    if result.production is not None:
        production = (
            f"\nThe production model scored an MAE of {result.production['mae']:.0f} "
            "on the same test rows.\n"
        )
    return f"""# Salary model: last training run

Trained on the DOU survey answers of the years before {result.test_year}
({result.rows_train:,} rows) and tested on {result.test_year} ({result.rows_test:,} rows), a year
the model had not seen. The baseline is the median by role and years of experience.

| | Model | Baseline |
|---|---|---|
{table}

A good interval holds the real salary in at least {INTERVAL_TARGET:.0%} of cases (the interval is
meant to hold 80%; the bar is lower on purpose, because the test year is a period the model could
not learn from).
{production}
**Decision:** {result.reason}.

## What the model relies on (CatBoost feature importance)

| Feature | Importance |
|---|---|
{importance}

## How to read it

- The data is a survey: self-reported, of people who answer surveys, not job offers. It shows what
  people earn, not what employers will offer a new hire.
- Correlation, not causation: English level or company type predict a salary, they do not cause it.
- The model is judged on one year. If the market moves a lot between years, the error grows.
- Salaries are in nominal USD per month, net.
"""
