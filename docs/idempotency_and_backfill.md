# Idempotency, backfill and data quality

A run for a date can be repeated at any time and gives the same data, not twice the data. Bad data
stops before the exported files change. This page says how, and which tests prove it.

## Idempotency, layer by layer

| Layer | Mechanism | Proven by |
|---|---|---|
| Bronze | The path is a function of (source, run date, URL): `{source}/dt={date}/{hash}`. A second write of the same page replaces the same file; an unchanged page is not rewritten. The `.meta.json` is written last and is the commit marker, so a half-written file counts as missing. | `tests/test_bronze.py` |
| Silver vacancies | Upsert by `id` (`ON CONFLICT ... DO UPDATE`). It only overwrites with a page fetched at the same time or later, so a backfill of an old day cannot replace a newer version. Columns filled by later steps (salary, seniority, group) are not touched by the parser upsert. | `tests/test_idempotency.py` |
| Silver enrichment | Salary, text signals, skills, USD and dedup are recomputed from silver on every run. | `tests/test_idempotency.py` |
| Sightings, rates, survey | Primary keys (`vacancy_id, seen_date`; `rate_date, currency`) with upsert; a survey file replaces its own rows in one transaction. | `tests/test_idempotency.py`, `tests/test_dou_salaries.py` |
| Gold (dbt) | Marts are `table` models: a full rebuild from silver, no `append`. The SCD2 snapshot adds a row only when the vacancy changed. | `tests/test_idempotency.py` |
| Ops tables | A re-run is a new attempt (`attempt + 1`), never an edit of the old row. | `tests/test_ops.py` |
| Parquet export | Written to `data/export.tmp`, checked against the dbt contracts, then swapped in with its `last_update.json`. | `tests/test_export.py` |

`tests/test_idempotency.py` runs one date twice (and the stored days out of order) and compares a
hash of every `silver_*` table and every mart (columns starting with `_` are bookkeeping and are
left out). It also edits a value by hand and shows that the fingerprint notices it and that a re-run
repairs it.

## Backfill

Past listing pages cannot be downloaded again: the sites only serve the current listing. So a
backfill means reprocessing what bronze already holds. It needs no network, and the LLM answers come
from the cache.

```bash
make backfill FROM=2026-11-01 TO=2026-11-30   # re-parse the stored days in the range, then rebuild gold
uv run jobmarket backfill all --from 2026-11-01 --to 2026-11-30   # the silver part only
```

- Only days that exist in bronze are processed; a range never invents days.
- A parser or taxonomy change: backfill the whole range **including the newest day**. The upsert
  does not let an older page overwrite a newer version of the same vacancy.
- Re-downloading today's pages (`jobmarket scrape ... --refetch`) is a separate, explicit action.
- Days are processed one after another. DuckDB allows one writer, and the parse is quick (about
  90 s for 6,900 vacancies), so parallel days would add locking and no speed.

## Contracts, data-quality checks and what to do when one fails

See [data_quality.md](data_quality.md).
