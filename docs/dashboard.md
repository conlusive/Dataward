# Dashboard

A Streamlit app that reads **only the parquet files of `make export`** (and `status.json`), never the
database. The UI is in Ukrainian.

```bash
make pipeline            # or `make export` after a dbt build: writes data/export
make dashboard           # http://localhost:8501
make docker-dashboard    # the same in a container (reads ./data/export read-only)
```

Set `DASHBOARD_DATA_DIR` to read another directory, and `DBT_DOCS_URL` to show a link to the dbt docs
on the "about the data" page.

## Pages

| Page | Shows | Reads |
|---|---|---|
| Огляд ринку | open, new and closed vacancies, trend by source, categories, filters, top skills | `fct_market_daily`, `fct_skill_demand_monthly`, `dim_skill` |
| Навички | one skill: share of vacancies over time, declared salary, what it appears with, its stack | demand, `fct_skill_pairs`, `fct_salary_by_skill`, `skill_clusters` |
| Стеки | the clusters and the pair graph of one cluster (threshold slider) | pairs, `skill_clusters` |
| Зарплати | DOU survey benchmarks by role, level and year; how long vacancies stay open | `fct_salary_survey`, `fct_vacancy_lifetime` |
| Стан пайплайну | SLOs, recent runs, checks, scraping errors, volumes | `status.json` |
| Про дані | export time, rows per table, sources, limitations | `last_update.json` |

## How it is built

- `src/jobmarket/dashboard_data.py`: plain functions over DataFrames (filters, top skills, trends,
  related skills, the stack graph, benchmarks). No Streamlit, so they are tested directly.
- `src/jobmarket/dashboard_ui.py`: cached loading (`st.cache_data`, 5 minutes) and one place that turns
  a missing file or column into a message instead of a stack trace.
- `dashboard/app.py` and `dashboard/views/*.py`: navigation and one script per page.
- `REQUIRED` in `dashboard_data.py` lists the columns each table must have; a test keeps it inside the
  dbt contracts, so the producer cannot rename a column the dashboard reads without a failing test.

The dependencies (Streamlit, pandas) are the optional `dashboard` group, so the pipeline image does not
carry them. `Dockerfile.dashboard` installs only that group, without dbt or dev tools.

## Tests

`tests/test_dashboard_data.py` checks the functions on a small made-up export whose answers are worked
out by hand. `tests/test_dashboard_app.py` runs every page headlessly (Streamlit's `AppTest`) on it and
checks the numbers shown, the filters, the empty states and a missing data directory. They are skipped
when Streamlit is not installed (`uv sync --group dashboard`); CI installs it. Every page was also run on
a real export: each rendered in about a second or less.

## Not here yet

- **Hosting.** Streamlit Community Cloud and the Hugging Face mirror need accounts. The data must reach
  the app (the `data` branch or object storage); until then it runs locally or in the container.
- **Salary calculator model** and **typical vacancies per skill**: see ADR 0033.
- **English UI**: only Ukrainian for now.
