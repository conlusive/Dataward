.PHONY: install lint test test-all scrape scrape-surveys parse dbt-build export gold

install:
	uv sync

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

dbt-build:
	uv run dbt snapshot --project-dir warehouse --profiles-dir warehouse
	uv run dbt build --project-dir warehouse --profiles-dir warehouse

# Gold marts -> parquet in data/export (needs `make dbt-build` first).
export:
	uv run jobmarket export

# Label the gold set: `make gold` writes the sheet, edit it, then `uv run jobmarket gold-import`
# and `uv run jobmarket gold-eval`. See the README.
gold:
	uv run jobmarket gold-sample
