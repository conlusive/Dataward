# Salary model

One model with a small, honest job: show that the gold layer is a good base for ML, and give the
dashboard a salary calculator. It is not a claim about how good a salary predictor can be.

## What it is

- **Data:** the DOU survey answers with a salary (`ml_features_salary`, about 289,000 rows, 2010-2026).
  One dbt model defines the features, so training and prediction read the same thing: role, level,
  years of experience, English, company size and type, city group, survey year.
- **Model:** CatBoost with a three-quantile loss (p10, p50, p90), so the answer is a range, weighted by
  the number of respondents each row stands for. The three outputs are sorted per row, so an interval
  is never inverted.
- **Baseline:** the weighted p10/p50/p90 by role and experience bucket, falling back to the role and
  then to everyone when a group has fewer than 30 answers.
- **Validation in time:** trained on the years before the last one, tested on the last year, which the
  model has never seen. A random split would let the model learn the same wave it is tested on.
- **Metrics:** MAE of the median in USD, the share of real salaries inside p10-p90, the width of the
  interval. The latest run is in [ml_report.md](ml_report.md).

## Why the survey and not the vacancies

The plan trained on vacancies with a salary range. There are only a few hundred of them, from a few days
of scraping, so a time split is impossible and the number is too small to learn from. The survey has
more than 200,000 rows over 15 years. When the vacancy history is long enough (months), a second model on
vacancies can be compared with this one; the plan listed the survey model as an optional extra, but it is
the only one that can be judged honestly today.

## Running it

```bash
uv sync --group ml                    # CatBoost, MLflow (optional group, not in the pipeline image)
make export                           # the survey rows must be in data/export
make train                            # train, compare, maybe promote, write the dashboard grid + docs/ml_report.md
uv run --group ml jobmarket predict-salary --role qa --seniority senior --experience 6 --english upper-intermediate
```

`predict-salary` prints the range and how much each feature moved the median (CatBoost's SHAP values).

## MLflow and promotion

Parameters, metrics, the model file and a report are logged to MLflow on a local SQLite database
(`data/mlflow/`, MLflow's file store is deprecated). The registered model `salary-model` has the alias
`production`.

A new model is **promoted only if**

1. its MAE is better than the baseline's, and
2. its MAE is not worse than the production model's **on the same test rows** (the production model is
   evaluated again on them, so a test set that grew does not make the comparison unfair).

A model that is not promoted is still registered as a version and logged, so it can be looked at.

## The dashboard

The dashboard does not load CatBoost. `make train` also writes `salary_model_grid.parquet` (the model's
range for every realistic role and level, experience, English and city group: about 5,000 profiles) and
`salary_model.json` (version, test year, metrics) next to the other exports; the page looks the profile
up. Without them the page says the model has not been trained.

## Limits, said plainly

- A survey is self-reported, by people who answer surveys. It shows what people earn, not what an
  employer will offer a new hire.
- Correlation, not causation: English level or company type predict a salary, they do not cause it.
- Judged on one test year. If the market moves much between years, the error grows.
- Salaries are nominal USD per month, net; the survey year is a feature, so the model learns the trend
  but a tree cannot extrapolate beyond the last year it saw.
- The first real run: the model's MAE is about 11% lower than the baseline's, and the p10-p90 range held
  the real salary in about 80% of cases. That is better than the baseline, not a precise predictor.

## Not here

- A monthly retraining workflow: the registry lives on the machine that trains, so there is nowhere yet
  to keep it between runs (it needs object storage or a hosted MLflow). Training is a manual command.
- A model on vacancy salaries (see above) and a "what to learn next" recommender.
