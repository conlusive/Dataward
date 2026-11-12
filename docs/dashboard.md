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

Eleven pages in a sidebar under the pixel logo, grouped by what you are doing: Головна, Вакансії
(Каталог, Для мене, Збережені), Розвиток (Навчання, Практика), Аналітика, Система. The sidebar is part of
the layout and cannot be collapsed; **the menu scrolls on its own and the avatar stays pinned below it**, so
no page is out of reach on a short window. **You are the avatar at its foot** (the frog in a frame, a name, a level bar): the whole card opens the profile, so
there is no "Профіль" in the menu (the page exists; its menu link is hidden). Tabs inside a page split one
topic into views. Filters live on the page, in a bar above the list, never in the sidebar.

| Page | Tabs | Shows | Reads |
|---|---|---|---|
| Головна | - | a header with a typed line; four bracketed figures; **Сьогодні**: up to three things to do now (coloured by where they lead) and two rings, the daily goal and readiness; **Ринок зараз**: the breakdown panel (thin stacked bars per day) beside a ring of the market that you switch between source, level and direction; the four biggest **directions** as tiles with a button that opens their vacancies; the top-10 skills and what changed; the three freshest vacancies (with a catalog); **Конвеєр даних**: the health chip, the last runs as squares, when the data was exported, DQ checks passed, SLOs kept, rows in silver | `fct_market_daily`, `fct_skill_demand_monthly`, `dim_skill`, `status.json`, `last_update.json`, the catalog |
| Каталог | Вакансії / Що вимагають / Компанії | **the vacancies themselves**: a filter bar (search, direction, skills, level and source as pills, and a "Ще фільтри" popover with all/any skills, only open, only with a salary, minimum salary, remote, when it appeared; the popover title counts what is changed), four tiles describing the selection, a **list with the vacancy already open beside it** (rows on the left, 15 a page with a pager, each row two lines: title, then company, level, salary and fit; the first vacancy is open at once and a click on a row opens another; no table to click into), the open vacancy's card with the market comparison and a save button, "save the whole page" (all skills, required ones marked, dates, both links when it is on both sites), what the selection asks for, which companies hire, a CSV download | `fct_vacancy_catalog` (local only) |
| Для мене | - | the open vacancies that suit your target, ranked by how well your skills cover them (a required skill counts twice), with what you have and what is missing, a readiness figure, a minimum-match slider and a card with a save button | the catalog, the profile |
| Збережені | - | saved vacancies by stage (збережено, відгукнувся, співбесіда, оффер, відмова) with a note, edited in a table | the profile |
| Профіль (the avatar) | - | **your frog**, its level and experience, the streak, a 20-week **activity grid**, what to do next, achievements, and the settings: skills you know and learn, a target (direction, level, minimum salary, remote), a daily goal | the profile file, `dim_skill`, `fct_market_daily` |
| Навчання | - | skills you are learning with their progress, the plan ("what completes the most vacancies") and **learning resources** for any skill, with a "finished" tick | the profile, the catalog, `learning_resources.yaml` |
| Практика | - | the interview trainer: a session of questions with a reacting frog, and your progress by skill | the profile, `interview_questions.yaml` |
| Ринок | Динаміка / Категорії / Рівні / Таблиця | the same tiles for the filtered slice (source, category, level), a line per source, new vs closed per day, ranked bars, and the rows as a table with a CSV download | `fct_market_daily` |
| Навички | Рейтинг / Навичка / Стеки | a searchable, sortable ranking (share, how often a hard requirement, change against the previous month in percentage points, declared salary) with a CSV download; one skill with its trend, salary and related skills; the stack clusters and a graph of one of them | demand, `dim_skill`, `fct_skill_pairs`, `fct_salary_by_skill`, `skill_clusters` |
| Зарплати | Калькулятор / Орієнтири DOU / За навичками / Тривалість вакансій | the model's p10-p50-p90 for a profile; the survey's median by year with its p25-p75 band; declared salaries by skill; how long a vacancy stays open | `salary_model_grid` (optional), `fct_salary_survey`, `fct_salary_by_skill`, `fct_vacancy_lifetime` |
| Стан системи | Стан / Перевірки / Скрапінг / Про дані | health in one line, SLOs, recent runs, quality checks, scraping errors, volumes, the export's time and tables, sources and limitations | `status.json`, `last_update.json` |

## The vacancy catalog is public

`fct_vacancy_catalog` has one row per real vacancy (the same job on DOU and Djinni is one row): title,
company, direction (category), level, salary, place, skills (all, and the required ones), dates, open or
closed, and the link to the original page. It has **no description text and no contacts** on purpose: the
listings belong to their authors, so the page shows only what is needed to find and filter them and the
link leads to the original. The catalog page says so under its heading.

