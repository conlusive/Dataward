# Changelog

## Unreleased

### Changed (hints, charts, calculator)
- Long grey explanations became a small **"?" that shows its text when pointed at** (or focused with the
  keyboard); card notes sit beside the card title the same way.
- **Market page**: the stacked bars are columns of dots with the total over each; "new and closed" is one
  axis with arrivals above and departures below, and the first day (where "new" is everything) is left
  out and explained in a tip.
- **Skills table** fits its box (fewer, narrower columns). The two selects on the home page show their
  whole value. Direction and vacancy tiles grow with their tags instead of cutting them.
- **The salary calculator works on the public site**: the trained grid ships with the app
  (`dashboard/model/`), used when the export has none; `make train` on your machine still wins.

### Changed (clearer figures)
- The page is a creamier plombir (`#FBF3E1`). The dot columns now carry **the total over every column, the
  day under it and what one dot is worth**; the waffle has a key with each part's share and value. Softer
  chart colours (berry, periwinkle, gold, rose) that still pass the palette validator.

### Changed (the look, second pass)
- **"Soft signal"** replaces the calm serif design the owner did not like: a plombir page, powder, mauve
  and wine worn as whole blocks, a heavy grotesque, small-capital labels, self-numbering sections, a menu
  without a panel, and **numbers and figures made of dots**: a ring of dots, stacked columns of dots and a
  waffle of 100 dots on the home page (`dashboard_dots.py`, plain SVG). New chart colours passed the
  palette validator.

### Changed (the look)
- **A light, calm design** replaces the dark pixel-terminal one: a warm off-white page, white cards with
  soft corners, serif headings (Source Serif 4) over sans text (Inter), a clay accent and pastel tints per
  part of the product. The prompt, brackets, cursor, stepped corners and capitals are gone. New chart
  colours passed the palette validator on the white card; text colours clear 4.5:1 (tested). A calm
  wordmark replaces the pixel logo in the menu.
### Added (hourly updates)
- **New vacancies every hour.** `jobmarket flow fresh` (`make pipeline-fresh`) reads the first two listing
  pages of every category again and fetches only vacancy pages not stored yet, then parses today, builds
  gold and exports. The nightly full sweep stays (closures need it: a vacancy closes after two days without
  a sighting, so an hourly run can never close one). `pipeline-daily.yml` runs it at minute 17 of every hour.
- The public site refreshes its data every 20 minutes, and **at a start fetches data older than two hours
  before serving**, so a host that slept or an old image no longer shows stale data for the first minute.
- An optional `deploy` job asks Render to deploy after a green merge (secret `RENDER_DEPLOY_HOOK_URL`).

### Changed (the public site)
- The **vacancy catalog is public**: `fct_vacancy_catalog` is no longer `meta.private`, so the nightly
  export carries it and the public site lists the vacancies (no description text, no contacts, a link to
  the original, a note on whose listings they are). It shows up on the site after the next nightly run.
- The public copy shows **the market and the vacancies, not a person**: Головна, Каталог, Ринок, Навички,
  Зарплати and Стан системи. The pages about you (Для мене, Збережені, Профіль, Навчання, Практика), the
  avatar, the undo bar and the "Сьогодні" block are not registered there, so no visitor meets a profile
  that is not theirs. The list has no save button or fit there. Everything personal stays on your machine.
- Menu colours follow the page a group holds, not its position, so the shorter public menu is coloured right.

### Changed (public site)
- Where the vacancy catalog is missing (the public export never has it: the listings belong to others),
  the **public demo** says so plainly and names what it does have (market, skills, salaries, profile,
  practice) instead of telling the visitor to run `make pipeline`. A local run still gets the build hint.

### Changed (workspace)
- The **filters of the catalog moved out of the sidebar** into a bar above the list (search, direction,
  skills, level, source, and a "Ще фільтри" popover), so the menu no longer scrolls. The profile is the
  **avatar at the foot of the sidebar** (the whole card is a link) and no longer appears in the menu twice.
- The **home page** answers "what to do today": up to three coloured actions, rings for the daily goal and
  readiness, the market as rings by source, level and direction beside the daily breakdown, four
  directions, three fresh vacancies and the state of the pipeline (DQ checks, SLOs, rows in silver).
- Parts of the product have a colour (vacancies teal, learning violet, analytics red, system yellow) in the
  headings, markers and the menu.

- The vacancy list is **paged** (15 a page) with few columns that fit without a sideways scroll; the
  full set of columns stays in the card and the CSV. The header chips that flew off the home page are
  gone: the pipeline state sits in its own block at the end. The menu scrolls on its own and the avatar
  is pinned below it, so no menu item is out of reach on a short window. The filter bar has a label of one
  height above every control, so the rows line up.

- The vacancy list is no longer a table you click into: **rows on the left and the vacancy already open on
  the right** (the first one at once, a click on a row opens another). "Save the whole page" replaces
  ticking rows. "Стан і дані" is now **"Стан системи"** without a heading above it (the heading looked like
  a button that did nothing). The filter bar has more room, and its pills wrap.

