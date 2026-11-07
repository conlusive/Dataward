import csv
import io
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from jobmarket.bronze import BronzeStore
from jobmarket.silver.dou_salaries import Schema, load_schemas, parse_wave, wave_date
from jobmarket.silver.store import SilverStore, SurveyRecord
from jobmarket.silver.survey_build import SOURCE, load_surveys
from tests.helpers import sample

SCHEMAS = load_schemas()


def test_every_survey_file_is_mapped_exactly_once_and_has_a_date() -> None:
    assert len(SCHEMAS) == 34
    assert wave_date("2024_june_raw") == date(2024, 6, 1)
    assert wave_date("2010_october_raw") == date(2010, 10, 1)
    assert wave_date("2017_jun_raw") == date(2017, 6, 1)
    assert wave_date("2022_june_qa") == date(2022, 6, 1)
    assert all(wave_date(stem).year >= 2010 for stem in SCHEMAS)


def test_unknown_month_in_a_file_name_is_an_error() -> None:
    with pytest.raises(ValueError):
        wave_date("2024_spring_raw")


def _csv(text: str) -> bytes:
    return ("﻿" + text).encode("utf-8")


def test_wave_parsing_rules_on_a_small_synthetic_file() -> None:
    schema = Schema(
        columns={
            "salary": "Salary, net after tax",
            "position": "Pos",
            "experience": "Exp",
            "city": "City",
        },
        delimiter=";",
        weight="freq",
        skip_rows={"city": ["Всі міста"]},
    )
    content = _csv(
        'Pos;"Salary, net\nafter tax";Exp;City;Pos;freq\n'  # multi-line header, repeated "Pos"
        "Dev;1500;3 роки;Київ;ignored;2\n"
        "QA;3749,7;4-6 років;Львів;x;1\n"
        "Dev;500 - 1000;Total;Київ;x;3\n"
        "Dev;1500;3 роки;Всі міста;x;5\n"  # subtotal
        "Dev;5000 грн;3 роки;Київ;x;1\n"  # not USD
        "Dev;50;3 роки;Київ;x;1\n"  # below the plausible window
        "Dev;99999;3 роки;Київ;x;1\n"  # above it
        "Dev;;3 роки;Київ;x;1\n"
    )

    rows, stats = parse_wave(content, schema)

    assert [(r.position, r.salary_usd, r.experience_years, r.city, r.weight) for r in rows] == [
        ("Dev", 1500.0, 3.0, "Київ", 2.0),  # the FIRST "Pos" column wins
        ("QA", 3749.7, 5.0, "Львів", 1.0),
        ("Dev", 750.0, None, "Київ", 3.0),
    ]
    assert (stats.rows, stats.kept, stats.subtotals) == (8, 3, 1)
    assert (stats.no_salary, stats.outliers) == (2, 2)
    assert [r.row_no for r in rows] == [1, 2, 3]


def test_a_long_header_matches_by_its_start() -> None:
    schema = Schema(columns={"salary": "Зарплата у $$$"})
    content = _csv('"Зарплата у $$$ за місяць,\nлише ставка ЧИСТИМИ"\n2500\n')

    rows, _ = parse_wave(content, schema)

    assert [r.salary_usd for r in rows] == [2500.0]


def test_missing_mapped_column_is_reported_not_guessed() -> None:
    with pytest.raises(KeyError):
        parse_wave(_csv("A,B\n1,2\n"), Schema(columns={"salary": "Salary"}))


def test_real_cross_tab_wave_keeps_only_detailed_rows() -> None:
    rows, stats = parse_wave(sample("dou_salaries/2022_june_qa.csv"), SCHEMAS["2022_june_qa"])

    # 12 real rows: 6 detailed + 2 "all cities" + 2 "all experience" + 2 "all positions"
    assert (stats.rows, stats.subtotals, stats.kept) == (12, 6, 6)
    assert all(r.city != "Всі міста" and r.position != "Всі посади" for r in rows)
    assert sum(r.weight for r in rows) == 19  # 1 + 2 + 5 + 2 + 8 + 1, not counted twice
    assert rows[0].salary_usd == 250.0  # the "0 - 500" bucket's midpoint


def test_real_wave_with_multiline_header_gets_all_fields() -> None:
    rows, stats = parse_wave(sample("dou_salaries/2023_dec_raw.csv"), SCHEMAS["2023_dec_raw"])

    assert stats.kept == len(rows) > 0
    first = rows[0]
    assert first.position and first.city and first.experience_years is not None
    assert first.english in {
        "elementary",
        "pre-intermediate",
        "intermediate",
        "upper-intermediate",
        "advanced",
        "none",
    }


