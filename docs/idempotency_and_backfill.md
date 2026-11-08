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

## Contracts

- **Gold:** the marts have enforced dbt contracts (`warehouse/models/marts/schema.yml`); the export
  reads its schema from them and stops when a table differs.
- **Silver:** `contracts/silver.yml` lists columns, types, nullability and primary keys.
  `tests/test_contracts.py` fails when `SilverStore`'s DDL differs from it, so a schema change must
  edit the contract in the same PR. `jobmarket dq` checks the live database against it too.
- Old databases are brought up to date by the `ALTER TABLE ... IF NOT EXISTS` migrations in
  `SilverStore`; a test checks that a database from before them ends up matching the contract.

## Data-quality checks

`make dq` (`jobmarket dq`) runs after `dbt build` and before the export. Each check measures one
number and compares it with a warn and an error limit (constants at the top of `src/jobmarket/dq.py`).
Every result, also a pass, is stored in `ops_dq_results`.

| Check | Measures | Warn | Error |
|---|---|---|---|
| `schema_contract` | differences from `contracts/silver.yml` | - | any |
| `fresh_data` | hours since the newest fetched page | 30 h | 36 h |
| `listing_volume` | latest day's listed vacancies / median of the previous 14 days | below 0.6 | below 0.3 |
| `empty_key_fields` | vacancies with an empty id, url, title or company | - | any |
| `references` | skill, group or text rows pointing at missing parents | - | any |
| `vacancies_without_skills` | share without any skill | 15% | 30% |
| `salary_in_range` | share of USD salaries outside 100-30,000 | 2% | 10% |
| `salary_parse_rate` | fall of the parsed share of salary strings, last 7 days vs earlier | 10 pp | 20 pp |
| `sightings_have_pages` | share of the latest day's listed vacancies without a parsed page | 10% | 30% |
| `salary_share_drift` | change in the share of vacancies with a salary string, newest fetch day vs earlier | 15 pp | - (warns only) |
| `description_length_drift` | relative change in the mean description length, same windows | 40% | - (warns only) |
| `parse_failures` | share of unparsed pages in the last parse runs | 1% | 5% |
| `gold_built` | rows in `fct_skill_demand_monthly` | - | none |

A check that has too little history (a few days, a few salary strings) is reported as `skipped`
and never as a pass. A check that crashes is an `error`.

- `warn`: logged, shown as an annotation on the GitHub run, and the pipeline continues.
- `error`: `jobmarket dq` exits 1, the workflow stops before the export, and the consumers keep the
  files of the last good run. The silver state is still saved, so no scraped data is lost.

Where this differs from the original plan: the volume check uses the listings seen each day
(stable from the first day) and not "new vacancies", and the skills threshold is 15%/30% instead of
5% because about 10% of real vacancies name no known skill. `parse_failures` counts vacancy pages
only; the survey loader also logs parse tasks, with rows instead of pages.

## When a check fails

1. `uv run python -c "import duckdb; print(duckdb.connect('data/jobmarket.duckdb', read_only=True).sql(\"select * from ops_dq_results where status in ('warn','error') order by created_at desc limit 20\"))"`
2. `fresh_data` or `listing_volume`: the scrape failed or the markup changed. Look at the scrape
   step of the run (`http_403`, `errors` in `ops_scrape_runs`).
3. `parse_failures`, `salary_parse_rate`: the parser no longer reads a page type. Fix the parser,
   then `make backfill` over the affected days.
4. `schema_contract`: the DDL changed without the contract. Update `contracts/silver.yml` and
   check that gold still builds.
