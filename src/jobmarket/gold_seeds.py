"""Seeds for the gold layer: survey positions -> role and seniority, survey cities -> one spelling.

The survey answers are free text across 15 years in two languages (558 positions, 86 cities in
the stored waves). The rules below turn them into a small vocabulary; the result is written to
CSV seeds that dbt reads, so every mapping is visible and can be corrected by editing the CSV.
"""

import csv
import re
from pathlib import Path

from jobmarket.silver.store import SilverStore

SEEDS_DIR = Path("warehouse/seeds")

# ---- positions ---------------------------------------------------------------------------------
_LEVELS = (
    ("intern", re.compile(r"\bintern\b|trainee|стажер|стажист", re.IGNORECASE)),
    ("junior", re.compile(r"\bjunior\b|\bjr\b|джуніор|джуниор", re.IGNORECASE)),
    ("middle", re.compile(r"\bmiddle\b|\bmid\b|міддл|миддл", re.IGNORECASE)),
    ("senior", re.compile(r"\bsenior\b|\bsr\b|сеньйор|сеньор", re.IGNORECASE)),
    (
        "lead",
        re.compile(
            r"\blead\b|tech lead|team lead|\bhead\b|principal|\bstaff\b|architect|director|\bcto\b"
            r"|тімлід|тимлид|техлід",
            re.IGNORECASE,
        ),
    ),
)
# Order matters: the first rule that matches wins.
_ROLES = (
    ("technical_writer", r"technical writer|tech writer|техн\w* писат"),
    ("hr", r"\bhr\b|recruit|рекрутер|learning and development|talent|sourcer"),
    ("sales", r"\bsales\b|продаж|business development|account manager"),
    ("marketing", r"marketing|\bseo\b|copywrit|\bpr\b|\bsmm\b|\bppc\b|маркетинг"),
    ("support", r"support|customer success|підтримк|поддержк|help ?desk"),
    ("designer", r"design|дизайн|artist|animator"),
    ("security", r"security|cyber|infosec|pentest|безпек"),
    ("database", r"\bdba\b|database|база даних"),
    ("qa", r"\bqa\b|\baqa\b|\bqc\b|tester|тестув|тестиров|quality"),
    (
        "devops",
        r"devops|sysadmin|sys admin|системн\w* админ|системн\w* адмін|\bsre\b|администратор",
    ),
    ("data", r"data scien\w*|machine learning|\bml\b|data engineer|big data|\bai\b"),
    ("analyst", r"analyst|аналітик|аналитик"),
    ("management", r"\bdirector\b|\bcto\b|\bceo\b|\bcoo\b|\bchro\b|\bvp\b|керівник|руководитель"),
    ("project_manager", r"project|product|program|delivery|scrum|\bpm\b|producer|owner"),
    ("frontend_coder", r"html coder|верстальщик|верстальник|front-?end"),
    ("management", r"\bdirector\b|\bhead\b|\bcto\b|\bceo\b|\bmanager\b|керівник|руководитель"),
    (
        "software_engineer",
        r"software|developer|programmer|engineer|разработчик|розробник|програміст|архітектор"
        r"|architect|\bse\b|\blead\b|\bmiddle\b|\bsenior\b|\bjunior\b|\bmid\b|\bstaff\b"
        r"|principal|c#|\.net|\bjava\b|\bphp\b|c\+\+|python|javascript|golang|\bios\b|android"
        r"|\berp\b|\bcrm\b|embedded|mobile|\bruby\b|oracle|\bsap\b|firmware",
    ),
)
_ROLE_PATTERNS = tuple((role, re.compile(pattern, re.IGNORECASE)) for role, pattern in _ROLES)


def classify_position(raw: str) -> tuple[str, str | None]:
    """(role, seniority) of a survey position; ``other`` and no level when nothing matches.

    A position that lists several levels ("Software Engineer (Junior, Middle, Senior, Team
    Lead)") is the form's menu, not a level, so it gets no seniority.
    """
    levels = [level for level, pattern in _LEVELS if pattern.search(raw)]
    seniority = levels[0] if len(levels) == 1 else None
    for role, pattern in _ROLE_PATTERNS:
        if pattern.search(raw):
            return role, seniority
    return "other", seniority


