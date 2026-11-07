.PHONY: install lint test test-all scrape parse dbt-build

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

# Bronze -> silver for every stored day without a finished parse, then rates and the dbt layer.
parse:
	uv run jobmarket parse all --missing
	uv run jobmarket fetch-rates
	uv run jobmarket parse all --missing

dbt-build:
	uv run dbt snapshot --project-dir warehouse --profiles-dir warehouse
	uv run dbt build --project-dir warehouse --profiles-dir warehouse
