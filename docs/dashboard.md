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

Eleven pages in a sidebar under the pixel logo, grouped by what you are doing: Огляд, Вакансії
(Каталог, Для мене, Збережені), Розвиток (Профіль, Навчання, Практика), Аналітика, Система. The
sidebar is part of the layout and cannot be collapsed; the frog sits under the menu on every page. Tabs
inside a page split one topic into views; the filters of the catalog live in the sidebar so that they stay
in view while the list scrolls.

| Page | Tabs | Shows | Reads |
|---|---|---|---|
| Головна | - | a header with the last pipeline runs as squares and a typed line; bracketed figures (open, new, closed, skills, sources); a "BREAKDOWN" panel (thin stacked bars per day, a metric and a cut chosen from two selectors); the biggest **directions** as tiles, each with a button that opens its vacancies (the catalog, or the market page without one); the top-10 skills and what changed since last month; the freshest vacancies as tiles (when there is a catalog) | `fct_market_daily`, `fct_skill_demand_monthly`, `dim_skill`, `status.json`, `last_update.json`, the catalog |
| Каталог | Вакансії / Що вимагають / Компанії | **the vacancies themselves**: filters (search in the title and company, direction, level, skills with "all" or "any", only open, only with a salary, minimum salary, remote, when it appeared, source), four tiles describing the selection, a sortable table with links, a card of the vacancy you click (all skills, required ones marked, dates, both links when it is on both sites), what the selection asks for, which companies hire, a CSV download | `fct_vacancy_catalog` (local only) |
| Для мене | - | the open vacancies that suit your target, ranked by how well your skills cover them (a required skill counts twice), with what you have and what is missing, a readiness figure, a minimum-match slider and a card with a save button | the catalog, the profile |
| Збережені | - | saved vacancies by stage (збережено, відгукнувся, співбесіда, оффер, відмова) with a note, edited in a table | the profile |
| Профіль | - | **your frog**, its level and experience, the streak, what to do next, achievements, and the settings: skills you know and learn, a target (direction, level, minimum salary, remote), a daily goal | the profile file, `dim_skill`, `fct_market_daily` |
| Навчання | - | skills you are learning with their progress, the plan ("what completes the most vacancies") and **learning resources** for any skill, with a "finished" tick | the profile, the catalog, `learning_resources.yaml` |
| Практика | - | the interview trainer: a session of questions with a reacting frog, and your progress by skill | the profile, `interview_questions.yaml` |
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

## The profile, the frog and learning

The profile is one small JSON file on this machine, `data/profile/profile.json` (git-ignored; set
`PROFILE_PATH` to move it). There is no account and no server-side storage: it is a single-user tool. The
file is written atomically (a half-written file is never visible), readable by the owner only, every field
is coerced when it is read (a hand-edited file cannot break the page) and a damaged file is set aside as
`profile.json.damaged-<time>`. If it cannot be written (a read-only mount) the page says so. In the
dashboard container mount a folder to keep it: `-v "$PWD/data/profile:/app/data/profile"`.

- **Match**: a vacancy's skills that you know, weighted (a required skill counts twice), as a percentage.
  Vacancies come from the catalog, narrowed by your target; a minimum salary hides only vacancies that state
  a lower one (most state none). **Readiness** is the median match of your 20 best vacancies.
- **Learning plan**: for the vacancies that fit your target, which skills you lack. "Відкриває" counts the
  vacancies where a skill is the only required one still missing, so learning it completes the vacancy.
- **Learning resources** (`learning_resources.yaml`): about 45 skills with official docs first, then
  practice platforms and courses, in Ukrainian where there is a good one. Every link was opened when the list
  was made, and a test checks the shape (https, a known kind, skills from the taxonomy). A skill without a
  list gets two search links marked as not curated. Tick a material "Пройшов" and it is remembered.
- **Saved vacancies** keep a snapshot (title, company, link), so they outlive the catalog, which is rebuilt.
- **Trainer** (`interview_questions.yaml`): 60 questions with short model answers for 12 skills at three
  levels. A session draws from your skills, from the plan, from one skill or from everything. You reveal the
  answer and rate yourself: "Знаю" moves the question up a Leitner box (it comes back after 2, 4, 8, 16
  days), "Частково" keeps the box, "Не знаю" sends it back to box 1 (tomorrow). The session card is a
  Streamlit fragment, so a click redraws only the card.