# ---- cities ------------------------------------------------------------------------------------
_CITY_SPELLING = {
    "киев": "Київ",
    "харьков": "Харків",
    "львов": "Львів",
    "одесса": "Одеса",
    "днепр": "Дніпро",
    "днепропетровск": "Дніпро",
    "винница": "Вінниця",
    "запорожье": "Запоріжжя",
    "ивано-франковск": "Івано-Франківськ",
    "николаев": "Миколаїв",
    "черновцы": "Чернівці",
    "черкассы": "Черкаси",
    "донецк": "Донецьк",
    "хмельницкий": "Хмельницький",
    "тернополь": "Тернопіль",
    "чернигов": "Чернігів",
    "сумы": "Суми",
    "ровно": "Рівне",
    "луцк": "Луцьк",
    "луганск": "Луганськ",
    "кропивницкий": "Кропивницький",
    "кировоград": "Кропивницький",
    "мариуполь": "Маріуполь",
    "кривой рог": "Кривий Ріг",
    "симферополь": "Сімферополь",
}
_REGION_TAIL = re.compile(r"\s+чи\s+.*область$|\s+чи\s+область$", re.IGNORECASE)
_ABROAD = re.compile(r"^за кордоном|^не україна", re.IGNORECASE)
_REMOTE = re.compile(r"^(удаленно|віддалено)$", re.IGNORECASE)
_UNSPECIFIED = re.compile(r"^(в україні|інше|другой)$", re.IGNORECASE)


def classify_city(raw: str) -> tuple[str, str]:
    """(city, group) where group is ukraine | abroad | remote | unspecified."""
    text = re.sub(r"\s+", " ", raw).strip()
    if _ABROAD.search(text):
        return "За кордоном", "abroad"
    if _REMOTE.match(text):
        return "Віддалено", "remote"
    if _UNSPECIFIED.match(text):
        return "Не вказано", "unspecified"
    if re.match(r"^донецька чи луганська область$", text, re.IGNORECASE):
        return "Донецька/Луганська область", "ukraine"
    city = _REGION_TAIL.sub("", text)
    return _CITY_SPELLING.get(city.casefold(), city), "ukraine"


# ---- writing the seeds -------------------------------------------------------------------------
def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_seeds(silver: SilverStore, directory: Path = SEEDS_DIR) -> dict[str, float]:
    """Write position_map.csv and city_map.csv from the survey values in silver.

    Returns, per seed, the share (by survey weight) that fell into the catch-all bucket, so a
    mapping that stops covering the data is visible.
    """
    positions = silver._con.execute(
        "SELECT position, sum(weight) FROM silver_dou_salaries WHERE position IS NOT NULL "
        "GROUP BY position ORDER BY position"
    ).fetchall()
    cities = silver._con.execute(
        "SELECT city, sum(weight) FROM silver_dou_salaries WHERE city IS NOT NULL "
        "GROUP BY city ORDER BY city"
    ).fetchall()

    position_rows, other_weight, total = [], 0.0, 0.0
    for raw, weight in positions:
        role, seniority = classify_position(raw)
        position_rows.append([raw, role, seniority or ""])
        total += weight
        other_weight += weight if role == "other" else 0.0
    _write(directory / "position_map.csv", ["position_raw", "role", "seniority"], position_rows)

    city_rows = []
    unspecified, city_total = 0.0, 0.0
    for raw, weight in cities:
        city, group = classify_city(raw)
        city_rows.append([raw, city, group])
        city_total += weight
        unspecified += weight if group == "unspecified" else 0.0
    _write(directory / "city_map.csv", ["city_raw", "city", "city_group"], city_rows)
    return {
        "positions_other": other_weight / total if total else 0.0,
        "cities_unspecified": unspecified / city_total if city_total else 0.0,
    }
