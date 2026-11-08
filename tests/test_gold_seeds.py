import csv
from datetime import date, datetime
from pathlib import Path

import pytest

from jobmarket.gold_seeds import classify_city, classify_position, write_seeds
from jobmarket.silver.store import SilverStore


@pytest.mark.parametrize(
    ("raw", "role", "seniority"),
    [
        ("Senior QA engineer", "qa", "senior"),
        ("QA Tech Lead", "qa", "lead"),
        ("Junior Software Engineer", "software_engineer", "junior"),
        ("Middle", "software_engineer", "middle"),
        ("Team Lead", "software_engineer", "lead"),
        ("Staff Software Engineer", "software_engineer", "lead"),
        ("DevOps, SysAdmin", "devops", None),
        ("Системный администратор", "devops", None),
        ("Senior Project Manager / Program Manager", "project_manager", "senior"),
        ("Product Manager", "project_manager", None),
        ("Sales manager", "sales", None),
        ("Data Scientist", "data", None),
        ("Data Science, Machine Learning, Big Data", "data", None),
        ("Business analyst", "analyst", None),
        ("Бизнес-аналитик", "analyst", None),
        ("Верстальщик", "frontend_coder", None),
        ("3D Artist", "designer", None),
        ("Security Specialist", "security", None),
        ("DBA", "database", None),
        ("Talent Researcher", "hr", None),
        ("Customer Success", "support", None),
        ("C#/.NET", "software_engineer", None),
        ("Director of Engineering / Program Director", "management", "lead"),
        ("Intern/Trainee", "other", "intern"),
        ("Всі", "other", None),
    ],
)
def test_positions_become_a_role_and_a_level(raw: str, role: str, seniority: str | None) -> None:
    assert classify_position(raw) == (role, seniority)


def test_a_position_that_lists_every_level_is_the_forms_menu_not_a_level() -> None:
    raw = "Software Engineer (Junior, Middle, Senior, Team/Tech Lead, Architect)"

    assert classify_position(raw) == ("software_engineer", None)


@pytest.mark.parametrize(
    ("raw", "city", "group"),
    [
        ("Киев", "Київ", "ukraine"),
        ("Київ", "Київ", "ukraine"),
        ("Київ чи область", "Київ", "ukraine"),
        ("Днепропетровск", "Дніпро", "ukraine"),
        ("Ивано-Франковск", "Івано-Франківськ", "ukraine"),
        ("Ужгород чи Закарпатська область", "Ужгород", "ukraine"),
        ("Кривой Рог", "Кривий Ріг", "ukraine"),
        ("Донецька чи Луганська область", "Донецька/Луганська область", "ukraine"),
        ("За кордоном, але планую повернутися", "За кордоном", "abroad"),
        ("Не Україна", "За кордоном", "abroad"),
        ("Удаленно", "Віддалено", "remote"),
        ("В Україні", "Не вказано", "unspecified"),
        ("Другой", "Не вказано", "unspecified"),
    ],
)
def test_cities_get_one_spelling_and_a_group(raw: str, city: str, group: str) -> None:
    assert classify_city(raw) == (city, group)


def test_the_seed_files_list_every_survey_value_and_report_the_catch_all_share(
    tmp_path: Path,
) -> None:
    silver = SilverStore(tmp_path / "test.duckdb")
    rows = [
        ("Senior QA engineer", "Киев", 3.0),
        ("Middle", "Київ чи область", 1.0),
        ("Всі", "В Україні", 1.0),
    ]
    silver.replace_survey_file(
        "f.csv",
        "2024_june_raw",
        date(2024, 6, 1),
        [(i, p, None, c, None, None, None, 2000.0, w) for i, (p, c, w) in enumerate(rows, 1)],
        run_id="r",
        loaded_at=datetime(2026, 11, 1),
    )

    shares = write_seeds(silver, tmp_path / "seeds")

    positions = list(
        csv.DictReader((tmp_path / "seeds" / "position_map.csv").open(encoding="utf-8"))
    )
    assert {r["position_raw"]: (r["role"], r["seniority"]) for r in positions} == {
        "Senior QA engineer": ("qa", "senior"),
        "Middle": ("software_engineer", "middle"),
        "Всі": ("other", ""),
    }
    cities = {
        r["city_raw"]: r["city"]
        for r in csv.DictReader((tmp_path / "seeds" / "city_map.csv").open(encoding="utf-8"))
    }
    assert cities == {"Киев": "Київ", "Київ чи область": "Київ", "В Україні": "Не вказано"}
    assert shares == {
        "positions_other": pytest.approx(1 / 5),
        "cities_unspecified": pytest.approx(1 / 5),
    }