- **The frog** is a pixel mascot drawn from character grids (`dashboard_mascot.py`): a tadpole, a froglet
  (level 3), a frog (level 6) and a king of frogs (level 10), each in a mood: idle, happy (answered today),
  party (the daily goal is met), sleepy (three days away), sad and thinking (reacting to an answer). It bobs
  and blinks in steps and stops for reduced motion.
- **Experience** is worked out from the saved profile, so it cannot drift or be earned twice: 2 per answer,
  10 per question learned (box 4 or higher), 5 per finished material, 2 per saved vacancy, 5 per application,
  1 per known skill. Level n starts at 25 (n - 1)^2 XP. The **streak** is days in a row with an answer
  (yesterday still counts until today is over). There are ten achievements and a list of "what to do next".

## Filters you can tell apart

An idle filter and an active one must not look alike. Short lists (source, level) are toggle pills: the
chosen ones are filled with the accent. Long lists are selects with a dashed border and the placeholder
"Усі ..." while idle, and an accent border and filled tags once something is chosen. Under the filters the
active ones are listed as tags (`Джерело: dou`), a quiet "фільтри не задано" when none is set, a count of
what is shown ("57 з 462") and a reset button. The catalog's default "only open" is itself a filter, so it
is shown as a tag too.

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
- **Logo**: three rising pixel bars, then DATAWARD spelled in a 5x7 pixel font with a pixel shadow, and a
  static terracotta full stop; the sidebar icon and the favicon are the bars and the stop. `dashboard_logo.py` draws them from a glyph
  table (`python -m jobmarket.dashboard_logo` rewrites `dashboard/static/`), and a test keeps the committed
  files equal to its output.
- **Motion**: things arrive in steps, never glide: the figures and tiles rise one after another, charts
  are wiped in, the meters grow, the subtitle of the home page types itself, the newest pipeline square
  pulses and the title cursor blinks. All of it stops for `prefers-reduced-motion`.
- **Charts** (`dashboard_charts.py`, Altair) follow the dataviz rules in a pixel style: thin square-ended
  bars, two-pixel lines, square markers, a hairline grid, a tooltip on every mark, a legend only when two
  series share a chart. The four series colours (`#8481F5`, `#E5603B`, `#26A08F`, `#B58A1F`) were checked with the palette
  validator on the card surface (dark lightness band, colour-blind separation at least 12.7, normal-vision
  at least 17.5, contrast over 3:1); a chart never needs a fifth: the tail of a breakdown is folded into a
  grey "Інші". A source always wears the same colour (dou the first, djinni the second) whatever the filter
  leaves. The accent itself is too light for large
  fills, so it is used for text, lines and highlights.
- **State is never colour alone**: a status chip or table cell carries an icon and a word (✓ ▲ ✕); a
  required skill is marked with a square as well as the accent.
- **Graph of a stack** shows at most 60 of the strongest links and only the skills they touch; a big
  cluster drawn in full is a hairball nobody can read.

## A running dashboard picks up edits

Streamlit reruns a page script when it changes, but the modules it imports from `src/` stayed in memory,
so a dashboard that was running during a `git pull` answered "module has no attribute ..." until it was
restarted. `dashboard/app.py` now calls `dashboard_reload.refresh()` first: when any dashboard module was
edited after the process started, all of them are forgotten and imported again (all, because the importer
of an edited module keeps the old copy). The reload module itself cannot reload itself, so restart once
after the very first update to this version.

## How it is built

- `src/jobmarket/dashboard_data.py`: plain functions over DataFrames (filters, ranking, trends, related
  skills, the stack graph, benchmarks, health). No Streamlit, so they are tested directly.
- `src/jobmarket/dashboard_theme.py`: colour tokens, the stylesheet and small HTML pieces (header, status
  chip, section label, skill tags, fact list); text is escaped. No Streamlit import either.
- `src/jobmarket/dashboard_logo.py`: the pixel logo, the sidebar icon and the favicon.
- `src/jobmarket/dashboard_profile.py`, `dashboard_interview.py`, `dashboard_resources.py`,
  `dashboard_progress.py` and `dashboard_mascot.py`: the profile file and matching, the question bank and
  its schedule, the learning resources, experience and levels, and the frog. No Streamlit, so they are
  tested directly.
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
