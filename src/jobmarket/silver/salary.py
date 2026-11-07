"""Salary expressions (declared ranges or free text) -> amounts per month in the stated currency.

``parse_salary`` returns the first plausible expression. It does not convert currencies: the USD
conversion needs the NBU rate for the publication date and is a separate step.
"""

import re
from dataclasses import dataclass
from typing import Literal

Period = Literal["month", "hour", "year"]

HOURS_PER_MONTH = 160
MONTHS_PER_YEAR = 12
MIN_MONTHLY_OR_YEARLY_AMOUNT = 100  # smaller numbers next to a currency are bonuses, prices, ...
MIN_HOURLY_AMOUNT = 5
MAX_MONTHLY_AMOUNT = 1_000_000  # larger ones are company revenue, not a salary


@dataclass(frozen=True)
class Salary:
    min: float | None  # per month, in `currency`; None = open lower bound ("до $4000")
    max: float | None  # None = open upper bound ("від $2500")
    currency: str  # USD | EUR | UAH
    period: Period  # period written in the text; min/max are already normalised to a month
    net: bool | None  # True = net ("на руки"), False = gross, None = not stated
    matched: str  # the exact fragment that was parsed


_CURRENCY_WORD = (
    r"(?:(?<![a-z])(?:usd|us\$|uah|eur|euro)(?![a-z])"
    r"|грн\.?|гривн[а-яіїєґ]*|євро"
    r"|дол(?:\.|ар[а-яіїєґ]*)?(?![а-яіїєґ]))"
)
_CURRENCY = rf"(?:[$€₴]|{_CURRENCY_WORD})"
_NUMBER = (
    r"(?:\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?"  # 3 000   50 000,5
    r"|\d{1,3}(?:,\d{3})+(?![\d])"  # 3,000
    r"|\d{1,3}(?:\.\d{3})+(?![\d])"  # 2.500
    r"|\d+(?:[.,]\d+)?)"  # 3000  2.5  4,5
)
_MULTIPLIER = r"(?:k(?![a-z])|к(?![а-яіїєґ])|тис(?:\.|яч[а-яіїєґ]*)?(?![а-яіїєґ])|thousand)"
_RANGE_SEPARATOR = r"(?:-|–|—|−|\bto\b|\bдо\b|\bпо\b)"
_PREFIX_WORD = r"(?:від|from|min|до|up\s+to|upto|max|не\s+більше)"

