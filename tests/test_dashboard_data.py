from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from jobmarket import dashboard_data as dd
from jobmarket.export import SCHEMA_FILE, contracts
from tests.dashboard_fixtures import GRID, NOV, tables, write_export, write_grid


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.DataFrame]:
    return tables()


# ---- the files and their columns -------------------------------------------------------------
def test_the_dashboard_only_asks_for_columns_the_dbt_contracts_publish() -> None:
    published = {name: {c for c, _ in cols} for name, cols in contracts(SCHEMA_FILE).items()}
    published["skill_clusters"] = {"skill_id", "cluster_id", "cluster_size", "cluster_label"}

    for table, needed in dd.REQUIRED.items():
        assert table in published, f"{table} is not exported"
        assert needed <= published[table], (table, needed - published[table])


def test_the_fixture_has_every_table_the_dashboard_needs() -> None:
    assert set(tables()) == set(dd.REQUIRED)


def test_a_table_is_read_from_parquet(tmp_path: Path) -> None:
    write_export(tmp_path)

    frame = dd.read_table(tmp_path, "dim_skill")

    assert sorted(frame["skill_id"]) == ["django", "docker", "python", "sql"]


def test_a_missing_file_says_how_to_create_it(tmp_path: Path) -> None:
    with pytest.raises(dd.DataError, match="make pipeline"):
        dd.read_table(tmp_path, "dim_skill")


def test_a_renamed_column_is_reported_by_name(tmp_path: Path) -> None:
    write_export(tmp_path)
    import duckdb

    duckdb.connect().execute(
        f"COPY (SELECT skill_id, canonical AS name FROM '{tmp_path / 'dim_skill.parquet'}') "
        f"TO '{tmp_path / 'dim_skill.parquet'}.new' (FORMAT parquet)"
    )
    (tmp_path / "dim_skill.parquet.new").replace(tmp_path / "dim_skill.parquet")

    with pytest.raises(
        dd.DataError, match=r"lacks the columns \['canonical', 'category', 'parent_id'\]"
    ):
        dd.read_table(tmp_path, "dim_skill")


def test_the_data_directory_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_DATA_DIR", "/somewhere")
    assert dd.data_dir() == Path("/somewhere")
    monkeypatch.delenv("DASHBOARD_DATA_DIR")
    assert dd.data_dir() == dd.DEFAULT_DIR


# ---- market overview -------------------------------------------------------------------------
def test_open_vacancies_per_day_have_one_column_per_source(frames: dict[str, pd.DataFrame]) -> None:
    series = dd.open_by_day(frames["fct_market_daily"])

    assert (
        series.loc[date(2026, 11, 1), "dou"] == 10 and series.loc[date(2026, 11, 2), "djinni"] == 5
    )


def test_filters_narrow_the_market_and_an_empty_filter_means_everything(
    frames: dict[str, pd.DataFrame],
) -> None:
    market = frames["fct_market_daily"]

    assert len(dd.filter_market(market)) == 4
    assert len(dd.filter_market(market, sources=["dou"])) == 2
    assert len(dd.filter_market(market, sources=["dou"], categories=["QA"])) == 0
    assert len(dd.filter_market(market, seniorities=["middle"])) == 2


def test_categories_are_counted_on_the_latest_day_most_first(
    frames: dict[str, pd.DataFrame],
) -> None:
    by_category = dd.open_by_category(frames["fct_market_daily"])

    assert by_category.to_dict("records") == [
        {"category": "Python", "open_vacancies": 12},
        {"category": "QA", "open_vacancies": 5},
    ]


def test_an_empty_selection_gives_an_empty_breakdown(frames: dict[str, pd.DataFrame]) -> None:
    empty = dd.filter_market(frames["fct_market_daily"], sources=["nothing"])

    assert dd.open_by_category(empty).empty


# ---- skills ----------------------------------------------------------------------------------
def test_top_skills_are_the_latest_months_most_demanded(frames: dict[str, pd.DataFrame]) -> None:
    demand, skills = frames["fct_skill_demand_monthly"], frames["dim_skill"]

    top = dd.top_skills(demand, skills, month=dd.latest_month(demand), n=3)

    assert dd.latest_month(demand) == NOV
    assert list(top["canonical"]) == ["Django", "Docker", "Python"]  # equal shares: by name
    assert dd.top_skills(demand, skills, month=NOV, category="database")["canonical"].tolist() == [
        "SQL"
    ]


def test_a_skills_trend_is_in_time_order(frames: dict[str, pd.DataFrame]) -> None:
    trend = dd.skill_trend(frames["fct_skill_demand_monthly"], "python")

    assert trend["share"].tolist() == [0.5, 0.6667] and trend["month"].is_monotonic_increasing


def test_related_skills_come_from_either_side_of_a_pair_and_skip_unknown_npmi(
    frames: dict[str, pd.DataFrame],
) -> None:
    related = dd.related_skills(frames["fct_skill_pairs"], frames["dim_skill"], "docker")

    assert related["canonical"].tolist() == ["Django", "Python"]  # by NPMI, highest first
    assert dd.related_skills(frames["fct_skill_pairs"], frames["dim_skill"], "sql").empty


