.PHONY: install lint test test-all scrape

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