- **Faster cold start on the hosted site**: bytecode is compiled when the image is built (the server cannot
  write `.pyc` files, so every start used to compile streamlit, pandas and altair again), the export of the
  build is baked into the image instead of being downloaded at every start, and the file watcher is off.
  The first refresh from the `data` branch comes a minute after the first visit.
- **Public hosting on Render**: `render.yaml`, a start script that serves on `$PORT`, and a data path that
  needs no volume. The nightly workflow publishes the public export (no third-party listings) to the `data`
  branch from a job of its own; the container downloads it on start and every 6 hours
  (`dashboard_sync.py`, only whitelisted files named by the archive's manifest). With
  `DASHBOARD_PROFILE=session` a visitor's profile lives in their tab instead of one shared file. An error
  about missing data names the file, not the server's path.
- **One tab icon in every browser**: Chrome showed ours, Safari Streamlit's own logo. Streamlit's page links
  its own `favicon.png` before any script runs, then swaps it for `page_icon` as a JPEG, and Safari keeps
  what it finds at load. The image now replaces Streamlit's `favicon.png` with ours; a local run gets the
  same from a small script (`dashboard_icon.py`) that sets a PNG and an `apple-touch-icon` from the
  static folder the app now serves. Safari keeps icons hard: close the tab, or quit Safari once.
- **A phone**: the menu is a drawer that starts closed (the buttons that hide it are now only hidden on a
  desktop; before, an open menu covered the page and could not be closed). Figures sit in pairs, the
  catalog filter bar is about half as tall, the pills wrap, the sort and the pager share two rows. A
  tapped vacancy opens as a full-screen card with a "← До списку" button (below the list it was a page
  away). Targets are at least 44 px on a touch screen.
- **Smoother page changes**: the old per-element arrival (figures rising one after another, charts
  wiped in) showed the page being built and read as jumping. Now the page body is hidden while it is
  built and shown at once, with no fade (no `html.dw-go`, then `html.dw-enter`); meters and the typed
  subtitle stay. The "Навички" page builds only the open tab instead of all three (its tables and the
  graph were drawn while hidden). Vacancy rows in the catalog have one fact per line: the title, the
  company and level, then the pay (in the accent colour) and the fit.
- **Arrival animations are back, once per page**: figures and tiles rise, charts are wiped in, meters grow,
  the subtitle types itself, but only when a page opens (`html.dw-enter` for 2.8 s), never after a click.
- **Lighter on a small machine**: nothing animates on its own any more, the
  `:has()` rule over all wrappers is gone, progress rings are CSS, home draws one chart of the market at a
  time instead of three. The toolbar over tables and charts (full screen, search, download) is hidden
  everywhere. On a short window the menu drops its headings (the group colour stays) so "Стан системи"
  is never below the fold.

### Added (workspace)
- **Undo** for every hand-made change of the profile: a bar with "Скасувати" (and `z` / `Ctrl Z`), the newest
  action first, 20 actions, three minutes.
- A **vacancy list** shared by the catalog and a new "Вакансії" tab of the market page: sort, pick one row
  for a card with an analysis against the market (each skill's share, salary against the direction's
  median, days listed), pick several to save them together, CSV.
- **Keyboard**: `g` + a letter to go to a page, `/` for the search, `Ctrl K` for a palette, `?` for the
  list, `Space` and `1`-`3` in the trainer. Not printed on the pages.
- Charts: **donut**, **ring** and a 20-week **activity grid** (profile).

### Changed (proportions)
- Headings and figures are set in **Tektur** (technical, no longer pixelated; Tiny5 is gone).
- **One type scale** of six steps (0.75, 0.85, 1, 1.25, 1.75, 2.5 rem) replaces twenty-one ad-hoc sizes, one
  spacing scale, equal-height cards in a row, and the menu sections are plain headings (no fold, no chevron;
  `expanded=True`). A test refuses any font size outside the scale.

### Added (cabinet v2)
- The profile became a **cabinet of five pages** under a menu grouped by what you do: Для мене, Збережені,
  Профіль, Навчання, Практика. The sidebar cannot be collapsed and carries a **pixel frog** (a tadpole that
  grows into a king of frogs, six moods) with a level, experience bar, streak and the questions due.
- **Learning resources** for about 45 skills (links checked when written), with a "finished" tick; the
  trainer can be aimed at one skill; experience, levels, a streak, ten achievements and "what to do next".
- Smoother: the question card and the breakdown panels are fragments (a click redraws only them), a rerun
  no longer dims the page, entrances are shorter.

### Fixed
- Hot reload did not work for modules inside a package: `from jobmarket import dashboard_ui` read the
  package attribute, which still held the old module. Both are dropped now (a regression test uses a real
  package).

### Added (profile)
- **Профіль** page: skills you know and learn, a target, vacancies ranked by how well they fit (with what is
  missing and a readiness figure), saved vacancies with a stage and a note, a learning plan ordered by what
  completes the most vacancies, and an **interview trainer** (60 questions for 12 skills, Leitner boxes). A
  saved vacancy and its fit with the profile are also available in the catalog; the home page shows a
  profile strip. Everything lives in a local JSON file (`data/profile/`, git-ignored, written atomically).

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
