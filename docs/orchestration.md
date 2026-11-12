# Orchestration and running the pipeline

## The daily flow

`make pipeline` (`jobmarket flow daily [--run-date YYYY-MM-DD]`) runs these steps in order. The
commands are the Makefile targets, so "how to scrape" or "how to build gold" is defined once; the
flow (`src/jobmarket/flow.py`) adds the policy around them.

| Step | Runs | Needs | Timeout | Retries |
|---|---|---|---|---|
| `scrape` | `make scrape` | - | 150 min | 1 |
| `scrape_surveys` | `make scrape-surveys` | - | 20 min | 1 |
| `parse` | `make parse` (parse, exchange rates, enrichment, dedup, survey) | `scrape` | 40 min | - |
| `dq_silver` | silver data-quality checks | `parse` | 5 min | - |
| `dbt` | `make dbt-build` (snapshot, models, tests) | `dq_silver` | 30 min | - |
| `dq_gold` | gold checks | `dbt` | 5 min | - |
| `export` | `make export` (parquet, contracts, clusters) | `dq_gold` | 10 min | - |

- **Failure:** a failed step makes the steps that need it `skipped`; independent ones still run. A
  silver check at `error` therefore stops dbt and the export, and consumers keep the files of the
  last good run. The exit code is 1 and the summary names the failed step.
- **Retries** exist only for the scrape steps: they skip what is already in bronze, so repeating
  them is safe. Parsing and dbt are not retried, a failure there is a bug or bad data, not a blip.
- **Timeouts** kill the step's process (exit code 124). A hung step cannot hold the run.
- **Records:** every attempt is a row in `ops_task_runs` (`task = 'flow'`, `source` = step name).
- **Partial runs:** `--only dbt,dq_gold,export` runs just those steps (a need outside the choice
  counts as met), e.g. to rebuild gold after fixing a model.
- **Backfill:** `make backfill FROM=... TO=...` or `jobmarket flow backfill --from ... --to ...`
  re-parses the stored days, then runs the checks, dbt and export. No network.
- **Message:** if `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set, a short summary is sent after
  the flow. Without them nothing happens; a delivery error never fails the run and never logs the
  token.

## GitHub Actions

- `ci.yml`: ruff, mypy, pytest (including real dbt runs on made-up data); a second job builds the
  Docker image and checks that the CLI and dbt start in it.
- `pipeline-daily.yml`: 04:00 UTC, restores the bronze/silver cache, runs `make pipeline`, saves the
  Every hour (minute 17) the same workflow runs the light flow instead: `make pipeline-fresh`
  (`flow fresh`: the first listing pages again, only new vacancy pages, today parsed again, gold, export).
  Runs queue, never overlap (one bronze cache).
  cache (also after a failure), prints run metrics and keeps the parquet export as an artifact.
  Optional secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- `docs.yml`: manual, builds the dbt docs site for GitHub Pages.

## Docker

```bash
make docker-pipeline        # builds the image and runs the daily flow; data stays in ./data
docker compose run --rm pipeline jobmarket flow backfill --from 2026-11-01 --to 2026-11-30
docker compose run --rm pipeline jobmarket dq
```

The image (`Dockerfile.pipeline`) holds the code, the dbt project and the contracts, runs as a
non-root user and keeps all data in the `/app/data` volume. Settings come from environment variables
(a local env file is read if present); no secret is baked into the image. On Linux the `./data`
directory must be writable by uid 1000.

## What is not here yet (needs an account or another component)

- Bronze in object storage (`STORAGE_URI`, R2/S3): bronze still uses the local directory and the
  Actions cache. The storage code uses plain paths, so this is a separate, larger change.
- dbt `prod` profile on Postgres (Neon): the models use DuckDB functions, so a Postgres target
  needs the models ported first.
- Prefect, the monthly retraining workflow and the dashboard image: there is no consumer yet (see
  ADR 0031 for Prefect).
