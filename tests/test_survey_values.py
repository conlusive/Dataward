import pytest

from jobmarket.silver.survey_values import (
    COMPANY_SIZES,
    COMPANY_TYPES,
    ENGLISH_LEVELS,
    clean_text,
    is_plausible_salary,
    lookup,
    parse_experience_years,
    parse_survey_salary,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3", 3.0),
        ("1.5", 1.5),
        ("0.5", 0.5),
        ("3 роки", 3.0),
        ("1 рік", 1.0),
        ("5 років", 5.0),
        ("3 года", 3.0),
        ("5 лет", 5.0),
        ("4 years", 4.0),
        ("1,5 року", 1.5),
        ("2,5 года", 2.5),
        ("3.5 л", 3.5),
        ("4y", 4.0),
        ("Пів року", 0.5),
        ("Півроку", 0.5),
        ("полгода", 0.5),
        ("Півтора роки", 1.5),
        ("До року", 0.5),
        ("до року", 0.5),
        ("3 місяці", 0.25),
        ("6 мес.", 0.5),
        ("3 month", 0.25),
        ("меньше 3 месяцев", 0.125),
        ("Менше як 3 місяці", 0.125),
        ("4-6 років", 5.0),
        ("3-4года", 3.5),
        ("від 1 до 3 років", 2.0),
        ("від 7 до 10 років", 8.5),
        ("10 и более лет", 10.0),
        ("10 і більше років", 10.0),
        ("15  і більше років", 15.0),
        ("10+ років", 10.0),
        ("10+", 10.0),
        ("понад 10 років", 10.0),
        ("Понад 20 років", 20.0),
        ("6 лет 6 мес", 6.5),
        ("3 года 6 месяцев", 3.5),
        ("1y3m", 1.25),
    ],
)
def test_experience_variants_seen_in_the_surveys(text: str, expected: float) -> None:
    assert parse_experience_years(text) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize(
    "text", ["", "Весь досвід", "Total", "-", "-99", "Харьков", "2ujlf", "три месяца"]
)
def test_experience_that_is_not_an_answer_is_none(text: str) -> None:
    assert parse_experience_years(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1500", 1500.0),
        ("3749,7", 3749.7),
        ("1542.75", 1542.75),
        ("500 - 1000", 750.0),
        ("1000 - 1500", 1250.0),
        ("1500 USD", 1500.0),
        ("1500 $", 1500.0),
        ("5000 грн", None),
        ("", None),
        ("n/a", None),
    ],
)
def test_survey_salary(text: str, expected: float | None) -> None:
    assert parse_survey_salary(text) == expected


def test_plausible_salary_window() -> None:
    assert is_plausible_salary(100) and is_plausible_salary(30_000)
    assert not is_plausible_salary(99.99) and not is_plausible_salary(30_000.01)


def test_english_levels_across_languages_and_option_numbers() -> None:
    assert lookup(ENGLISH_LEVELS, "выше среднего") == "upper-intermediate"
    assert lookup(ENGLISH_LEVELS, "Upper-Intermediate") == "upper-intermediate"
    assert lookup(ENGLISH_LEVELS, "5. Upper-Intermediate") == "upper-intermediate"
    assert lookup(ENGLISH_LEVELS, "1. Не знаю взагалі") == "none"
    assert lookup(ENGLISH_LEVELS, "") is None


def test_company_vocabularies_merge_russian_and_ukrainian_wording() -> None:
    assert (
        lookup(COMPANY_TYPES, "Аутсорсинговая")
        == lookup(COMPANY_TYPES, "Аутсорсингова")
        == "outsource"
    )
    assert lookup(COMPANY_TYPES, "Аутстафінгова") == "outstaff"
    assert lookup(COMPANY_SIZES, "свыше 1000 человек") == ">1000"
    assert lookup(COMPANY_SIZES, "до 50  человек") == "<=50"
    assert lookup(COMPANY_SIZES, "something else") is None


def test_clean_text_collapses_spaces_and_empties_to_none() -> None:
    assert clean_text("  Київ \n") == "Київ"
    assert clean_text("A   B") == "A B"
    assert clean_text("   ") is None