_EXPRESSION = re.compile(
    rf"""
    (?:(?P<pre>{_PREFIX_WORD})\s*)?
    (?P<c1>{_CURRENCY})?\s*(?P<a>{_NUMBER})(?:\s?(?P<ak>{_MULTIPLIER}))?\s*(?P<c2>{_CURRENCY})?
    (?:\s*{_RANGE_SEPARATOR}\s*
       (?P<c3>{_CURRENCY})?\s*(?P<b>{_NUMBER})(?:\s?(?P<bk>{_MULTIPLIER}))?\s*(?P<c4>{_CURRENCY})?
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)
_NOT_MONEY_AFTER = re.compile(r"\s*(?:m\b|mm\b|bn\b|million|billion|млн|млрд|%)", re.IGNORECASE)
_OPEN_UPPER = re.compile(r"^(?:від|from|min)$", re.IGNORECASE)
_OPEN_LOWER = re.compile(r"^(?:до|up\s+to|upto|max|не\s+більше)$", re.IGNORECASE)

_PERIOD_AFTER: tuple[tuple[Period, re.Pattern[str]], ...] = (
    (
        "hour",
        re.compile(
            r"^\s*(?:/\s*(?:год|hour|hr|h)\b|per\s+hour|hourly|на\s+годину|в\s+годину)", re.I
        ),
    ),
    (
        "year",
        re.compile(
            r"^\s*(?:/\s*(?:рік|year|yr)\b|per\s+(?:year|annum)|annually|yearly|на\s+рік|в\s+рік)",
            re.I,
        ),
    ),
    (
        "month",
        re.compile(r"^\s*(?:/\s*(?:міс|month|mo)\b|per\s+month|monthly|на\s+місяць)", re.I),
    ),
)
_NET = re.compile(
    r"\bnet\b|на\s+руки|після\s+(?:сплати\s+)?(?:податків|оподаткування)|after\s+tax", re.I
)
_GROSS = re.compile(
    r"\bgross\b|до\s+(?:сплати\s+)?(?:податків|оподаткування)|before\s+tax|брутто", re.I
)

# Free text mentions many amounts (bonuses, donations, client budgets). Only an amount with one of
# these words nearby counts as pay. "оплат" and "offer" are left out on purpose: they match
# benefits ("оплата курсів $500", "Benefits We Offer: $100/month").
_PAY_CONTEXT = re.compile(
    r"salar|зарплат|заробітн|заробіток|вилк|compensation|компенсаці[яїює]\b|\brate\b|ставк"
    r"|\bpay\b|income|дохід|винагород|оклад|remuneration|\bwages?\b|оплат[аи]\s+праці"
    r"|\bnet\b|\bgross\b|на\s+руки|брутто",
    re.IGNORECASE,
)
_CONTEXT_BEFORE = 80
_CONTEXT_AFTER = 25

_SYMBOLS = {"$": "USD", "€": "EUR", "₴": "UAH"}


def _currency_code(token: str) -> str:
    token = token.lower().rstrip(".")
    if token in _SYMBOLS:
        return _SYMBOLS[token]
    if token in ("usd", "us$") or token.startswith("дол"):
        return "USD"
    if token in ("eur", "euro", "євро"):
        return "EUR"
    return "UAH"  # uah, грн, гривня


def _to_number(token: str) -> float:
    digits = re.sub(r"[   ]", "", token)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", digits):
        return float(digits.replace(",", ""))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", digits):
        return float(digits.replace(".", ""))
    return float(digits.replace(",", "."))


def _multiplier(token: str | None) -> float:
    return 1.0 if token is None else 1000.0


def _period_after(text: str, end: int) -> Period:
    window = text[end : end + 30]
    for period, pattern in _PERIOD_AFTER:
        if pattern.search(window):
            return period
    return "month"


def _is_net(text: str, start: int, end: int) -> bool | None:
    window = text[max(0, start - 20) : end + 30]
    net, gross = _NET.search(window), _GROSS.search(window)
    if net and (not gross or net.start() <= gross.start()):
        return True
    return False if gross else None


def _has_pay_context(text: str, match: re.Match[str]) -> bool:
    window = text[max(0, match.start() - _CONTEXT_BEFORE) : match.end() + _CONTEXT_AFTER]
    return _PAY_CONTEXT.search(window) is not None


def parse_salary(text: str, *, require_context: bool = False) -> Salary | None:
    """First plausible salary in ``text``.

    ``require_context`` is for running text such as a job description: an amount only counts when
    a pay word ("salary", "зарплата", "rate", "на руки", ...) is close to it. Leave it off for text
    that is already known to be a salary, like a declared range.
    """
    for match in _EXPRESSION.finditer(text):
        found = _interpret(text, match)
        if found is None:
            continue
        if require_context and not _has_pay_context(text, match):
            continue
        return found
    return None


def _interpret(text: str, match: re.Match[str]) -> Salary | None:
    currencies = [match.group(g) for g in ("c1", "c2", "c3", "c4") if match.group(g)]
    if not currencies:
        return None
    if _NOT_MONEY_AFTER.match(text, match.end()):
        return None

    low, high = _to_number(match.group("a")), None
    low_mult, high_mult = match.group("ak"), match.group("bk")
    if match.group("b") is not None:
        high = _to_number(match.group("b"))
        if high_mult and not low_mult and low < high:
            low_mult = high_mult  # "3-5k" means 3k-5k
        high *= _multiplier(high_mult)
    low *= _multiplier(low_mult)

    period = _period_after(text, match.end())
    floor = MIN_HOURLY_AMOUNT if period == "hour" else MIN_MONTHLY_OR_YEARLY_AMOUNT
    amounts = [x for x in (low, high) if x is not None]
    if min(amounts) < floor:
        return None

    factor = {"month": 1.0, "hour": float(HOURS_PER_MONTH), "year": 1 / MONTHS_PER_YEAR}[period]
    if high is None:
        pre = (match.group("pre") or "").strip()
        if _OPEN_UPPER.match(pre):
            lo, hi = low, None
        elif _OPEN_LOWER.match(pre):
            lo, hi = None, low
        else:
            lo, hi = low, low
    else:
        lo, hi = sorted((low, high))
    lo = round(lo * factor, 2) if lo is not None else None
    hi = round(hi * factor, 2) if hi is not None else None
    if max(x for x in (lo, hi) if x is not None) > MAX_MONTHLY_AMOUNT:
        return None

    return Salary(
        min=lo,
        max=hi,
        currency=_currency_code(currencies[0]),
        period=period,
        net=_is_net(text, match.start(), match.end()),
        matched=match.group(0).strip(),
    )
