"""DOU salary survey waves: bronze CSV -> silver_dou_salaries rows."""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

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

COLUMNS_FILE = Path(__file__).with_name("dou_salaries_columns.yaml")
_MONTHS = {"october": 10, "may": 5, "june": 6, "jun": 6, "dec": 12}
_STEM = re.compile(r"^(\d{4})_([a-z]+)(?:_.+)?$")


@dataclass(frozen=True)
class SurveyRow:
    row_no: int  # position of the answer in its file, 1-based
    position: str | None
    experience_years: float | None
    city: str | None
    english: str | None
    company_size: str | None
    company_type: str | None
    salary_usd: float
    weight: float


@dataclass
class WaveStats:
    rows: int = 0
    kept: int = 0
    subtotals: int = 0  # cross-tab subtotal rows: counting them would repeat respondents
    no_salary: int = 0  # empty or not a USD amount
    outliers: int = 0  # outside MIN_SALARY_USD..MAX_SALARY_USD


@dataclass(frozen=True)
class Schema:
    columns: dict[str, str]
    encoding: str = "utf-8-sig"
    delimiter: str = ","
    weight: str | None = None
    skip_rows: dict[str, list[str]] = field(default_factory=dict)


def load_schemas(path: Path = COLUMNS_FILE) -> dict[str, Schema]:
    """file stem -> schema, from the YAML mapping."""
    config: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    schemas: dict[str, Schema] = {}
    for entry in config["schemas"]:
        schema = Schema(
            columns=entry["columns"],
            encoding=entry.get("encoding", "utf-8-sig"),
            delimiter=entry.get("delimiter", ","),
            weight=entry.get("weight"),
            skip_rows=entry.get("skip_rows", {}),
        )
        for stem in entry["files"]:
            if stem in schemas:
                raise ValueError(f"{stem} is listed in two schemas")
            schemas[stem] = schema
    return schemas


def wave_date(stem: str) -> date:
    """First day of the survey month, from a name like ``2024_june_raw``."""
    match = _STEM.match(stem)
    if match is None or match.group(2) not in _MONTHS:
        raise ValueError(f"cannot read the survey month from {stem!r}")
    return date(int(match.group(1)), _MONTHS[match.group(2)], 1)


def _normalise_header(header: str) -> str:
    return re.sub(r"\s+", " ", header.replace("﻿", "")).strip()


def _column_index(header: list[str], wanted: str) -> int:
    """First column named ``wanted``; a longer header that starts with it also matches."""
    name = _normalise_header(wanted)
    for index, candidate in enumerate(header):
        if candidate == name:
            return index
    for index, candidate in enumerate(header):
        if candidate.startswith(name):
            return index
    raise KeyError(f"column {wanted!r} not found")


def _same(cell_value: str, expected: str) -> bool:
    return re.sub(r"\s+", " ", cell_value).strip().casefold() == expected.casefold()


def parse_wave(content: bytes, schema: Schema) -> tuple[list[SurveyRow], WaveStats]:
    rows = list(
        csv.reader(io.StringIO(content.decode(schema.encoding)), delimiter=schema.delimiter)
    )
    header = [_normalise_header(h) for h in rows[0]]
    index = {field: _column_index(header, column) for field, column in schema.columns.items()}
    weight_index = _column_index(header, schema.weight) if schema.weight else None

    def cell(row: list[str], field: str) -> str:
        position = index.get(field)
        return row[position] if position is not None and position < len(row) else ""

    stats = WaveStats()
    parsed: list[SurveyRow] = []
    for number, row in enumerate(rows[1:], start=1):
        if not row:
            continue
        stats.rows += 1
        if any(
            _same(cell(row, name), value)
            for name, values in schema.skip_rows.items()
            for value in values
        ):
            stats.subtotals += 1
            continue
        salary = parse_survey_salary(cell(row, "salary"))
        if salary is None:
            stats.no_salary += 1
            continue
        if not is_plausible_salary(salary):
            stats.outliers += 1
            continue
        weight = 1.0
        if weight_index is not None:
            weight = (
                float(row[weight_index].replace(",", ".")) if row[weight_index].strip() else 1.0
            )
        parsed.append(
            SurveyRow(
                row_no=number,
                position=clean_text(cell(row, "position")),
                experience_years=parse_experience_years(cell(row, "experience")),
                city=clean_text(cell(row, "city")),
                english=lookup(ENGLISH_LEVELS, cell(row, "english")),
                company_size=lookup(COMPANY_SIZES, cell(row, "company_size")),
                company_type=lookup(COMPANY_TYPES, cell(row, "company_type")),
                salary_usd=round(salary, 2),
                weight=weight,
            )
        )
        stats.kept += 1
    return parsed, stats
