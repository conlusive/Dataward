from datetime import date

import pytest

from jobmarket.silver.dates import parse_ua_date
from jobmarket.silver.model import ParseError, text_hash
from jobmarket.silver.parse_djinni import parse_djinni_vacancy
from jobmarket.silver.parse_dou import parse_dou_vacancy
from jobmarket.silver.text import html_to_text
from tests.helpers import sample

FETCHED = date(2026, 11, 6)
DOU_URL = "https://jobs.dou.ua/companies/solid-software/vacancies/359220/"
DJINNI_URL = "https://djinni.co/jobs/857083-python-spark-ai-developer_tt/"


def _dou(name: str, url: str = DOU_URL):  # type: ignore[no-untyped-def]
    return parse_dou_vacancy(sample(f"dou/{name}").decode(), url, fetched_on=FETCHED)


def _djinni(name: str, url: str = DJINNI_URL):  # type: ignore[no-untyped-def]
    return parse_djinni_vacancy(sample(f"djinni/{name}").decode(), url, fetched_on=FETCHED)


def test_dou_remote_vacancy() -> None:
    v = _dou("detail.html")

    assert (v.id, v.source) == ("dou:359220", "dou")
    assert (v.title, v.company, v.category) == (
        "Senior Python Developer",
        "Solid Software",
        "Python",
    )
    assert v.remote is True and v.locations == []
    assert v.published_at == date(2026, 10, 30)
    assert v.description_text.startswith("We are looking for a Senior Python Developer")


def test_dou_office_vacancy_lists_cities_and_is_not_remote() -> None:
    v = _dou("detail_cities.html", "https://jobs.dou.ua/companies/eleks/vacancies/378180/")

    assert v.company == "ELEKS" and v.category == "PHP"
    assert v.locations == ["Київ", "Львів", "Івано-Франківськ", "Тернопіль"]
    assert v.remote is False


def test_djinni_structured_fields_come_from_json_ld() -> None:
    v = _djinni("detail.html")

    assert (v.id, v.company, v.category) == ("djinni:857083", "PulseRise Technologies", "Python")
    assert v.remote is True
    assert v.experience_years == 3.0
    assert v.published_at == date(2026, 11, 6)
    assert v.salary_raw is None


def test_djinni_declared_salary_is_kept_as_parseable_text() -> None:
    v = _djinni(
        "detail_salary.html", "https://djinni.co/jobs/764691-junior-python-software-engineer/"
    )

    assert v.salary_raw == "550-700 USD/MONTH"


def test_djinni_city_list_in_json_ld_is_flattened() -> None:
    v = _djinni("detail_cities.html", "https://djinni.co/jobs/856312-senior-scala-engineer/")

    assert v.locations == ["Київ", "Львів"]
    assert v.remote is False


@pytest.mark.parametrize("name", ["detail.html", "detail_cities.html"])
def test_descriptions_are_clean_text(name: str) -> None:
    text = _dou(name).description_text

    assert "\xa0" not in text and "<" not in text
    assert text == text.strip()
    assert "\n" in text  # paragraphs survive


def test_listing_page_is_not_a_vacancy() -> None:
    with pytest.raises(ParseError):
        parse_dou_vacancy(sample("dou/list_python.html").decode(), DOU_URL, fetched_on=FETCHED)
    with pytest.raises(ParseError):
        parse_djinni_vacancy(
            sample("djinni/list_python.html").decode(), DJINNI_URL, fetched_on=FETCHED
        )


def test_wrong_url_is_rejected() -> None:
    with pytest.raises(ParseError):
        parse_dou_vacancy(
            sample("dou/detail.html").decode(), "https://jobs.dou.ua/", fetched_on=FETCHED
        )


def test_content_hash_ignores_case_and_whitespace() -> None:
    assert text_hash("Hello   World\n") == text_hash(" hello world")
    assert text_hash("hello world") != text_hash("hello there")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("30 жовтня 2026", date(2026, 10, 30)),
        ("  5 листопада 2026\n", date(2026, 11, 5)),
        ("3 січня", date(2026, 1, 3)),  # no year: this year
        ("30 грудня", date(2025, 12, 30)),  # no year and still in the future: last year
        ("32 жовтня 2026", None),
        ("30 foo 2026", None),
        ("", None),
    ],
)
def test_parse_ua_date(text: str, expected: date | None) -> None:
    assert parse_ua_date(text, today=date(2026, 11, 6)) == expected


def test_html_to_text_keeps_blocks_and_joins_inline_markup() -> None:
    html = "<p>We&nbsp;need a <b>Senior</b> dev</p><ul><li>one</li><li>two</li></ul>a<br>b"

    assert html_to_text(html) == "We need a Senior dev\none\ntwo\na\nb"


def test_a_hidden_employer_is_kept_with_the_word_the_site_gives() -> None:
    html = sample("djinni/detail.html").decode()
    start = html.index('"hiringOrganization"')
    end = html.index("}", start) + 1
    hidden = html[:start] + '"hiringOrganization": "confidential"' + html[end:]

    vacancy = parse_djinni_vacancy(hidden, DJINNI_URL, fetched_on=FETCHED)

    assert vacancy.company == "confidential" and vacancy.title == "Python/Spark/AI Developer_TT"
