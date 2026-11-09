# Changelog

## Unreleased

### Changed (dashboard v3)
- **Home page** rebuilt: pipeline runs as squares, bracketed figures, a "BREAKDOWN" panel (thin stacked bars,
  a metric and a cut from two selectors), direction tiles that open their vacancies, top skills and what
  changed, fresh vacancy tiles.
- **Filters you can tell apart**: toggle pills for short lists, dashed idle and accent-filled active
  selects, tags of the active filters, a count and a reset button (market and catalog).
- **Logo**: rising bars + the name + a static full stop (no blinking). **Motion**: stepped entrances, chart
  wipes, growing meters, a typed subtitle; off for reduced motion. A fourth and third series colour,
  validated.
- A running dashboard now picks up edited modules (`dashboard_reload`) instead of failing with "no
  attribute" until restarted.

### Fixed
- A source lost its colour when the other was filtered away (colour followed position, not the entity).

### Added
- **Vacancy catalog**: the dbt model `fct_vacancy_catalog` (one row per real vacancy, with skills, salary,
  dates and the link) and a Каталог page: filters in the sidebar, a table, a card of the chosen vacancy, what
  the selection asks for and which companies hire. The table is flagged `meta.private`; `jobmarket export-public` makes a copy of
  the export without it, the nightly workflow uploads only that copy, and tests cover both.
- A pixel logo (`dashboard_logo.py`), the sidebar grouped into Огляд / Вакансії / Аналітика / Система.

### Changed
- **Dashboard redesign**: a home page with six numbered tiles, five pages with tabs (Головна, Ринок,
  Навички, Зарплати, Стан і дані), a searchable and sortable skill ranking with the change against the
  previous month, declared salaries by skill, CSV downloads, and a dark "smoky lilac" theme with monospace
  type. The stack graph now draws at most 60 of the strongest links.
- The look is now pixel and terminal: Tiny5 headings, stepped corners, a prompt and a blinking cursor,
  square chart marks.

## 0.2.1: the first measured accuracy

### Added
- **Gold set**: `gold-label` (blind terminal labelling), `--labelled-by` provenance recorded in the gold
  file and on the metrics page, taxonomy gaps (`+ Name`) kept as `wanted`, `regression_min_f1` kept on
  re-import. First measurement on 150 vacancies: dictionary F1 0.81, LLM F1 0.80 (labels by an LLM).
- LLM client: `--rpm` limiter, patient 429 handling, `--sheet`; verified Gemini prices.

### Fixed
- Evaluation counted a method that ran and found nothing as "not run", leaving its misses out of the score.

## 0.2.0: the pipeline, its checks, and what sits on top

The first release that is more than ingestion. Everything below was built between 2026-11-06 and
2026-11-09.

### Added
- **Silver**: parsers for DOU and Djinni, salary parsing with USD conversion at the National Bank rate,
  seniority, experience and English from the text, a skill dictionary (trie, strict ambiguous words), an
  LLM method with a cache and a cost cap, deduplication across the two sites, the DOU salary survey.
- **Gold (dbt)**: vacancy lifecycle and SCD2 history, deduplicated skill demand with roll-ups to parent
  skills, skill co-occurrence (lift, PMI, NPMI), salary percentiles that are not published for small
  samples, how long vacancies stay open, a daily market mart, features for the salary model. Enforced
  column contracts and tests on every mart.
- **Export**: parquet checked against the dbt contracts, `last_update.json`, skill clusters (Louvain).
- **Reliability**: a test that a date run twice leaves silver and gold unchanged, `make backfill`, a
  contract file for silver, 13 data-quality checks with warn and error levels, SLOs.
- **Operations**: one flow (`make pipeline`) with timeouts, retries for scraping, step dependencies and
  run records; Docker images for the pipeline and the dashboard; a Telegram summary when a bot is set up.
- **Observability**: `ops_pipeline_runs`, `jobmarket status`, `status.json`, a postmortem template and a
  first real postmortem.
- **Consumers**: a Streamlit dashboard (six pages, Ukrainian) and a salary model (CatBoost p10/p50/p90 on
  the survey, MLflow tracking and promotion) with a calculator.
- **Docs**: architecture, data sources, data model, a generated dbt lineage, data quality, taxonomy guide,
  decisions, operations, a test that the docs' links and `make` targets exist.

### Known gaps
- Bronze is kept in a rolling GitHub Actions cache, not in durable object storage.
- No Postgres warehouse, no hosted dashboard, no monthly retraining.
- Precision and recall of the skill methods are not measured yet (the hand-labelled set is not done), and
  the LLM method has not been run on the corpus.
- The history is days, not weeks: no trends yet, and the reliability record is short.

## 0.1.0: ingestion into bronze

Scrapers for DOU, Djinni, the National Bank and the DOU survey, an immutable bronze store, run records,
CI and a daily workflow.
