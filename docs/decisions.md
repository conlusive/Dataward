# Decisions

The decisions that shaped the project, with the reason and what was turned down. Each was made when the
need appeared, usually after the data disagreed with the first idea.

## Data and storage

**Bronze, silver, gold, and bronze never changes.** Every layer has a contract, and the raw files are
kept exactly as received. *Why:* a parser fix, a new skill or a new rule must be able to rebuild
everything without the network. *Rejected:* a flat "raw / processed" split.

**DuckDB for everything now, Postgres later.** *Why:* no infrastructure to start, fast, SQL that dbt
runs. *Not done yet:* the Postgres target; the models use DuckDB functions, so it needs porting first.

**Idempotency by construction.** Bronze paths are a function of (source, date, URL); silver writes are
upserts that never let an older page overwrite a newer one; gold is rebuilt; ops rows are new attempts.
*Why:* a re-run must be safe. *Rejected:* appending and de-duplicating later.

**Interim bronze storage in the GitHub Actions cache.** *Why:* it needs no account. *Cost:* it is not
durable and has a size limit; object storage is the planned replacement.

## Sources

**work.ua is not scraped.** It answers automated clients with a Cloudflare challenge; getting around that
is bypassing a protection, so the project uses two job sites. Honest `User-Agent`, `robots.txt`, a low
request rate.

## Silver: turning pages into facts

**A dictionary for skills, built on a trie, with "strict" words.** Words like Go, R, Spring or Swift count
only with the exact spelling and a context word nearby. *Why:* the first version found "can", "composer"
and "ray" in ordinary sentences. *Rejected:* a library for fuzzy matching, and an LLM as the first line
(slow, paid, not repeatable).

**The LLM client is a small piece of `httpx` and `pydantic`, with a cache.** Answers are cached by title,
text hash, prompt and model, and a dry run estimates the cost first. *Rejected:* `litellm` and
`instructor` (two large dependencies for one request shape).

**Deduplication inside a company, by title and text, never across levels.** The thresholds from the plan
were both too weak (the same boilerplate text on two different vacancies) and too strict (it missed
"Senior Java Backend Engineer" against "Java Backend Engineer"). Employers who hide their name are never
compared with each other. *Why:* a wrong merge is worse than a missed one.

**Lifecycle and SCD2 in dbt.** A vacancy is `new`, `active` and `closed` after two days off the listing;
the first day of data is flagged, because those vacancies may have been open for weeks. *Rejected:*
closing a vacancy on one missed day (a listing page can fail once).

**The skill gold set is labelled blind.** The sheet has no suggestions and the texts stay local.
*Why:* a prepared list makes a person agree, and then the metric measures the agreement.

## Gold

**Marts do not publish small samples, and they are `table`, not `incremental`.** The minimum sizes are
variables in one file. *Why:* a median of three salaries misleads more than an empty cell; the largest
mart builds in seconds, so incremental logic would add state for no gain.

**Contracts are the source of truth for the export.** The exporter reads columns and types from the dbt
contracts and stops if a table differs. Skill clusters (Louvain) are computed at export, from the pair
mart. *Why:* a consumer never sees a half-updated or renamed set.

## Operations

**Backfill is a re-parse of stored days, without parallelism.** Past listing pages cannot be downloaded
again, and DuckDB has one writer. To apply a parser change to everything, the range must include the
newest day.

**Checks have two levels, and thresholds live in one place.** A `warn` is reported; an `error` stops the
run before the export. A check with too little history is `skipped`, never a pass. The thresholds were
calibrated on real data (for example, about 9% of vacancies name no known skill, so the 5% of the plan was
replaced).

**The flow is plain Python over the Makefile, not Prefect.** Scheduling is already GitHub Actions, and
retries, timeouts and dependencies for seven steps are about a hundred lines. Prefect would add a large
dependency tree and a server. Each step is a command, so wrapping them later is mechanical.

**SLOs are measured by a query.** Freshness 36 hours, 95% of runs in 30 days, under 10% of vacancies without
a skill. A value that cannot be judged yet is `n/a`.

## Consumers

**The dashboard reads only exported parquet.** Streamlit and pandas are an optional dependency group with
their own image. The column list the dashboard needs is checked against the dbt contracts by a test.

**The salary model is trained on the survey, not on the vacancies.** Only a few hundred vacancies state a
salary, from a few days of scraping, so a time split is impossible. The survey has about 289,000 answers
over 15 years. CatBoost predicts p10, p50 and p90, is judged on the last year it has not seen, against a
baseline, and is promoted only if it beats the baseline and the current production model on the same test
rows. *Result:* about 11% lower error than the baseline; better, not precise.
