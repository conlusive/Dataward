# Dashboard

A Streamlit app that reads **only the parquet files of `make export`** (and `status.json`), never the
database. The UI is in Ukrainian.

```bash
make pipeline            # or `make export` after a dbt build: writes data/export
make dashboard           # http://localhost:8501
make docker-dashboard    # the same in a container (reads ./data/export read-only)
```

Set `DASHBOARD_DATA_DIR` to read another directory, and `DBT_DOCS_URL` to show a link to the dbt docs
on the "about the data" page.

## Pages

Six pages in a sidebar under the pixel logo, grouped as Огляд / Вакансії / Аналітика / Система. Tabs
inside a page split one topic into views; the filters of the catalog live in the sidebar so that they stay
in view while the list scrolls.

| Page | Tabs | Shows | Reads |
|---|---|---|---|
| Головна | - | six numbered tiles (open, new, closed vacancies with a sparkline and the change since yesterday; skills seen; the leading skill; pipeline health), open vacancies by source, the top-10 skills, categories and levels, the freshest vacancies (when there is a catalog), links to the other pages | `fct_market_daily`, `fct_skill_demand_monthly`, `dim_skill`, `status.json`, `last_update.json`, the catalog |
| Каталог | Вакансії / Що вимагають / Компанії | **the vacancies themselves**: filters (search in the title and company, direction, level, skills with "all" or "any", only open, only with a salary, minimum salary, remote, when it appeared, source), four tiles describing the selection, a sortable table with links, a card of the vacancy you click (all skills, required ones marked, dates, both links when it is on both sites), what the selection asks for, which companies hire, a CSV download | `fct_vacancy_catalog` (local only) |
| Ринок | Динаміка / Категорії / Рівні / Таблиця | the same tiles for the filtered slice (source, category, level), a line per source, new vs closed per day, ranked bars, and the rows as a table with a CSV download | `fct_market_daily` |
| Навички | Рейтинг / Навичка / Стеки | a searchable, sortable ranking (share, how often a hard requirement, change against the previous month in percentage points, declared salary) with a CSV download; one skill with its trend, salary and related skills; the stack clusters and a graph of one of them | demand, `dim_skill`, `fct_skill_pairs`, `fct_salary_by_skill`, `skill_clusters` |
| Зарплати | Калькулятор / Орієнтири DOU / За навичками / Тривалість вакансій | the model's p10-p50-p90 for a profile; the survey's median by year with its p25-p75 band; declared salaries by skill; how long a vacancy stays open | `salary_model_grid` (optional), `fct_salary_survey`, `fct_salary_by_skill`, `fct_vacancy_lifetime` |
| Стан і дані | Стан / Перевірки / Скрапінг / Про дані | health in one line, SLOs, recent runs, quality checks, scraping errors, volumes, the export's time and tables, sources and limitations | `status.json`, `last_update.json` |

## The vacancy catalog is local on purpose

`fct_vacancy_catalog` has one row per real vacancy (the same job on DOU and Djinni is one row): title,
company, direction (category), level, salary, place, skills (all, and the required ones), dates, open or
closed, and the link to the original page. It has no description text.

These are other people's listings and the repository is public, so the table is marked `meta.private` in
`warehouse/models/marts/schema.yml`. It is exported to `data/export` like every mart, but the nightly
workflow first runs `jobmarket export-public`, which copies the export to `data/export_public` without
the private tables (and without their entry in `last_update.json`), and uploads only that copy.
`tests/test_export.py` tests the copy and fails if the workflow stops using it. So the catalog exists
wherever you build the export yourself:

```bash
make pipeline          # scrape, parse, dbt and export: the whole nightly run, locally
make dashboard         # the Каталог page now lists the vacancies
```

On an export without it (the CI artifact) the page says so instead of failing. Showing the catalog to other
people is a separate decision about the sites' terms; nothing here publishes it.

## The look

- **Colours**: the "smoky lilac" pair, surface `#303032` and accent `#AAA8FF`; cards are a step darker
  (`#28282A`). The theme is in `.streamlit/config.toml` (native Streamlit options) and `dashboard_theme.py`
  (one stylesheet for the tiles, tabs, sidebar and header).
- **Pixel and terminal**: Tiny5 (a pixel font with good Cyrillic) for headings, figures and labels,
  JetBrains Mono for text and tables. Corners are stepped (a CSS clip), a page starts with a prompt
  (`$ вакансії · каталог`) and a blinking cursor after the title (switched off by `prefers-reduced-motion`),
  section labels read `// ВИБІРКА`, the open tab has an arrow. The fonts come from Google Fonts, and the
  browser falls back to its own monospace font offline. Pixelify Sans was tried first and dropped: its
  Cyrillic is crude.
