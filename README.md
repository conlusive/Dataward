# jobmarket

Reproducible, observable data pipeline for the Ukrainian IT job market:
daily scraping into an immutable bronze layer, silver cleaning/dedup/SCD2, gold marts in dbt.

Status: phase 1 (ingestion into bronze). The full plan lives in the Obsidian vault.

## Quick start

```bash
make install
make lint
make test
make scrape RUN_DATE=2026-11-06        # NBU + jobs.dou.ua + djinni.co into data/bronze
```

Single source or a smoke run:

```bash
uv run jobmarket scrape dou --run-date 2026-11-06 --max-pages 1
uv run jobmarket scrape dou_salaries   # DOU salary surveys, manual (published twice a year)
```

Re-running a date is safe: pages already in bronze for that date are not downloaded again
(`--refetch` forces it), and every run is recorded as a new attempt in `ops_scrape_runs`
(`data/jobmarket.duckdb`).

## Silver

```bash
uv run jobmarket parse all --run-date 2026-11-06   # bronze -> silver_vacancies (DuckDB)
```

Parses vacancy pages of one date into `silver_vacancies` (upsert by id; a backfill of an older date
never overwrites newer data). Pages that no longer match the parser are counted as failed in
`ops_task_runs` instead of stopping the run.

Salaries are recomputed on every `parse`: `salary_min/max/currency` from the declared range or the
description, then `salary_usd_min/max` from the NBU rate on the publication date. `parse` reads only
bronze; if a rate for some date is missing it logs the dates, and

```bash
uv run jobmarket fetch-rates   # downloads the missing NBU rates into bronze
```

fetches them (run `parse` again afterwards).

## Exploring the data

`notebooks/01_eda_bronze.ipynb` summarises what is in `data/bronze`: volumes, statuses, distinct
vacancies and salary coverage. Re-run it after more days accumulate.

## Automation

- `ci.yml`: ruff, mypy, pytest on every PR and push to `main`.
- `pipeline-daily.yml`: scrape at 04:00 UTC (also manually, with `run_date` and `max_pages`).
  Bronze is kept in a rolling GitHub Actions cache for now; this is interim storage and not
  durable. Object storage (R2/S3) replaces it later.

## Scraping etiquette

`robots.txt` is honoured, at most 1-2 requests per second, honest User-Agent, no logins.
work.ua is not scraped: it blocks automated clients with a Cloudflare challenge.
Raw HTML is not published; `data/bronze_sample/` holds a few pages for tests only.