It is published like every other mart: the nightly workflow runs `jobmarket export-public`, which copies
the export to `data/export_public` without any table flagged `meta.private` in
`warehouse/models/marts/schema.yml` (none is at the moment, and `tests/test_export.py` tests the copy
with a synthetic one), and uploads only that copy; `publish-data` puts it on the `data` branch that the
public site reads. An export from before the catalog was built says so on the page instead of failing
(`make pipeline` locally builds it).

A vacancy that is gone from the source is marked closed and is hidden by the default "only open"
filter; closed ones stay in the catalog (the market history needs them) with the same fields.

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

## Keyboard

Shortcuts exist but are not printed on the pages: `?` lists them, `Ctrl K` (`⌘ K`) opens a palette.

| Keys | Does |
|---|---|
| `g` then a letter | go to a page: `h` Головна, `c` Каталог, `f` Для мене, `b` Збережені, `u` Профіль, `l` Навчання, `p` Практика, `m` Ринок, `s` Навички, `w` Зарплати, `d` Стан системи |
| `/` | focus the search field of the page |
| `Ctrl K` | the palette: type a part of a page name, arrows and Enter |
| `Space`, `1` `2` `3` | trainer: reveal the answer, then "Знаю", "Частково", "Не знаю" |
| `z` / `Ctrl Z` | take back the last action (see below) |
| `Esc` | close the window, or leave a field |

The table lives in `dashboard_keys.py` and the script is generated from it (`st.html` with
`unsafe_allow_javascript`); it clicks the sidebar links and the trainer's buttons, so it knows nothing
about Streamlit's routing. Keys are matched by position (`KeyboardEvent.code`), so they work in the
Ukrainian layout. A test keeps the table equal to the menu and checks the script with `node --check`.

## Taking an action back

Every change to the profile that you make by hand (saving vacancies, editing the saved ones, ticking
plan or material marks, the profile form) keeps the state before it. A slim bar over the page says
"↶ Збережено вакансій: 15" with a **Скасувати** button (or press `z`); each press undoes one action, the
newest first, up to 20 actions and for three minutes. Routine writes (a trainer answer) and writes that
change nothing are not offered. The undo restores the file as it was, so XP, streak and the saved list go
back together. Nothing is kept on disk besides the profile itself.

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
- **Pixel and terminal**: Tektur (angular and technical, not pixelated, good Cyrillic) for headings,
  figures and labels,
  JetBrains Mono for text and tables. Corners are stepped (a CSS clip), a page starts with a prompt
  (`$ вакансії · каталог`) and a blinking cursor after the title (switched off by `prefers-reduced-motion`),
  section labels read `// ВИБІРКА`, the open tab has an arrow. The fonts come from Google Fonts, and the
  browser falls back to its own monospace font offline. Pixelify Sans (crude Cyrillic) and Tiny5 (read as too pixelated) were tried and
  dropped.
- **Logo**: three rising pixel bars, then DATAWARD spelled in a 5x7 pixel font with a pixel shadow, and a
  static terracotta full stop; the sidebar icon and the favicon are the bars and the stop. `dashboard_logo.py` draws them from a glyph
  table (`python -m jobmarket.dashboard_logo` rewrites `dashboard/static/`), and a test keeps the committed
  files equal to its output.
- **Motion**: a page arrives **once, as a whole**. When the address changes, `dashboard_motion.py` hides
  the page body (`html.dw-go` is taken away; the stylesheet hides the body from the very first paint
  too), waits until the run has finished (the app's own script state) and the page has stopped changing (lazy widgets and charts mount after
  the run; at most 1.7 s, and the stylesheet frees the body after 2 s even if the script fails),
  shows it at once with no fade (a fade made the whole page its own layer and flickered when it ended), then switches `html.dw-enter` on for 2.8 s: the meters grow and the subtitle of the
  home page types itself. Nothing rises or is staggered per element, so the building of a page is never
  seen. A rerun after a click plays none of it (a test refuses an arrival animation outside
  `html.dw-enter`). Only a state moves by itself: the frog, the newest pipeline square and the title
  cursor. All of it stops for `prefers-reduced-motion`.
- **Tabs build only the open one** (the page "Навички"): `st.tabs(..., on_change="rerun")` and
  `if tab.open:`, so a hidden table or graph is never drawn. Their widgets keep their values through
  `ui.keep(...)`, because Streamlit forgets a widget it did not draw.
