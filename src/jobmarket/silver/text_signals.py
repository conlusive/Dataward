"""Signals read from a vacancy's title and description: seniority, required experience, English.

Seniority comes from the title only; required experience and the English level come from the
description. They are kept apart on purpose: a "Senior" title and "3+ years" in the text are two
independent opinions about the same vacancy.
"""

import re

_MAX_YEARS = 25.0
_MIN_YEARS = 0.5

# --- required experience ----------------------------------------------------------------------
_NUMBER = r"\d{1,2}(?:[.,]\d)?"
_YEAR_UNIT = r"(?:years?|yrs?|років|роки|рік|року|лет|года|год)(?![a-zа-яіїєґ])"
_MONTH_UNIT = r"(?:months?|місяців|місяці|місяць|міс\.?|месяцев|месяца|месяц)(?![a-zа-яіїєґ])"
_ANY_UNIT = rf"(?:{_YEAR_UNIT}|{_MONTH_UNIT})"
_AT_LEAST = (
    r"(?:at\s+least|minimum(?:\s+of)?|min\.?|from|від|не\s+менше(?:\s+ніж)?|мінімум|щонайменше)"
)

_PLUS = re.compile(rf"(?<![\d.,\-–—])({_NUMBER})\s*\+\s*({_ANY_UNIT})", re.IGNORECASE)
_LOWER_BOUND = re.compile(rf"{_AT_LEAST}\s+({_NUMBER})\s*({_ANY_UNIT})", re.IGNORECASE)
_RANGE = re.compile(
    rf"(?<![\d.,])({_NUMBER})\s*(?:[-–—]|\bto\b|\bдо\b)\s*{_NUMBER}\s*\+?\s*({_ANY_UNIT})",
    re.IGNORECASE,
)
_FROM_TO = re.compile(  # "від 1 до 4 років", "from 2 to 3 years"
    rf"(?:від|from)\s+({_NUMBER})\s*(?:до|to)\s+{_NUMBER}\s*({_ANY_UNIT})", re.IGNORECASE
)
_PLAIN = re.compile(rf"(?<![\d.,])({_NUMBER})\s*({_ANY_UNIT})", re.IGNORECASE)

# "years" next to one of these is about experience; without them (and without a marker such as
# "+" or "at least") it is a duration, a date or a company age:
# "до 2030 року", "на 2-3 роки вперед".
_EXPERIENCE_WORD = re.compile(
    r"experience|досвід|commercial|комерційн|hands-on|practical|практичн", re.IGNORECASE
)
# What follows the number in a requirement: "4-6 years in backend", "3 роки в скорингу".
_USAGE_AFTER = re.compile(
    r"\s*(?:of|in|with|as|building|developing|working|using|running|в|у|з)(?![a-zа-яіїєґ])",
    re.IGNORECASE,
)
# The company or team describing itself, not asking for experience.
_ABOUT_US = re.compile(
    r"on the (?:\w+ )?market|на ринку|since\s+\d{4}|founded|заснован|company (?:has|with|is)"
    r"|(?:вже|already)\s+\d+\+?\s*(?:років|рік|years?)"
    r"|компанія (?:має|з)\b|our (?:team|company)|we(?:'ve| have) been|minimum development "
    r"experience is",
    re.IGNORECASE,
)


def _years(amount: str, unit: str) -> float:
    value = float(amount.replace(",", "."))
    return value / 12 if re.fullmatch(_MONTH_UNIT, unit, re.IGNORECASE) else value


def _plausible(years: float) -> bool:
    return _MIN_YEARS <= years <= _MAX_YEARS


def parse_required_experience(text: str) -> float | None:
    """Years of experience the vacancy asks for (lower bound; the largest mentioned)."""
    found: list[float] = []
    for line in text.splitlines():
        if _ABOUT_US.search(line):
            continue
        has_keyword = _EXPERIENCE_WORD.search(line) is not None
        strong = [*_PLUS.finditer(line), *_LOWER_BOUND.finditer(line)]
        ranges = [
            m
            for m in [*_RANGE.finditer(line), *_FROM_TO.finditer(line)]
            if has_keyword or _USAGE_AFTER.match(line, m.end())
        ]
        # A plain number inside a range or a marked match is not a second requirement.
        plain = [
            m
            for m in _PLAIN.finditer(line)
            if has_keyword or _USAGE_AFTER.match(line, m.end())
            if not any(r.start() <= m.start() < r.end() for r in [*ranges, *strong])
        ]
        for match in [*strong, *ranges, *plain]:
            years = round(_years(match.group(1), match.group(2)), 2)
            if _plausible(years):
                found.append(years)
    return max(found) if found else None


