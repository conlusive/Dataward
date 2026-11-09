.PHONY: install lint test test-all scrape scrape-surveys parse backfill dbt-build dq dq-silver dq-gold pipeline export docker-build docker-pipeline dashboard docker-dashboard train gold

install:
	uv sync --group dashboard --group ml

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

test:
	uv run pytest

test-all:
	uv run pytest -m ''

# Daily sources into bronze. Usage: make scrape [RUN_DATE=YYYY-MM-DD]
scrape:
	uv run jobmarket scrape all $(if $(RUN_DATE),--run-date $(RUN_DATE),)

# Survey waves: files already in bronze are skipped, so this is cheap on repeat runs.
scrape-surveys:
	uv run jobmarket scrape dou_salaries

# Bronze -> silver for every stored day without a finished parse, then rates and the dbt layer.
parse:
	uv run jobmarket parse all --missing
	uv run jobmarket fetch-rates
	uv run jobmarket parse all --missing
	uv run jobmarket parse-surveys

# Re-parse stored days after a parser or taxonomy change, then rebuild gold. No network, no LLM calls
# (answers come from the cache). Usage: make backfill FROM=2026-11-01 TO=2026-11-30
backfill:
	@test -n "$(FROM)" -a -n "$(TO)" || { echo "usage: make backfill FROM=YYYY-MM-DD TO=YYYY-MM-DD"; exit 2; }
	uv run jobmarket backfill all --from $(FROM) --to $(TO)
	$(MAKE) dbt-build

dbt-build:
	uv run dbt snapshot --project-dir warehouse --profiles-dir warehouse
	uv run dbt build --project-dir warehouse --profiles-dir warehouse

# Data-quality checks on silver and gold; exit 1 when a check is at error level.
dq:
	uv run jobmarket dq

# The same checks by layer: silver before dbt (bad silver data must not reach gold), gold after.
dq-silver:
	uv run jobmarket dq --layer silver

dq-gold:
	uv run jobmarket dq --layer gold

# The whole daily flow with retries, timeouts, step dependencies and ops rows.
# Usage: make pipeline [RUN_DATE=YYYY-MM-DD]
pipeline:
	uv run jobmarket flow daily $(if $(RUN_DATE),--run-date $(RUN_DATE),)

# The pipeline in a container (see docker-compose.yml); data stays in ./data.
docker-build:
	docker compose build pipeline

docker-pipeline:
	docker compose run --rm pipeline

# The dashboard on the last export (run `make pipeline` or `make export` first): localhost:8501
dashboard:
	uv run --group dashboard streamlit run dashboard/app.py

docker-dashboard:
	docker compose up --build dashboard

# Train the salary model on the exported survey rows and write the dashboard's grid. Needs the ml
# group (`uv sync --group ml`) and `make export` first. Writes docs/ml_report.md.
train:
	uv run --group ml jobmarket train-salary
	uv run --group ml jobmarket salary-grid

# Gold marts -> parquet in data/export (needs `make dbt-build` first).
export:
	uv run jobmarket export

# Label the gold set: `make gold` writes the sheet, edit it, then `uv run jobmarket gold-import`
# and `uv run jobmarket gold-eval`. See the README.
gold:
	uv run jobmarket gold-sample
