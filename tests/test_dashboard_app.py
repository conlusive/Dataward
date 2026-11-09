"""Runs every dashboard page headlessly on the made-up export and checks what it shows.

Pages are opened through the entry point (``app.py`` + ``switch_page``): the home page links to the
others, and that only works inside the navigation.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402  (after the skip on purpose)

from jobmarket import dashboard_profile as pr  # noqa: E402
from tests.dashboard_fixtures import write_catalog, write_export  # noqa: E402

ROOT = Path(__file__).parent.parent / "dashboard"
PAGES = [
    "home", "catalog", "fit", "saved", "profile", "learn", "practice", "market", "skills", "salary",
    "system",
]  # fmt: skip
NBSP = " "  # thousands are separated by a no-break space


@pytest.fixture
def export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = write_export(tmp_path / "export")
    monkeypatch.setenv("DASHBOARD_DATA_DIR", str(directory))
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile" / "profile.json"))  # never yours
    return directory


@pytest.fixture
def with_catalog(export: Path) -> Path:
    """The export of a machine that built the catalog (it is local-only data)."""
    write_catalog(export)
    return export


def _run(page: str) -> AppTest:
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    if page != "home":
        app = app.switch_page(f"views/{page}.py").run()
    assert not app.exception, app.exception
    return app


def _metrics(app: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in app.metric}


def _markdown(app: AppTest) -> str:
    return "\n".join(m.value for m in app.markdown)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_with_a_title_and_without_an_error(export: Path, page: str) -> None:
    app = _run(page)

    assert not app.error and '<h1 class="dw-title">' in _markdown(app)


def test_the_app_starts_on_the_home_page(export: Path) -> None:
    app = _run("home")

    assert "Ринок праці IT·UA" in _markdown(app)


# ---- home -------------------------------------------------------------------------------------
def test_home_shows_the_latest_day_as_bracketed_figures(export: Path) -> None:
    html = _markdown(_run("home"))

    assert "<em>Відкрито:</em><b>17</b>" in html
    assert "<em>Нових за день:</em><b>3</b>" in html
    assert "<em>Закрито за день:</em><b>2</b>" in html
    assert "<em>Джерел:</em><b>2</b>" in html


def test_home_says_the_pipeline_has_remarks_when_a_check_warns(export: Path) -> None:
    html = _markdown(_run("home"))

    assert "Є зауваження" in html  # a chip in the header
    assert html.count('class="dw-pulse"') == 1  # and the squares of the last runs


def test_home_splits_the_market_by_the_chosen_metric_and_cut(export: Path) -> None:
    app = _run("home")

    app.selectbox(key="home_metric").select("Нові").run()
    app.selectbox(key="home_split").select("Напрямок").run()

    assert not app.exception


def test_home_offers_the_biggest_directions_with_a_button_each(export: Path) -> None:
    app = _run("home")

    html = _markdown(app)
    assert 'dw-dir-name">Python<' in html and 'dw-dir-name">QA<' in html
    assert [b.label for b in app.button if b.key and b.key.startswith("dir_")] == [
        "Розріз →",
        "Розріз →",
    ]  # without a catalog a direction opens the market, not the catalog


def test_with_a_catalog_a_direction_opens_the_vacancies(with_catalog: Path) -> None:
    app = _run("home")

    labels = [b.label for b in app.button if b.key and b.key.startswith("dir_")]
    assert labels == ["Вакансії →", "Вакансії →"]
    assert "dw-dir-chips" in _markdown(app) or "dw-chip" in _markdown(app)  # top skills shown


def _only_the_first_day(export: Path) -> None:
    import duckdb

    path = export / "fct_market_daily.parquet"
    duckdb.connect().execute(
        f"COPY (SELECT * FROM '{path}' WHERE date = DATE '2026-11-01') TO '{path}.one' "
        "(FORMAT parquet)"
    )
    (export / "fct_market_daily.parquet.one").replace(path)


def test_on_the_first_day_of_data_the_page_explains_why_everything_is_new(export: Path) -> None:
    _only_the_first_day(export)

    app = _run("home")

    assert any("перший день спостереження" in c.value for c in app.caption)


def test_from_the_second_day_on_there_is_no_such_note(export: Path) -> None:
    app = _run("home")

    assert not any("перший день спостереження" in c.value for c in app.caption)


def test_a_missing_data_directory_is_a_message_not_a_stack_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHBOARD_DATA_DIR", str(tmp_path / "nothing"))

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()

    assert not app.exception and "Немає даних" in app.error[0].value


# ---- market -----------------------------------------------------------------------------------
def test_the_filters_change_the_market_numbers(export: Path) -> None:
    app = _run("market")
    assert _metrics(app)["01 · Відкриті вакансії"] == "17"

    app.session_state["mk_sources"] = ["dou"]
    app.run()

    assert _metrics(app)["01 · Відкриті вакансії"] == "12"


def test_an_active_filter_is_shown_as_a_tag_and_an_idle_page_says_none_is_set(
    export: Path,
) -> None:
    app = _run("market")
    assert "фільтри не задано" in _markdown(app)

    app.session_state["mk_sources"] = ["dou"]
    app.run()

    assert "Джерело: dou" in _markdown(app)
    assert any(b.label == "Скинути фільтри" for b in app.button)


def test_the_market_reset_button_clears_the_filters(export: Path) -> None:
    app = _run("market")
    app.session_state["mk_sources"] = ["dou"]
    app.run()

    next(b for b in app.button if b.label == "Скинути фільтри").click().run()

    assert _metrics(app)["01 · Відкриті вакансії"] == "17" and "фільтри не задано" in _markdown(app)


def test_a_filter_with_no_vacancies_says_so_instead_of_showing_empty_charts(export: Path) -> None:
    app = _run("market")

    app.session_state["mk_sources"] = ["dou"]
    app.multiselect(key="mk_cats").select("QA").run()  # category QA on DOU: there is none

    assert not app.exception and "вакансій немає" in app.info[0].value


def test_the_market_breakdown_follows_the_chosen_metric_and_cut(export: Path) -> None:
    app = _run("market")

    app.selectbox(key="mk_metric").select("Закриті").run()
    app.selectbox(key="mk_split").select("Рівень").run()

    assert not app.exception


def test_the_market_table_lists_the_filtered_rows(export: Path) -> None:
    app = _run("market")

    app.session_state["mk_sources"] = ["djinni"]
    app.run()

    table = app.dataframe[-1].value
    assert set(table["Джерело"]) == {"djinni"} and len(table) == 2


# ---- skills -----------------------------------------------------------------------------------
def test_the_ranking_lists_every_skill_with_its_change_and_salary(export: Path) -> None:
    app = _run("skills")

    table = app.dataframe[0].value

    assert table["Навичка"].tolist() == ["Django", "Docker", "Python", "SQL"]
    python = table[table["Навичка"] == "Python"].iloc[0]
    assert python["Частка вакансій, %"] == 66.7 and python["Зміна, п. п."] == pytest.approx(
        16.7, abs=0.1
    )
    assert python["Медіана вилки, USD"] == 3000


def test_the_ranking_can_be_searched_and_filtered_by_group(export: Path) -> None:
    app = _run("skills")

    app.text_input(key="rank_query").input("sql").run()
    assert app.dataframe[0].value["Навичка"].tolist() == ["SQL"]

    app.text_input(key="rank_query").input("").run()
    app.multiselect(key="rank_groups").select("devops").run()
    assert app.dataframe[0].value["Навичка"].tolist() == ["Docker"]


def test_a_search_that_matches_nothing_says_so(export: Path) -> None:
    app = _run("skills")

    app.text_input(key="rank_query").input("zzz").run()

    assert any("навичок немає" in i.value for i in app.info)


def test_the_skill_page_shows_demand_salary_and_relations(export: Path) -> None:
    app = _run("skills")

    app.selectbox(key="skill_name").select("Python").run()

    metrics = _metrics(app)
    assert metrics["01 · Частка вакансій"] == "66.7%"
    assert metrics["03 · Медіана вилки, USD/міс"] == f"3{NBSP}000"
    assert any(len(d.value) == 1 for d in app.dataframe)  # the related skills of Python: SQL


def test_a_skill_without_enough_salaries_says_so(export: Path) -> None:
    app = _run("skills")

    app.selectbox(key="skill_name").select("SQL").run()

    assert any("Замало вакансій" in i.value for i in app.info)


def test_the_stacks_tab_has_a_slider_and_survives_moving_it(export: Path) -> None:
    app = _run("skills")

    app.slider(key="stack_npmi").set_value(0.9).run()

    assert not app.exception


def test_a_threshold_that_keeps_a_link_draws_the_graph_without_the_empty_note(
    export: Path,
) -> None:
    app = _run("skills")

    app.slider(key="stack_npmi").set_value(0.95).run()  # django-docker (1.0) stays

    assert not app.exception and not any("зв'язків немає" in i.value for i in app.info)


# ---- salary -----------------------------------------------------------------------------------
def test_the_salary_page_shows_the_survey_for_the_chosen_role(export: Path) -> None:
    app = _run("salary")

    app.selectbox(key="survey_role").select("qa").run()

    assert _metrics(app)["02 · Медіана"] == f"3{NBSP}000"


def test_without_a_trained_model_the_calculator_says_how_to_get_one(export: Path) -> None:
    app = _run("salary")

    assert any("make train" in i.value for i in app.info)


def test_the_calculator_shows_the_models_range_for_the_chosen_profile(export: Path) -> None:
    from tests.dashboard_fixtures import write_grid

    write_grid(export)
    app = _run("salary")

    app.slider(key="calc_experience").set_value(5.0)
    app.selectbox(key="calc_english").select("upper-intermediate")
    app.run()

    metrics = _metrics(app)
    assert metrics["01 · Нижня межа (p10), USD/міс"] == f"2{NBSP}000"
    assert metrics["02 · Типова (p50), USD/міс"] == f"3{NBSP}300"
    assert metrics["03 · Верхня межа (p90), USD/міс"] == f"4{NBSP}800"
    assert any(
        "1245" in c.value and "1405" in c.value for c in app.caption
    )  # model vs baseline error


# ---- system -----------------------------------------------------------------------------------
def test_the_system_page_counts_the_checks_that_need_attention(export: Path) -> None:
    assert _metrics(_run("system"))["01 · Перевірок, що потребують уваги"] == "1"


def test_the_slo_table_marks_each_state_with_an_icon_and_a_word(export: Path) -> None:
    slo = _run("system").dataframe[0].value

    assert slo["стан"].tolist() == ["✓ виконано", "… замало даних"]


def test_the_about_tab_gives_the_update_time(export: Path) -> None:
    assert "2026-11-09T04:15:00" in _markdown(_run("system"))


# ---- the vacancy catalog ----------------------------------------------------------------------
def _found(app: AppTest) -> str:
    return _metrics(app)["01 · Знайдено"]


def _titles(app: AppTest) -> list[str]:
    return list(app.dataframe[0].value["Назва"])


def test_without_a_catalog_the_page_explains_why_and_how_to_get_one(export: Path) -> None:
    app = _run("catalog")

    assert any("навмисно" in i.value and "make pipeline" in i.value for i in app.info)
    assert not app.metric  # nothing to count


def test_the_catalog_opens_on_the_open_vacancies_newest_first(with_catalog: Path) -> None:
    app = _run("catalog")

    assert _found(app) == "5"  # v4 is closed
    assert _titles(app) == [
        "DevOps Engineer", "Senior Python Developer", "Middle Python Engineer",
        "QA Automation Engineer", "Product Manager",
    ]  # fmt: skip


def test_the_sample_is_described_by_its_salaries_and_novelty(with_catalog: Path) -> None:
    metrics = _metrics(_run("catalog"))

    assert metrics["02 · З вилкою"] == "3"
    assert metrics["03 · Медіана вилки"] == f"3{NBSP}750"  # middles of 3 750, 2 000 and 6 000
    assert metrics["04 · Нові за 7 днів"] == "3"


def test_the_search_filters_by_title_or_company(with_catalog: Path) -> None:
    app = _run("catalog")

    app.text_input(key="cat_q").input("python").run()
    assert _titles(app) == ["Senior Python Developer", "Middle Python Engineer"]

    app.text_input(key="cat_q").input("acme").run()
    assert _titles(app) == ["Senior Python Developer", "QA Automation Engineer"]


def test_closed_vacancies_come_back_when_the_open_filter_is_off(with_catalog: Path) -> None:
    app = _run("catalog")

    app.toggle(key="cat_open").set_value(False).run()

    assert _found(app) == "6" and "Junior Java Developer" in _titles(app)


def test_skills_are_required_together_or_one_of(with_catalog: Path) -> None:
    app = _run("catalog")

    app.multiselect(key="cat_skills").set_value(["Docker", "Python"]).run()
    assert _titles(app) == ["DevOps Engineer", "Senior Python Developer"]

    app.radio(key="cat_skill_mode").set_value("будь-яка").run()
    assert _found(app) == "4"


def test_direction_level_and_salary_filters_combine(with_catalog: Path) -> None:
    app = _run("catalog")

    app.session_state["cat_levels"] = ["senior"]
    app.toggle(key="cat_remote").set_value(True).run()
    app.slider(key="cat_min_salary").set_value(5000).run()

    assert _titles(app) == ["DevOps Engineer"]


def test_a_filter_that_matches_nothing_says_so(with_catalog: Path) -> None:
    app = _run("catalog")

    app.text_input(key="cat_q").input("zzz").run()

    assert not app.exception and any("вакансій немає" in i.value for i in app.info)


def test_the_reset_button_clears_every_filter(with_catalog: Path) -> None:
    app = _run("catalog")
    app.text_input(key="cat_q").input("python").run()
    app.toggle(key="cat_open").set_value(False).run()
    app.multiselect(key="cat_dirs").set_value(["QA"]).run()

    next(b for b in app.button if b.label == "Скинути").click().run()

    assert _found(app) == "5" and app.text_input(key="cat_q").value == ""
    assert app.multiselect(key="cat_dirs").value == [] and app.toggle(key="cat_open").value


def test_the_selection_tabs_show_what_the_sample_asks_for_and_who_hires(
    with_catalog: Path,
) -> None:
    app = _run("catalog")

    assert [t.label for t in app.tabs] == ["Вакансії", "Що вимагають", "Компанії"]
    assert not app.exception


def test_the_catalog_can_be_downloaded_as_a_table_of_what_is_shown(with_catalog: Path) -> None:
    app = _run("catalog")

    app.text_input(key="cat_q").input("python").run()

    table = app.dataframe[0].value
    assert list(table["Посилання"]) == ["https://example.com/v1", "https://example.com/v2"]


def test_home_lists_the_freshest_open_vacancies_as_tiles_when_there_is_a_catalog(
    with_catalog: Path,
) -> None:
    app = _run("home")

    html = _markdown(app)
    assert "Свіжі вакансії" in html and html.count('class="dw-vac"') == 3  # one row, no more
    assert html.index("DevOps Engineer") < html.index("Senior Python Developer")  # newest first
    assert len(app.get("link_button")) == 3


def test_home_without_a_catalog_has_no_vacancy_list(export: Path) -> None:
    assert "Свіжі вакансії" not in _markdown(_run("home"))


def _card(tmp_path: Path, position: int) -> AppTest:
    def script(directory: str, index: int) -> None:
        from pathlib import Path

        from jobmarket import dashboard_data as dd
        from jobmarket import dashboard_ui as ui

        frame = dd.read_catalog(Path(directory))
        assert frame is not None
        ui.vacancy_card(frame.iloc[index])

    write_catalog(tmp_path)
    return AppTest.from_function(script, args=(str(tmp_path), position), default_timeout=60).run()


def test_a_vacancy_card_gives_the_link_and_marks_the_required_skills(tmp_path: Path) -> None:
    app = _card(tmp_path, 0)  # v1: a salary range, Python and Django required

    assert not app.exception
    html = _markdown(app)
    assert "Senior Python Developer" in html and "3\u00a0000–4\u00a0500 $" in html
    assert '<span class="dw-chip req">Python</span>' in html
    assert '<span class="dw-chip">Docker</span>' in html
    assert len(app.get("link_button")) == 1


def test_a_missing_second_link_is_not_mistaken_for_a_link(tmp_path: Path) -> None:
    """Regression: a missing link is NaN, which is truthy, and a button was built from it."""
    app = _card(tmp_path, 2)  # v3 has no second link

    assert not app.exception and len(app.get("link_button")) == 1
    assert "ще одне оголошення" not in _markdown(app)


def test_a_vacancy_on_both_sites_offers_both_links(tmp_path: Path) -> None:
    app = _card(tmp_path, 1)  # v2 is on both sites

    assert len(app.get("link_button")) == 2 and "ще одне оголошення" in _markdown(app)


def test_a_vacancy_card_is_escaped(tmp_path: Path) -> None:
    def script(directory: str) -> None:
        from pathlib import Path

        from jobmarket import dashboard_data as dd
        from jobmarket import dashboard_ui as ui

        frame = dd.read_catalog(Path(directory))
        assert frame is not None
        row = frame.iloc[0].copy()
        row["title"] = "<script>alert(1)</script>"
        row["skills"] = ["<b>x</b>"]
        ui.vacancy_card(row)

    write_catalog(tmp_path)
    app = AppTest.from_function(script, args=(str(tmp_path),), default_timeout=60).run()

    assert "<script>" not in _markdown(app) and "<b>x</b>" not in _markdown(app)


def test_the_catalog_names_its_active_filters(with_catalog: Path) -> None:
    app = _run("catalog")
    assert "Статус: відкриті" in _markdown(app)  # the default is itself a filter, so it is shown

    app.text_input(key="cat_q").input("python").run()
    app.toggle(key="cat_open").set_value(False).run()

    html = _markdown(app)
    assert "Пошук: python" in html and "Статус: відкриті" not in html


def test_the_catalog_source_filter_is_a_set_of_pills(with_catalog: Path) -> None:
    app = _run("catalog")

    app.session_state["cat_sources"] = ["djinni"]
    app.run()

    assert _titles(app) == ["Middle Python Engineer"]  # v4 is djinni too but closed
    assert "Джерело: djinni" in _markdown(app)


# ---- the profile ------------------------------------------------------------------------------
def _saved_profile(**changes: object) -> pr.Profile:
    profile = pr.Profile(**changes)  # type: ignore[arg-type]
    pr.save(profile)
    return profile


def _today() -> str:
    return date.today().isoformat()


def test_a_new_profile_is_filled_in_with_a_form_and_kept_in_a_file(export: Path) -> None:
    app = _run("profile")

    app.text_input(key="pf_name").input("Ярослав")
    app.multiselect(key="pf_know").set_value(["Python", "SQL"])
    app.multiselect(key="pf_learning").set_value(["Docker"])
    app.selectbox(key="pf_level").select("middle")
    app.number_input(key="pf_goal").set_value(8)
    next(b for b in app.button if b.label == "Зберегти профіль").click().run()

    saved = pr.load()
    assert saved.name == "Ярослав" and saved.known() == {"Python", "SQL"}
    assert saved.learning() == {"Docker"} and saved.level == "middle" and saved.goal == 8
    assert "Профіль збережено" in "".join(s.value for s in app.success)
    assert "<em>Знаю:</em><b>2</b>" in _markdown(app)


def test_a_skill_the_taxonomy_no_longer_lists_survives_saving_the_form(export: Path) -> None:
    _saved_profile(skills={"Забутий": "know", "Python": "know"})
    app = _run("profile")

    app.multiselect(key="pf_know").set_value(["Python", "SQL"])
    next(b for b in app.button if b.label == "Зберегти профіль").click().run()

    assert pr.load().known() == {"Забутий", "Python", "SQL"}


def test_a_profile_that_cannot_be_written_says_so_instead_of_crashing(
    export: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run("profile")

    def refuse(*_: object, **__: object) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(pr, "save", refuse)
    next(b for b in app.button if b.label == "Зберегти профіль").click().run()

    assert not app.exception and any("read-only" in e.value for e in app.error)


def test_a_new_profile_has_a_tadpole_and_asks_for_skills_first(export: Path) -> None:
    html = _markdown(_run("profile"))

    assert "Пуголовок · <b>рівень 1</b>" in html and 'class="dw-frog dw-frog-idle"' in html
    assert "Досягнення" in html and "Перший крок" in html and 'class="dw-medal on"' not in html


def test_the_profile_shows_the_streak_and_lights_the_medals_that_were_earned(export: Path) -> None:
    days = {(date.today() - timedelta(days=n)).isoformat(): 5 for n in range(3)}
    _saved_profile(skills={"Python": "know"}, activity=days)

    html = _markdown(_run("profile"))

    assert "серія: 3 дн." in html and 'class="dw-medal on"' in html
    assert 'class="dw-frog dw-frog-party"' in html  # five answers today meet the goal of five


def test_the_frog_is_in_the_sidebar_on_every_page(export: Path) -> None:
    for page in ("home", "market", "learn"):
        app = _run(page)
        assert any("dw-avatar" in m.value and "dw-frog" in m.value for m in app.sidebar.markdown), (
            page
        )


def test_the_sidebar_cannot_be_collapsed() -> None:
    from jobmarket import dashboard_theme as theme

    assert "stSidebarCollapseButton" in theme.css() and "display: none" in theme.css()


def test_home_asks_an_empty_profile_for_skills_and_then_tracks_the_day(export: Path) -> None:
    assert "Додайте навички" in _markdown(_run("home"))

    _saved_profile(skills={"Python": "know", "SQL": "know", "Docker": "learning"})
    html = _markdown(_run("home"))

    assert "Додайте навички" not in html
    assert "<em>Рівень:</em>" not in html  # the level lives in the avatar, not twice on the page


def test_home_shows_the_goal_of_the_day_as_a_ring(export: Path) -> None:
    app = _run("home")

    assert any("ціль дня: 0/5" in c.value for c in app.caption)


def test_home_shows_the_market_as_rings_per_source_level_and_direction(export: Path) -> None:
    app = _run("home")

    assert [t.label for t in app.tabs if t.label in {"Джерела", "Рівні", "Напрямки"}] == [
        "Джерела",
        "Рівні",
        "Напрямки",
    ]


def test_home_shows_the_pipeline_behind_the_numbers(export: Path) -> None:
    html = _markdown(_run("home"))

    assert "Конвеєр даних" in html
    assert "<em>Перевірки DQ:</em><b>1/2</b>" in html  # one check passed, one warns
    assert "<em>SLO:</em><b>1/2</b>" in html  # the second one has too little data to say


# ---- vacancies for me -------------------------------------------------------------------------
def test_without_a_catalog_the_vacancy_pages_say_so(export: Path) -> None:
    for page in ("fit", "learn"):
        app = _run(page)
        assert any("каталог" in i.value for i in app.info), page


def test_vacancies_are_offered_by_how_well_they_fit(with_catalog: Path) -> None:
    _saved_profile(skills={"Python": "know"})
    app = _run("fit")

    metrics = _metrics(app)
    assert metrics["01 · Вакансій за ціллю"] == "5"
    assert metrics["02 · Найкращий збіг"] == "67%"
    assert metrics["03 · Готовність"] == "37%"
    jobs = app.dataframe[0].value
    assert jobs["Назва"].iloc[0] == "Middle Python Engineer" and jobs["Збіг, %"].iloc[0] == 67
    assert jobs["Бракує"].iloc[1] == "Django, Docker"  # the second best: Senior Python Developer


def test_the_match_floor_hides_the_weaker_vacancies(with_catalog: Path) -> None:
    _saved_profile(skills={"Python": "know"})
    app = _run("fit")

    app.slider(key="pf_floor").set_value(50).run()

    assert list(app.dataframe[0].value["Назва"]) == ["Middle Python Engineer"]


def test_without_known_skills_the_page_asks_for_them_before_matching(with_catalog: Path) -> None:
    assert any("навички, які ви вмієте" in i.value for i in _run("fit").info)


def test_the_target_narrows_the_offered_vacancies(with_catalog: Path) -> None:
    _saved_profile(skills={"Python": "know"}, category="QA")

    assert _metrics(_run("fit"))["01 · Вакансій за ціллю"] == "1"


def test_saved_vacancies_are_counted_by_stage(with_catalog: Path) -> None:
    profile = _saved_profile()
    pr.save_vacancy(profile, "v1", title="Dev", company="A", url="u", today=date(2026, 11, 1))
    pr.save_vacancy(profile, "v2", title="Dev 2", company="B", url="u", today=date(2026, 11, 2))
    pr.update_saved(profile, "v2", status="interview", note="")
    pr.save(profile)

    html = _markdown(_run("saved"))

    assert "<em>збережено:</em><b>1</b>" in html and "<em>співбесіда:</em><b>1</b>" in html
    assert "<em>оффер:</em><b>0</b>" in html


def test_with_nothing_saved_the_page_says_where_to_save(export: Path) -> None:
    assert any("Збережених вакансій ще немає" in i.value for i in _run("saved").info)


# ---- learning ---------------------------------------------------------------------------------
def test_the_learning_page_lists_curated_materials_even_without_a_catalog(export: Path) -> None:
    app = _run("learn")

    html = _markdown(app)
    assert "Матеріали" in html and 'class="dw-resource"' in html
    assert app.selectbox(key="learn_skill").value in app.selectbox(key="learn_skill").options


def test_a_skill_with_materials_shows_them_and_one_without_shows_search(export: Path) -> None:
    app = _run("learn")

    app.selectbox(key="learn_skill").select("Python").run()
    assert "Офіційний туторіал Python" in _markdown(app) and not any(
        "Добірки для цієї навички ще немає" in c.value for c in app.caption
    )

    assert "Docker: Get started" not in _markdown(app)
    app.selectbox(key="learn_skill").select("Docker").run()
    assert "Docker: Get started" in _markdown(app)


def test_a_finished_material_is_remembered_and_earns_experience(export: Path) -> None:
    app = _run("learn")
    app.selectbox(key="learn_skill").select("Python").run()

    app.checkbox(key="res_Python_0").check().run()

    done = pr.load().done
    assert list(done) == ["https://docs.python.org/3/tutorial/"] and list(done.values()) == [
        _today()
    ]
    app.checkbox(key="res_Python_0").uncheck().run()
    assert pr.load().done == {}  # the mark can be taken back


def test_a_skill_being_learned_shows_its_progress_and_can_be_declared_known(
    export: Path,
) -> None:
    _saved_profile(skills={"Python": "learning"})
    app = _run("learn")
    assert "матеріалів: 0 з 4" in " ".join(c.value for c in app.caption)

    app.button(key="fin_Python").click().run()

    assert pr.load().known() == {"Python"}
    assert "тепер серед ваших навичок" in "".join(s.value for s in app.success)


def test_the_plan_names_what_to_learn_and_how_many_vacancies_it_completes(
    with_catalog: Path,
) -> None:
    _saved_profile(skills={"Python": "know"})
    app = _run("learn")

    text = " ".join(c.value for c in app.caption)
    assert "5 відкритих вакансій" in text and "«Відкриває»" in text


# ---- practice ---------------------------------------------------------------------------------
def _finish_a_session(app: AppTest, size: int, rating: str = "know") -> None:
    app.radio(key="iv_scope").set_value("Усі питання")
    app.selectbox(key="iv_size").select(size)
    app.run()
    app.button(key="iv_start").click().run()
    for _ in range(size):
        app.button(key="iv_reveal").click().run()
        app.button(key=f"iv_rate_{rating}").click().run()


def test_a_practice_session_asks_reveals_rates_and_remembers(export: Path) -> None:
    app = _run("practice")
    app.radio(key="iv_scope").set_value("Усі питання")
    app.selectbox(key="iv_size").select(5)
    app.run()

    app.button(key="iv_start").click().run()
    assert "Питання 1 з 5" in _markdown(app) and 'class="dw-answer"' not in _markdown(app)

    app.button(key="iv_reveal").click().run()
    assert 'class="dw-answer"' in _markdown(app)
    assert {b.key for b in app.button if b.key and b.key.startswith("iv_rate_")} == {
        "iv_rate_know", "iv_rate_partial", "iv_rate_dont",
    }  # fmt: skip

    app.button(key="iv_rate_know").click().run()
    assert "Питання 2 з 5" in _markdown(app) and len(pr.load().practice) == 1


def test_the_frog_reacts_to_each_answer_and_celebrates_the_end(export: Path) -> None:
    app = _run("practice")
    app.radio(key="iv_scope").set_value("Усі питання")
    app.selectbox(key="iv_size").select(5)
    app.run()
    app.button(key="iv_start").click().run()

    for rating, mood in (("dont", "sad"), ("partial", "think"), ("know", "happy")):
        app.button(key="iv_reveal").click().run()
        app.button(key=f"iv_rate_{rating}").click().run()
        assert app.session_state["iv_mood"] == mood
        assert f"dw-frog-{mood}" in _markdown(app)


def test_a_finished_session_summarises_celebrates_and_counts_the_days_answers(
    export: Path,
) -> None:
    app = _run("practice")

    _finish_a_session(app, 5)

    html = _markdown(app)
    assert "Сесію завершено" in html and "<em>Знаю:</em><b>5</b>" in html
    assert "dw-frog-party" in html
    profile = pr.load()
    assert len(profile.practice) == 5 and {e["box"] for e in profile.practice.values()} == {2}
    assert profile.activity == {_today(): 5}  # the history behind the streak


def test_a_question_that_was_not_known_goes_back_to_the_first_box(export: Path) -> None:
    app = _run("practice")

    _finish_a_session(app, 5, rating="dont")

    assert {e["box"] for e in pr.load().practice.values()} == {1}


def test_a_second_session_the_same_day_asks_other_questions(export: Path) -> None:
    app = _run("practice")
    _finish_a_session(app, 5)
    first = set(pr.load().practice)

    again = _run("practice")
    _finish_a_session(again, 5)

    assert len(pr.load().practice) == 10 and not first & (set(pr.load().practice) - first)


def test_practice_by_my_skills_needs_skills_and_says_so(export: Path) -> None:
    app = _run("practice")

    assert any("немає навичок із питаннями" in i.value for i in app.info)
    assert app.button(key="iv_start").disabled


def test_practice_by_my_skills_asks_only_about_them(export: Path) -> None:
    _saved_profile(skills={"Python": "know"})
    app = _run("practice")
    app.selectbox(key="iv_size").select(5)
    app.run()

    app.button(key="iv_start").click().run()

    assert 'class="dw-q-meta">Python · ' in _markdown(app)


def test_practice_can_be_aimed_at_one_skill(export: Path) -> None:
    app = _run("practice")
    app.radio(key="iv_scope").set_value("Одна навичка").run()
    app.selectbox(key="iv_skill").select("Git").run()
    app.selectbox(key="iv_size").select(5)
    app.run()

    app.button(key="iv_start").click().run()

    assert 'class="dw-q-meta">Git · ' in _markdown(app)
    assert 'class="dw-q-meta">Python' not in _markdown(app)


# ---- a vacancy card with a profile ------------------------------------------------------------
def _card_with_profile(tmp_path: Path, index: int) -> AppTest:
    def script(directory: str, position: int) -> None:
        from pathlib import Path

        from jobmarket import dashboard_data as dd
        from jobmarket import dashboard_profile as pr
        from jobmarket import dashboard_ui as ui

        frame = dd.read_catalog(Path(directory))
        assert frame is not None
        ui.vacancy_card(frame.iloc[position], profile=pr.load())

    write_catalog(tmp_path)
    return AppTest.from_function(script, args=(str(tmp_path), index), default_timeout=60).run()


def test_a_vacancy_card_says_how_it_fits_the_profile_and_can_be_saved(
    tmp_path: Path, export: Path
) -> None:
    _saved_profile(skills={"Python": "know"})
    app = _card_with_profile(
        tmp_path / "c", 0
    )  # v1: Python, Django, Docker; Python, Django required

    assert "Збіг із вашим профілем: <b>40%</b>; бракує: Django, Docker" in _markdown(app)
    app.button(key="save_v1").click().run()

    saved = pr.load().saved
    assert list(saved) == ["v1"] and saved["v1"]["title"] == "Senior Python Developer"
    assert app.button(key="save_v1").disabled and app.button(key="save_v1").label == "✓ У профілі"


def test_a_vacancy_card_without_a_profile_has_no_save_button(tmp_path: Path, export: Path) -> None:
    app = _card(tmp_path / "plain", 0)

    assert not any(b.key and b.key.startswith("save_") for b in app.button)
