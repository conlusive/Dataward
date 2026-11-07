"""Value parsers for DOU salary-survey answers (Russian and Ukrainian wording, 2010-2026)."""

import re

from jobmarket.silver.salary import parse_salary

MIN_SALARY_USD = 100  # below: typos and non-monthly answers
MAX_SALARY_USD = 30_000

_DECIMAL = r"\d+(?:[.,]\d+)?"


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def parse_survey_salary(text: str) -> float | None:
    """USD per month: a plain number, a "500 - 1000" bucket (midpoint) or "1500 USD".

    Amounts in another currency ("5000 грн") are not converted here and return None.
    """
    value = text.strip()
    if re.fullmatch(_DECIMAL, value):
        return _number(value)
    bucket = re.fullmatch(rf"({_DECIMAL})\s*[-–]\s*({_DECIMAL})", value)
    if bucket:
        return (_number(bucket.group(1)) + _number(bucket.group(2))) / 2
    parsed = parse_salary(value)
    if parsed is None or parsed.currency != "USD":
        return None
    amounts = [x for x in (parsed.min, parsed.max) if x is not None]
    return sum(amounts) / len(amounts)


def is_plausible_salary(usd: float) -> bool:
    return MIN_SALARY_USD <= usd <= MAX_SALARY_USD


# --- experience -------------------------------------------------------------------------------
_UNKNOWN_EXPERIENCE = {"", "весь досвід", "total", "-", "-99"}
_YEAR = r"(?:років|рік|року|роки|рок|лет|года|год|годов|years?|yrs?|y|л|г)"
_MONTH = r"(?:місяців|місяці|місяць|месяцев|месяца|месяц|мес|міс|months?|m)"
_PAIR = re.compile(rf"({_DECIMAL})\s*({_YEAR}|{_MONTH})?(?![a-zа-яіїє])", re.IGNORECASE)
_MONTH_UNIT = re.compile(rf"^{_MONTH}$", re.IGNORECASE)
_RANGE = re.compile(rf"({_DECIMAL})\s*(?:[-–]|до)\s*({_DECIMAL})")
_OPEN_END = re.compile(r"\+|більше|более|понад|свыше", re.IGNORECASE)


def _years(amount: float, unit: str | None) -> float:
    return amount / 12 if unit and _MONTH_UNIT.match(unit) else amount


def parse_experience_years(text: str) -> float | None:
    """Years of experience from answers like "3 роки", "4-6 років", "10 і більше років"."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    if t in _UNKNOWN_EXPERIENCE:
        return None
    if "півтора" in t:
        return 1.5
    if re.search(r"пів\s?року|полгода", t):
        return 0.5
    if re.search(r"^(?:до|менше|меньше)(?: як)? року$", t):
        return 0.5

    less = re.search(rf"(?:менше|меньше)(?: як)? ({_DECIMAL}) ?({_MONTH}|{_YEAR})", t)
    if less:  # "less than 3 months": take the middle of the interval
        return round(_years(_number(less.group(1)) / 2, less.group(2)), 3)

    span = _RANGE.search(t)
    if span:
        # "4-6 років", "від 1 до 3 років", "3-4года": the middle of the range
        return (_number(span.group(1)) + _number(span.group(2))) / 2

    pairs = list(_PAIR.finditer(t))
    if not pairs:
        return None
    if len(pairs) == 1:
        amount = _number(pairs[0].group(1))
        unit = pairs[0].group(2)
        return round(_years(amount, unit), 2)  # "10+", "понад 10 років" -> 10
    # "6 лет 6 мес", "1год 5 месяцев": years plus months
    if all(p.group(2) for p in pairs):
        return round(sum(_years(_number(p.group(1)), p.group(2)) for p in pairs), 2)
    return None


# --- small vocabularies -----------------------------------------------------------------------
ENGLISH_LEVELS = {
    "элементарный": "elementary",
    "elementary": "elementary",
    "ниже среднего": "pre-intermediate",
    "pre-intermediate": "pre-intermediate",
    "средний": "intermediate",
    "intermediate": "intermediate",
    "выше среднего": "upper-intermediate",
    "upper-intermediate": "upper-intermediate",
    "продвинутый": "advanced",
    "advanced": "advanced",
    "не знаю взагалі": "none",
}
COMPANY_TYPES = {
    "аутсорсинговая": "outsource",
    "аутсорсингова": "outsource",
    "продуктовая": "product",
    "продуктова": "product",
    "аутстаффинговая": "outstaff",
    "аутстафінгова": "outstaff",
    "стартап": "startup",
    "другая": "other",
    "інша": "other",
    "фріланс": "freelance",
}
COMPANY_SIZES = {
    "меньше 10 человек": "<=10",
    "до 10 человек": "<=10",
    "10 - 50 человек": "<=50",
    "до 50 человек": "<=50",
    "до 100 человек": "<=100",
    "50 - 200 человек": "<=200",
    "до 200 человек": "<=200",
    "больше 200 человек": ">200",
    "до 1000 человек": "<=1000",
    "свыше 1000 человек": ">1000",
}


def lookup(vocabulary: dict[str, str], text: str) -> str | None:
    """Vocabulary entry for an answer; a leading option number ("5. Advanced") is ignored."""
    cleaned = re.sub(r"^\d+\.\s*", "", re.sub(r"\s+", " ", text.strip().lower()))
    return vocabulary.get(cleaned)


def clean_text(text: str) -> str | None:
    """Trimmed, single-spaced text; empty becomes None."""
    value = re.sub(r"\s+", " ", text).strip()
    return value or None