# --- English level ----------------------------------------------------------------------------
# Authors often type the CEFR letter with a Cyrillic look-alike ("В2" for "B2").
_LOOKALIKES = str.maketrans({"А": "a", "В": "b", "С": "c", "а": "a", "с": "c"})
_CEFR = {
    "a1": "elementary",
    "a2": "pre-intermediate",
    "b1": "intermediate",
    "b2": "upper-intermediate",
    "c1": "advanced",
    "c2": "advanced",
}
_LEVEL_WORDS = (
    ("pre-intermediate", "pre-intermediate"),
    ("pre intermediate", "pre-intermediate"),
    ("upper-intermediate", "upper-intermediate"),
    ("upper intermediate", "upper-intermediate"),
    ("upper-int", "upper-intermediate"),
    ("intermediate", "intermediate"),
    ("elementary", "elementary"),
    ("advanced", "advanced"),
    ("fluent", "advanced"),
    ("proficient", "advanced"),
)
_LEVEL = re.compile(
    r"(?<![a-zа-яіїєґ])(?:(?P<word>pre[- ]intermediate|upper[- ](?:intermediate|int)|intermediate"
    r"|elementary|advanced|fluent|proficient)|(?P<cefr>[abcАВСас][12])(?=\+?(?![a-z0-9])))"
    r"(?![a-zа-яіїєґ])",
    re.IGNORECASE,
)
_ENGLISH = re.compile(r"english|англійськ|англ\.", re.IGNORECASE)
# Perks, not requirements: "Free English and business English courses", "заняття з англійської".
_PERK = re.compile(
    r"курс|заняття|classes|courses|clubs|клуб|безкоштовн|\bfree\b|compensation|компенсац"
    r"|навчання|learning|lessons|уроки",
    re.IGNORECASE,
)
_ENGLISH_DISTANCE = 45  # characters between the English word and the level


def parse_english_level(text: str) -> str | None:
    """The English level a vacancy asks for, on the DOU scale (elementary .. advanced)."""
    for line in text.splitlines():
        if _PERK.search(line):
            continue
        english = [m.start() for m in _ENGLISH.finditer(line)]
        if not english:
            continue
        for match in _LEVEL.finditer(line):
            if min(abs(match.start() - pos) for pos in english) > _ENGLISH_DISTANCE:
                continue
            if match.group("cefr"):
                return _CEFR[match.group("cefr").translate(_LOOKALIKES).lower()]
            word = re.sub(r"\s+", " ", match.group("word").lower())
            for alias, level in _LEVEL_WORDS:
                if word.replace("-", " ") == alias.replace("-", " ") or word.startswith(alias[:9]):
                    return level
    return None


# --- seniority (title) ------------------------------------------------------------------------
_SENIORITY = (
    ("intern", r"intern(?:ship)?\b|trainee|стажер|стажист"),
    ("junior", r"junior|\bjr\b\.?|молодш|початківець|entry[- ]level"),
    ("middle", r"middle|\bmid\b(?![- ]?level\b)|\bmid[- ]level\b|\bmiddle\+|середн"),
    ("senior", r"senior|\bsr\b\.?|старш"),
    (
        "lead",
        r"(?<!generation )\blead\b(?! generation| gen\b)|\bprincipal\b|\bstaff\b|\bhead of\b"
        r"|\barchitect\b|\bтімлід|\bтехлід|провідн|головн",
    ),
)


def parse_seniority(title: str) -> str | None:
    """Seniority named in the title: intern / junior / middle / senior / lead.

    When a title names several levels ("Junior/Middle", "Trainee / Junior") the first one in the
    title wins.
    """
    earliest: tuple[int, str] | None = None
    for level, pattern in _SENIORITY:
        match = re.search(pattern, title, re.IGNORECASE)
        if match and (earliest is None or match.start() < earliest[0]):
            earliest = (match.start(), level)
    return earliest[1] if earliest else None