- **Logo**: DATAWARD spelled in a 5x7 pixel font, with a pixel shadow and a blinking terracotta cursor;
  the sidebar icon and the favicon are the "D" and the cursor. `dashboard_logo.py` draws them from a glyph
  table (`python -m jobmarket.dashboard_logo` rewrites `dashboard/static/`), and a test keeps the committed
  files equal to its output.
- **Charts** (`dashboard_charts.py`, Altair) follow the dataviz rules in a pixel style: thin square-ended
  bars, two-pixel lines, square markers, a hairline grid, a tooltip on every mark, a legend only when two
  series share a chart. The two series colours (`#8481F5`, `#E5603B`) were checked with the palette
  validator on this surface (dark lightness band, colour-blind separation about 27, contrast over 3:1); a
  source always wears the same colour whatever the filter leaves. The accent itself is too light for large
  fills, so it is used for text, lines and highlights.
- **State is never colour alone**: a status chip or table cell carries an icon and a word (✓ ▲ ✕); a
  required skill is marked with a square as well as the accent.
- **Graph of a stack** shows at most 60 of the strongest links and only the skills they touch; a big
  cluster drawn in full is a hairball nobody can read.

## How it is built

- `src/jobmarket/dashboard_data.py`: plain functions over DataFrames (filters, ranking, trends, related
  skills, the stack graph, benchmarks, health). No Streamlit, so they are tested directly.
- `src/jobmarket/dashboard_theme.py`: colour tokens, the stylesheet and small HTML pieces (header, status
  chip, section label, skill tags, fact list); text is escaped. No Streamlit import either.
- `src/jobmarket/dashboard_logo.py`: the pixel logo, the sidebar icon and the favicon.
- `src/jobmarket/dashboard_charts.py`: the charts, each taking a frame with fixed column names.
- `src/jobmarket/dashboard_ui.py`: cached loading (`st.cache_data`, 5 minutes), one place that turns a
  missing file or column into a message instead of a stack trace, and the tile/card helpers.
- `dashboard/app.py` and `dashboard/views/*.py`: navigation and one script per page.
- `REQUIRED` in `dashboard_data.py` lists the columns each table must have; a test keeps it inside the
  dbt contracts, so the producer cannot rename a column the dashboard reads without a failing test.

The dependencies (Streamlit, pandas) are the optional `dashboard` group, so the pipeline image does not
carry them. `Dockerfile.dashboard` installs only that group, without dbt or dev tools, and copies
`.streamlit/` (the theme).

## Looking at it with real data

The nightly run keeps its export for 14 days as the `gold-export` artifact:

```bash
gh run download "$(gh run list --workflow pipeline-daily.yml --limit 1 --json databaseId -q '.[0].databaseId')" \
  -n gold-export -D /tmp/gold-export
DASHBOARD_DATA_DIR=/tmp/gold-export make dashboard
```

The calculator tab stays empty there: the model is trained locally (`make train`), not in CI.
The first time Streamlit runs on a machine it asks for an email; press Enter (or add
`--server.headless true`).

## Tests

`tests/test_dashboard_data.py` checks the functions on a small made-up export whose answers are worked
out by hand. `tests/test_dashboard_app.py` runs every page headlessly (Streamlit's `AppTest`, through the
entry point so that the page links work) and checks the numbers shown, the filters, search, the empty
states and a missing data directory. `tests/test_dashboard_charts.py` checks the chart specs (a colour per
series, a bar thickness cap, square marks, tick density), `tests/test_dashboard_theme.py` the stylesheet,
the escaping and the contrast of the colour tokens, and `tests/test_dashboard_logo.py` the pixel logo. They are skipped when Streamlit is not installed
(`uv sync --group dashboard`); CI installs it. Every page and tab was also opened in a real browser on the
nightly export, which found two bugs the unit tests had not (a shadowed argument that emptied a chart,
and repeating date labels).

## Not here yet

- **Hosting.** Streamlit Community Cloud and the Hugging Face mirror need accounts. The data must reach
  the app (the `data` branch or object storage); until then it runs locally or in the container.
- **A public vacancy list**: the catalog is local on purpose (see above); publishing other people's listings needs a decision about the sites' terms.
- **English UI**: only Ukrainian for now.