def test_real_semicolon_wave_with_decimal_commas() -> None:
    rows, stats = parse_wave(sample("dou_salaries/2021_dec_raw.csv"), SCHEMAS["2021_dec_raw"])

    assert stats.kept == len(rows) > 0
    assert all(isinstance(r.salary_usd, float) for r in rows)


@pytest.fixture
def silver(tmp_path: Path) -> SilverStore:
    return SilverStore(tmp_path / "test.duckdb")


def _store_csv(
    bronze: BronzeStore, name: str, content: bytes, day: date, *, status: int = 200
) -> None:
    bronze.write(
        source=SOURCE,
        run_date=day,
        url=f"https://raw.example/salaries/{name}",
        content=content,
        status=status,
        run_id="r1",
        fetched_at=datetime(day.year, day.month, day.day, tzinfo=UTC),
        suffix=".csv",
    )


def _count(silver: SilverStore) -> int:
    row = silver._con.execute("SELECT count(*) FROM silver_dou_salaries").fetchone()
    return int(row[0]) if row else -1


def test_loading_all_waves_is_idempotent_and_reports_unmapped_files(
    tmp_path: Path, silver: SilverStore
) -> None:
    bronze = BronzeStore(tmp_path / "bronze")
    day = date(2026, 11, 6)
    _store_csv(bronze, "2022_june_qa.csv", sample("dou_salaries/2022_june_qa.csv"), day)
    _store_csv(bronze, "2023_dec_raw.csv", sample("dou_salaries/2023_dec_raw.csv"), day)
    _store_csv(bronze, "2030_dec_raw.csv", b"a,b\n1,2\n", day)  # not in the mapping
    _store_csv(bronze, "listing.json", b"[]", day)  # not a CSV

    first = load_surveys(bronze, silver, run_id="p1")
    rows_after_first = _count(silver)
    second = load_surveys(bronze, silver, run_id="p2")

    assert (first.files, first.loaded, first.unmapped, first.failed) == (3, 2, 1, 0)
    assert rows_after_first == first.rows_kept > 0
    assert _count(silver) == rows_after_first and second.rows_kept == first.rows_kept


def _first_answers(content: bytes, count: int) -> bytes:
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows[: count + 1])
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def test_the_newest_bronze_copy_of_a_file_wins(tmp_path: Path, silver: SilverStore) -> None:
    bronze = BronzeStore(tmp_path / "bronze")
    full = sample("dou_salaries/2023_dec_raw.csv")
    _store_csv(bronze, "2023_dec_raw.csv", full, date(2026, 11, 6))
    load_surveys(bronze, silver, run_id="p1")
    assert _count(silver) == 10

    _store_csv(bronze, "2023_dec_raw.csv", _first_answers(full, 4), date(2026, 11, 20))
    load_surveys(bronze, silver, run_id="p2")

    assert _count(silver) == 4  # the older, larger copy is replaced, not merged


def test_a_file_that_no_longer_matches_its_mapping_fails_alone(
    tmp_path: Path, silver: SilverStore
) -> None:
    bronze = BronzeStore(tmp_path / "bronze")
    day = date(2026, 11, 6)
    _store_csv(bronze, "2022_june_qa.csv", sample("dou_salaries/2022_june_qa.csv"), day)
    _store_csv(bronze, "2023_dec_raw.csv", b"Totally,different\n1,2\n", day)

    stats = load_surveys(bronze, silver, run_id="p1")

    assert (stats.loaded, stats.failed) == (1, 1)
    assert _count(silver) > 0


def test_a_failing_insert_rolls_back_and_keeps_the_previous_rows(silver: SilverStore) -> None:
    when = date(2024, 6, 1)
    good: list[SurveyRecord] = [(1, "Dev", 3.0, "Київ", None, None, None, 2000.0, 1.0)]
    silver.replace_survey_file(
        "f.csv", "2024_june_raw", when, good, run_id="p1", loaded_at=datetime(2026, 11, 6)
    )
    bad: list[Any] = [(1, "Dev", 3.0, "Київ", None, None, None, None, 1.0)]  # salary is NOT NULL

    with pytest.raises(duckdb.Error):
        silver.replace_survey_file(
            "f.csv", "2024_june_raw", when, bad, run_id="p2", loaded_at=datetime(2026, 11, 7)
        )

    assert _count(silver) == 1
    kept = silver._con.execute("SELECT salary_usd, _run_id FROM silver_dou_salaries").fetchone()
    assert kept == (2000.0, "p1")
