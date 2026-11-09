"""Runs every dashboard page headlessly on the made-up export and checks what it shows."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402  (after the skip on purpose)

from tests.dashboard_fixtures import write_export  # noqa: E402

ROOT = Path(__file__).parent.parent / "dashboard"
PAGES = ["overview", "skills", "stacks", "salary", "status", "about"]


@pytest.fixture
def export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = write_export(tmp_path / "export")
    monkeypatch.setenv("DASHBOARD_DATA_DIR", str(directory))
    return directory


def _run(page: str) -> AppTest:
    app = AppTest.from_file(str(ROOT / "views" / f"{page}.py"), default_timeout=60).run()
    assert not app.exception, app.exception
    return app


def _metrics(app: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in app.metric}


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_an_error(export: Path, page: str) -> None:
    app = _run(page)

    assert len(app.title) == 1 and not app.error


def test_the_app_starts_on_the_market_overview(export: Path) -> None:
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()

    assert not app.exception and app.title[0].value == "Огляд ринку"


def test_the_overview_shows_the_latest_day_and_the_filters_change_it(export: Path) -> None:
    app = _run("overview")
    assert _metrics(app) == {
        "Відкриті вакансії": "17", "Нові за день": "3", "Закриті за день": "2",
    }  # fmt: skip

    app.multiselect[0].select("dou").run()

    assert _metrics(app)["Відкриті вакансії"] == "12"


def test_a_filter_with_no_vacancies_says_so_instead_of_showing_empty_charts(export: Path) -> None:
    app = _run("overview")

    app.multiselect[1].select("QA").run()  # category QA ...
    app.multiselect[0].select("dou").run()  # ... on DOU: there is none

    assert not app.exception and "вакансій немає" in app.info[0].value


def test_the_skill_page_shows_demand_salary_and_relations(export: Path) -> None:
    app = _run("skills")

    app.selectbox[0].select("Python").run()

    metrics = _metrics(app)
    assert metrics["Частка вакансій (2026-11)"] == "66.7%"
    assert metrics["Медіана, USD/міс"] == "3000"
    assert len(app.dataframe) == 1  # the related skills


def test_a_skill_without_enough_salaries_says_so(export: Path) -> None:
    app = _run("skills")

    app.selectbox[0].select("SQL").run()

    assert any("Замало вакансій" in i.value for i in app.info)


def test_the_stacks_page_has_a_slider_and_survives_moving_it(export: Path) -> None:
    app = _run("stacks")

    app.slider[0].set_value(0.9).run()

    assert not app.exception


def test_the_salary_page_shows_the_survey_for_the_chosen_role(export: Path) -> None:
    app = _run("salary")

    app.selectbox[0].select("qa").run()

    assert _metrics(app)["Медіана"] == "3000"


def test_the_status_page_counts_the_checks_that_need_attention(export: Path) -> None:
    app = _run("status")

    assert _metrics(app) == {"Перевірок, що потребують уваги": "1"}


def test_the_about_page_gives_the_update_time(export: Path) -> None:
    app = _run("about")

    assert any("2026-11-09T04:15:00" in m.value for m in app.markdown)


def test_a_missing_data_directory_is_a_message_not_a_stack_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DASHBOARD_DATA_DIR", str(tmp_path / "nothing"))

    app = AppTest.from_file(str(ROOT / "views" / "overview.py"), default_timeout=60).run()

    assert not app.exception and "Немає даних" in app.error[0].value


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

    app = _run("overview")

    assert any("перший день спостереження" in c.value for c in app.caption)


def test_from_the_second_day_on_there_is_no_such_note(export: Path) -> None:
    app = _run("overview")

    assert not any("перший день спостереження" in c.value for c in app.caption)
