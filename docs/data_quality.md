# Data quality: contracts and checks

Bad data should stop before it reaches the files other people read. Three mechanisms do that:
**contracts** (the shape of a table), **checks** (the content of the data, with a warn and an error
level), and the **flow**, which does not build gold or export when a silver check fails (see
[orchestration.md](orchestration.md)). Idempotency and backfill are in
[idempotency_and_backfill.md](idempotency_and_backfill.md).

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
