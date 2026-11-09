"""Runs every dashboard page headlessly on the made-up export and checks what it shows.

Pages are opened through the entry point (``app.py`` + ``switch_page``): the home page links to the
others, and that only works inside the navigation.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402  (after the skip on purpose)

from tests.dashboard_fixtures import write_export  # noqa: E402

ROOT = Path(__file__).parent.parent / "dashboard"
PAGES = ["home", "market", "skills", "salary", "system"]
NBSP = " "  # thousands are separated by a no-break space


@pytest.fixture
def export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = write_export(tmp_path / "export")
    monkeypatch.setenv("DASHBOARD_DATA_DIR", str(directory))
    return directory


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

    assert "Ринок праці в ІТ України" in _markdown(app)


# ---- home --------------------------------------------------------------------------------------
def test_home_shows_the_latest_day_as_numbered_tiles(export: Path) -> None:
    metrics = _metrics(_run("home"))

    assert metrics["01 · Відкриті вакансії"] == "17"
    assert metrics["02 · Нові за день"] == "3"
    assert metrics["03 · Закриті за день"] == "2"
    assert metrics["05 · Найпопулярніша навичка"] == "Django"  # ties on share are broken by name


def test_home_says_the_pipeline_has_remarks_when_a_check_warns(export: Path) -> None:
    app = _run("home")

    assert _metrics(app)["06 · Стан пайплайну"] == "Є зауваження"
    assert "Є зауваження" in _markdown(app)  # the same state as a chip in the header


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


# ---- market ------------------------------------------------------------------------------------
def test_the_filters_change_the_market_numbers(export: Path) -> None:
    app = _run("market")
    assert _metrics(app)["01 · Відкриті вакансії"] == "17"

    app.multiselect[0].select("dou").run()

    assert _metrics(app)["01 · Відкриті вакансії"] == "12"


def test_a_filter_with_no_vacancies_says_so_instead_of_showing_empty_charts(export: Path) -> None:
    app = _run("market")

    app.multiselect[1].select("QA").run()  # category QA ...
    app.multiselect[0].select("dou").run()  # ... on DOU: there is none

    assert not app.exception and "вакансій немає" in app.info[0].value


def test_the_market_table_lists_the_filtered_rows(export: Path) -> None:
    app = _run("market")

    app.multiselect[0].select("djinni").run()

    table = app.dataframe[-1].value
    assert set(table["Джерело"]) == {"djinni"} and len(table) == 2


# ---- skills ------------------------------------------------------------------------------------
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


# ---- salary ------------------------------------------------------------------------------------
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


# ---- system ------------------------------------------------------------------------------------
def test_the_system_page_counts_the_checks_that_need_attention(export: Path) -> None:
    assert _metrics(_run("system"))["01 · Перевірок, що потребують уваги"] == "1"


def test_the_slo_table_marks_each_state_with_an_icon_and_a_word(export: Path) -> None:
    slo = _run("system").dataframe[0].value

    assert slo["стан"].tolist() == ["✓ виконано", "… замало даних"]


def test_the_about_tab_gives_the_update_time(export: Path) -> None:
    assert "2026-11-09T04:15:00" in _markdown(_run("system"))
