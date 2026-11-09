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

`parse` also reads three signals from the text: `seniority` (from the title only), the required
`experience_years_text` and the `english_level` (from the description). They are kept next to the
page's own `experience_years` (Djinni JSON-LD) instead of replacing it. Gold cases live in
`data/gold/vacancy_text_cases.yaml`.

Skills are found by a dictionary over `src/jobmarket/skills/taxonomy.yaml` (~490 skills, ~2000
spellings). Ambiguous words ("Go", "R", "Spring", "Swift") count only with the exact case and a
context word nearby; skills under "nice to have" headings are marked `nice`, benefit sections are
ignored. Add a skill by appending a line; `make test` validates the file. Results go to
`silver_vacancy_skills` (`method = dictionary`).

Duplicates are found across both sites: inside one company, two vacancies are the same posting when
the titles are almost equal and the text is the same or very similar, or when the text is
near-identical and the levels do not conflict ("Senior X" and "X" merge, "Middle X" and "Senior X" do
not). Every vacancy gets a `dedup_group_id` (the oldest member's id) and `silver_vacancy_groups` says
which member supplies the text (DOU first) and which the salary (Djinni first).

`make parse` runs the whole silver step for every stored day that has no finished parse yet (it is
the catch-up used by the daily workflow), then fetches missing exchange rates and parses again.
Each day's listing pages are also stored as `silver_vacancy_sightings` (who was listed when). dbt
(`warehouse/`, DuckDB) turns them into `fct_vacancy_daily` (a vacancy is `new`, then `active`, and
`closed` after two days off the listing; first-day vacancies are flagged `left_censored`) and keeps an
SCD2 history of title/salary/description changes:

```bash
make dbt-build    # dbt snapshot + dbt build (models and tests)
```

## Running it

```bash
make pipeline          # the whole daily flow: scrape, parse, checks, dbt, checks, export
make docker-pipeline   # the same in a container, data in ./data
```

Each step has a timeout, the scrape steps retry, a failed step skips the steps that depend on it, and
every attempt is recorded in `ops_task_runs`. See [docs/orchestration.md](docs/orchestration.md).

## Observability

```bash
uv run jobmarket status    # SLOs, recent runs and the checks that need attention
```

SLOs: data at most 36 h old, at least 95% of runs in 30 days succeed, under 10% of vacancies without
a skill. Every run is a row in `ops_pipeline_runs`, a Telegram summary is sent when the bot is
configured, and `status.json` is written next to the parquet export. See
[docs/observability.md](docs/observability.md) and [docs/postmortems](docs/postmortems).

## Reliability

A run for a date can be repeated and gives the same data (`tests/test_idempotency.py` compares hashes
of every silver table and mart after two runs). Backfill and the data-quality checks:

```bash
make backfill FROM=2026-11-01 TO=2026-11-30   # re-parse stored days (no network), rebuild gold
make dq                                       # 13 checks; exit 1 on an error, a warning only reports
```

`dq` runs in the daily workflow before the export, so bad data stops there and the consumers keep the
last good files. Results go to `ops_dq_results`. Silver tables have contracts in `contracts/silver.yml`
that a test keeps in step with the code. Details: [docs/idempotency_and_backfill.md](docs/idempotency_and_backfill.md).

## Gold

dbt also builds the marts: skill demand per month, which skills appear together (lift, PMI, NPMI),
salary percentiles per skill and from the DOU survey, and how long vacancies stay open. A real
vacancy listed on both DOU and Djinni counts once, and a skill counts for its parents (Django for
Python). Marts do not publish samples that are too small (`warehouse/dbt_project.yml`, `vars`), and
their column types are enforced contracts.

```bash
uv run jobmarket make-seeds   # position/city vocabularies for the survey -> warehouse/seeds
make export                   # marts -> data/export/*.parquet + last_update.json (checked against the contracts)
```

`export` also writes `skill_clusters.parquet` (Louvain communities of the pair graph). The daily
workflow keeps the export as the `gold-export` artifact. The manual `dbt-docs` workflow publishes the
model documentation once GitHub Pages is switched on (Settings -> Pages -> Source: GitHub Actions).

Method B asks an LLM for the skills (needs a key, never part of CI):

```bash
uv run jobmarket extract-skills all --dry-run          # counts requests and estimates the cost, no key
OPENAI_API_KEY=... uv run jobmarket extract-skills all --max-cost-usd 2
uv run jobmarket skills-review                         # most frequent skills the taxonomy lacks
uv run jobmarket skills-renormalize                    # re-map stored answers after editing the taxonomy
```

`LLM_MODEL` picks the provider: a plain name is OpenAI, `gemini/...` uses `GEMINI_API_KEY`,
`ollama/...` uses `OLLAMA_BASE_URL`. Answers are cached by title, text hash, prompt and model, so a
repeat run costs nothing; prices live in `src/jobmarket/skills/llm_prices.yaml` (edit when they change).

The skill gold set (the hand-labelled truth that precision/recall are measured against):

```bash
uv run jobmarket gold-sample --n 150     # data/gold/_label_sheet.md, blind (no suggestions)
# open the sheet, list the skill ids each vacancy asks for under "Labels:" (ids: data/gold/_skill_ids.md)
uv run jobmarket gold-import             # checks the ids, writes data/gold/skills_gold.yaml
uv run jobmarket gold-eval               # precision / recall / F1 per method -> docs/metrics.md
```

The sheet and the vacancy texts stay local (gitignored); only the labels are committed. After the
first `gold-eval`, put `regression_min_f1: <value>` in `skills_gold.yaml` and CI-style regression
checks of the dictionary method start working (`tests/test_gold_regression.py`).

DOU salary surveys (34 waves since 2010) are loaded separately:

```bash
uv run jobmarket scrape dou_salaries   # CSVs into bronze, a few times a year
uv run jobmarket parse-surveys         # bronze -> silver_dou_salaries (~300k answers, ~7 s)
```

`src/jobmarket/silver/dou_salaries_columns.yaml` maps each wave's columns to one schema; a file
whose columns changed fails alone and is reported, the other waves still load. Reloading replaces a
file's rows atomically. Cross-tab subtotal rows (2022) are skipped so no respondent is counted twice.

## Exploring the data

`notebooks/01_eda_bronze.ipynb` summarises what is in `data/bronze`: volumes, statuses, distinct
vacancies and salary coverage. Re-run it after more days accumulate.

## Automation

- `ci.yml`: ruff, mypy, pytest on every PR and push to `main`.
- `docs.yml`: manual; builds the dbt docs site for GitHub Pages.
- `pipeline-daily.yml`: scrape at 04:00 UTC (also manually, with `run_date` and `max_pages`).
  Bronze is kept in a rolling GitHub Actions cache for now; this is interim storage and not
  durable. Object storage (R2/S3) replaces it later.

## Scraping etiquette

`robots.txt` is honoured, at most 1-2 requests per second, honest User-Agent, no logins.
work.ua is not scraped: it blocks automated clients with a Cloudflare challenge.
Raw HTML is not published; `data/bronze_sample/` holds a few pages for tests only.
