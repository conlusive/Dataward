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

## The hourly flow waits for the day's sweep

An hourly run reads only the first listing pages, about 900 vacancies against the usual 6 800. Before the
night's full sweep of the same UTC day has finished, publishing that would show a market that shrank to a
seventh, and the `listing_volume` quality check rightly refuses it (it failed every first hourly run of a
day). So `jobmarket flow fresh` first asks the run records whether the `daily` flow of the day succeeded
(`OpsStore.has_successful_sweep`); if not it logs why, scrapes and publishes nothing and exits 0, and the
site keeps the previous full data. A sweep that failed does not open the way either. `--force` runs it
anyway (for a local try). The workflow's "Prepare the public export" step tolerates that an hour exported
nothing; a failed flow still fails its own step.

## An external hourly trigger

GitHub runs a `schedule` when it has room: on a public repository the hourly cron (`17 * * * *`) arrives
about every four to six hours, and some runs are dropped. The workflow also takes a manual start
(`workflow_dispatch`, inputs `flow` = `daily` or `fresh`), so a small outside scheduler can start it on time.
Runs queue and never overlap (`concurrency`, one at a time; a start that arrives while a sweep runs waits
as the one pending run), so a ping that comes too often costs nothing.

Set it up once, with a free scheduler such as cron-job.org:

1. **A token.** GitHub > Settings > Developer settings > Personal access tokens > *Fine-grained tokens* >
   Generate. Repository access: *Only select repositories* > `Dataward`. Permissions > Repository
   permissions > **Actions: Read and write** (nothing else). Expiration: as long as you accept (a year);
   put the date in your calendar, an expired token only stops the pings.
2. **The job** (cron-job.org > Create cronjob):
   - URL: `https://api.github.com/repos/conlusive/Dataward/actions/workflows/pipeline-daily.yml/dispatches`
   - Schedule: every hour (for example at minute 5)
   - Request method: `POST`; Request body: `{"ref":"main","inputs":{"flow":"fresh"}}`
   - Headers: `Authorization: Bearer <the token>`, `Accept: application/vnd.github+json`,
     `X-GitHub-Api-Version: 2022-11-28`, `Content-Type: application/json`, `User-Agent: dataward-ping`
   - Success is **HTTP 204** (no body). Optionally a second job at 04:00 UTC with `"flow":"daily"`.
3. **Try it by hand first** (the token goes in the environment, not in the command line history):

   ```bash
   read -rs GH_PING_TOKEN && export GH_PING_TOKEN
   curl -si -X POST -H "Authorization: Bearer $GH_PING_TOKEN" -H "Accept: application/vnd.github+json" \
     -d '{"ref":"main","inputs":{"flow":"fresh"}}' \
     https://api.github.com/repos/conlusive/Dataward/actions/workflows/pipeline-daily.yml/dispatches | head -1
   ```

   `HTTP/2 204` means it started: the run appears under Actions as "workflow_dispatch". `401` is a wrong
   or expired token, `403` or `404` a token without *Actions: Read and write* on this repository.

The token can only start workflows of this one repository; it cannot read the code's secrets. Keep it out
of the repository and of chat.