def test_skill_salary_is_none_when_too_few_vacancies_state_one(
    frames: dict[str, pd.DataFrame],
) -> None:
    salary = frames["fct_salary_by_skill"]

    assert dd.skill_salary(salary, "python") == {
        "vacancies": 2.0,
        "p25": 2500.0,
        "median": 3000.0,
        "p75": 3500.0,
    }
    assert dd.skill_salary(salary, "sql") is None


def test_a_skills_cluster_lists_its_members(frames: dict[str, pd.DataFrame]) -> None:
    cluster = dd.skill_cluster(frames["skill_clusters"], frames["dim_skill"], "django")

    assert cluster == {
        "cluster_id": 1,
        "size": 3,
        "label": "python",
        "members": ["Django", "Docker", "Python"],
    }
    assert dd.skill_cluster(frames["skill_clusters"], frames["dim_skill"], "sql") is None


# ---- stacks ----------------------------------------------------------------------------------
def test_the_cluster_overview_has_one_row_per_cluster(frames: dict[str, pd.DataFrame]) -> None:
    overview = dd.cluster_overview(frames["skill_clusters"], frames["dim_skill"])

    assert overview.to_dict("records") == [
        {"cluster_id": 1, "size": 3, "label": "python", "members": "Django, Docker, Python"}
    ]


def test_the_stack_graph_has_a_node_per_member_and_an_edge_per_strong_pair(
    frames: dict[str, pd.DataFrame],
) -> None:
    dot = dd.stack_dot(frames["fct_skill_pairs"], frames["skill_clusters"], frames["dim_skill"], 1)

    assert dot.startswith("graph G {") and dot.endswith("}")
    assert (
        dot.count(" -- ") == 2
    )  # django-docker (1.0) and docker-python (0.369); python-sql is not in the cluster
    assert '"Django" -- "Docker"' in dot


def test_a_higher_threshold_drops_the_weaker_edge(frames: dict[str, pd.DataFrame]) -> None:
    dot = dd.stack_dot(
        frames["fct_skill_pairs"], frames["skill_clusters"], frames["dim_skill"], 1, min_npmi=0.5
    )

    assert dot.count(" -- ") == 1


def test_a_skill_name_with_a_quote_cannot_break_the_graph_syntax() -> None:
    skills = pd.DataFrame({"skill_id": ["a", "b"], "canonical": ['we"ird', "plain"]})
    clusters = pd.DataFrame({"skill_id": ["a", "b"], "cluster_id": [1, 1]})
    pairs = pd.DataFrame({"skill_a": ["a"], "skill_b": ["b"], "npmi": [0.9]})

    dot = dd.stack_dot(pairs, clusters, skills, 1)

    assert 'we\\"ird' in dot and 'we"ird' not in dot.replace('we\\"ird', "")


# ---- salary, status --------------------------------------------------------------------------
def test_the_survey_benchmark_is_per_role_newest_year_first(
    frames: dict[str, pd.DataFrame],
) -> None:
    qa = dd.survey_benchmark(frames["fct_salary_survey"], role="qa")

    assert qa["survey_year"].tolist() == [2025, 2024]
    assert dd.survey_benchmark(frames["fct_salary_survey"], role="qa", seniority="junior").empty


def test_slo_and_run_tables_use_plain_words() -> None:
    from tests.dashboard_fixtures import STATUS

    slo = dd.slo_table(STATUS)
    runs = dd.runs_table(STATUS)

    assert slo["стан"].tolist() == ["виконано", "замало даних"]
    assert runs["впали кроки"].tolist() == ["", "parse"]


# ---- the salary calculator -----------------------------------------------------------------------
def test_without_a_trained_model_there_is_no_grid(tmp_path: Path) -> None:
    write_export(tmp_path)

    assert dd.read_grid(tmp_path) is None


def test_the_grid_is_read_with_its_description(tmp_path: Path) -> None:
    write_export(tmp_path)
    write_grid(tmp_path)

    loaded = dd.read_grid(tmp_path)

    assert loaded is not None
    grid, info = loaded
    assert len(grid) == 6 and info["version"] == 3


def test_a_grid_with_a_missing_column_is_reported(tmp_path: Path) -> None:
    import duckdb

    write_export(tmp_path)
    write_grid(tmp_path)
    path = tmp_path / "salary_model_grid.parquet"
    duckdb.connect().execute(
        f"COPY (SELECT role, seniority FROM '{path}') TO '{path}.new' (FORMAT parquet)"
    )
    (tmp_path / "salary_model_grid.parquet.new").replace(path)

    with pytest.raises(dd.DataError, match="make train"):
        dd.read_grid(tmp_path)


def test_the_lookup_takes_the_closest_experience_on_the_grid() -> None:
    profile = {
        "role": "qa",
        "seniority": "senior",
        "english": "upper-intermediate",
        "city_group": "ukraine",
    }

    found = dd.grid_lookup(GRID, experience=4.4, **profile)  # 5 is closer than 3

    assert found == {"p10": 2000.0, "p50": 3300.0, "p90": 4800.0, "experience_used": 5.0}
    assert dd.grid_lookup(GRID, experience=40.0, **profile)["experience_used"] == 10.0  # type: ignore[index]


def test_a_profile_that_is_not_in_the_grid_gets_none() -> None:
    assert (
        dd.grid_lookup(
            GRID,
            role="dev",
            seniority="senior",
            experience=3.0,
            english="intermediate",
            city_group="ukraine",
        )
        is None
    )