- **A phone** (`_PHONE` in the theme, `dashboard_mobile.py`): Streamlit shows the sidebar as a drawer below
  768 px and stacks columns below 640 px; the stylesheet only adjusts what is too big. The drawer is closed
  by a small script once per page load and its buttons are hidden only above 768 px. Figures go two to a
  row, the filter bar of the catalog is two columns wide, the pills wrap. On the list of vacancies a tapped
  row gives its "back" button the key `*_close_open`, and the stylesheet lays the card (`:has()` on that
  key, phone only) over the screen; the card itself keeps its key, so a click does not mount it anew.
- **The tab icon** (`dashboard_icon.py`): the page ships Streamlit's own `favicon.png` and swaps it for
  `page_icon` after load, as a JPEG; Chrome follows, Safari keeps what it read at load. So the container
  image overwrites Streamlit's `favicon.png` with ours (`Dockerfile.dashboard`), and a script does the
  same for a local run: it removes the icon links and adds a PNG one and an `apple-touch-icon` from
  `/app/static` (`enableStaticServing`). The address carries a hash of the icon. `page_icon` is not set.
- **Colour by part of the product**: vacancies teal, learning (Розвиток) violet, analytics red, the state of
  the system yellow; they colour the heading marks, the menu bars and the actions (`DOMAINS` in the theme;
  a test keeps the hues). These are not the chart series colours.
- **Smooth on a small machine**: no selector that rescans every wrapper (`:has()` over all containers), no
  entrance animation, progress rings are CSS (a conic gradient) instead of charts, one ring of the market
  at a time (a radio, not three tabs that would all draw), and the toolbar over tables and charts (full
  screen, search, download) is hidden everywhere. Where a download makes sense there is a button.
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
- `src/jobmarket/dashboard_charts.py`: the charts, each taking a frame with fixed column names: lines, ranked
  and stacked bars, **donut** and **ring** (parts of a whole, one value), the **activity grid**.
- `src/jobmarket/dashboard_keys.py`: the shortcut table and the script generated from it.
- `src/jobmarket/dashboard_motion.py`: the script that plays the arrival once per page.
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

## Public hosting (Render)

Streamlit is a long-running server with WebSockets, so it needs a host that runs a container (not a
serverless platform such as Vercel). `render.yaml` is a Render Blueprint for the image of
`Dockerfile.dashboard`:

- **Data.** The nightly workflow (`publish-data` in `pipeline-daily.yml`, its own job, the only one
  with a write token) force-pushes the *public* export, the artifact already stripped of third-party
  listings, to the `data` branch. `jobmarket.dashboard_sync` downloads that branch as an archive and
  writes only the files the archive's own `last_update.json` names (plus `status.json`). It runs at
  build time, so the image holds the export of its build and a start needs no download; a running
  server refreshes it a minute after the first visit and every 20 minutes; at a start, data older than two hours is fetched before serving (a host that slept, an old image). A failed download keeps the old
  files. `DASHBOARD_DATA_URL` is the archive URL (Render passes its env vars to the build as well);
  unset, nothing is fetched, and `scripts/dashboard-start.sh` fetches only if the image has no data.
- **The public copy shows the market and the vacancies, not a person.** On Render
  (`DASHBOARD_PROFILE=session`) the menu is Головна, Вакансії (Каталог), Аналітика (Ринок, Навички,
  Зарплати) and Стан системи. The pages about you (Профіль, Навчання, Практика, Для мене, Збережені), the
  avatar, the undo bar and the "Сьогодні" block do not exist there: they are not hidden but not registered,
  so their URLs do not open, and the shortcuts and the palette do not offer them. The vacancy list is
  there without a profile: no match with your skills and no save button. Run it on your own machine for
  the whole product.
- **Start time.** A cold start on the free plan (a tenth of a CPU) is mostly Python importing. The
  packages belong to root and the server runs as `app`, which cannot write `.pyc` files, so the image
  compiles bytecode at build time (`UV_COMPILE_BYTECODE`, `compileall`); without it every start compiled
  streamlit, pandas and altair again. The file watcher is off.
- **Profiles.** `DASHBOARD_PROFILE=session` is also the storage rule: should a profile ever be created on
  the public copy it lives in the visitor's session and never in the server's file, because one file on a
  shared server would be one profile for everybody. Today nothing on the public copy creates one.
- **Free plan.** The service sleeps after about 15 minutes without a visit and wakes in under a
  minute; it has 512 MB of memory.

Set up once: merge to `main`, publish the first `data` branch (run the workflow, or push the public
export yourself), then on Render: New > Blueprint > this repository.

## Not here yet

- **Other hosts**: Streamlit Community Cloud and the Hugging Face mirror (see "Public hosting" for Render).
- **English UI**: only Ukrainian for now.
