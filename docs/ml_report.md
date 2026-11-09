# Salary model: last training run

Trained on the DOU survey answers of the years before 2026
(274,417 rows) and tested on 2026 (14,358 rows), a year
the model had not seen. The baseline is the median by role and years of experience.

| | Model | Baseline |
|---|---|---|
| MAE of the median (USD/month) | 1245 | 1405 |
| Share of salaries inside p10-p90 | 79% | 75% |
| Mean width of p10-p90 (USD) | 3926 | 3609 |

A good interval holds the real salary in at least 75% of cases (the interval is
meant to hold 80%; the bar is lower on purpose, because the test year is a period the model could
not learn from).

**Decision:** promoted: no production model yet and it beats the baseline.

## What the model relies on (CatBoost feature importance)

| Feature | Importance |
|---|---|
| experience_years | 29.3 |
| survey_year | 21.9 |
| seniority | 16.7 |
| role | 13.9 |
| english | 11.3 |
| company_size | 2.8 |
| company_type | 2.6 |
| city_group | 1.5 |

## How to read it

- The data is a survey: self-reported, of people who answer surveys, not job offers. It shows what
  people earn, not what employers will offer a new hire.
- Correlation, not causation: English level or company type predict a salary, they do not cause it.
- The model is judged on one year. If the market moves a lot between years, the error grows.
- Salaries are in nominal USD per month, net.
