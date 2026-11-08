"""Table contracts for the silver layer (`contracts/silver.yml`) checked against a real database.

A contract lists the columns, types, nullability and primary key a table must have. Column order is
not part of it: migrations append columns, so an old database has them in a different order. gold
and the exports read these tables, so a drift is reported as a list of violations, never silently.
"""

from dataclasses import dataclass
from pathlib import Path

import duckdb
import yaml

SILVER_CONTRACT = Path("contracts/silver.yml")


@dataclass(frozen=True)
class TableContract:
    columns: dict[str, tuple[str, bool]]  # name -> (type, nullable)
    primary_key: tuple[str, ...]


def load_contracts(path: Path = SILVER_CONTRACT) -> dict[str, TableContract]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        table: TableContract(
            columns={
                c["name"]: (str(c["type"]).upper(), bool(c["nullable"])) for c in spec["columns"]
            },
            primary_key=tuple(spec.get("primary_key", ())),
        )
        for table, spec in raw["tables"].items()
    }


def violations(con: duckdb.DuckDBPyConnection, contracts: dict[str, TableContract]) -> list[str]:
    """Human-readable differences between the database and the contracts (empty = all good)."""
    found: list[str] = []
    for table, contract in contracts.items():
        rows = con.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table],
        ).fetchall()
        if not rows:
            found.append(f"{table}: table is missing")
            continue
        actual = {name: (str(kind).upper(), nullable == "YES") for name, kind, nullable in rows}
        for name, (kind, nullable) in contract.columns.items():
            if name not in actual:
                found.append(f"{table}.{name}: column is missing")
            elif actual[name] != (kind, nullable):
                found.append(
                    f"{table}.{name}: is {_describe(actual[name])}, contract says "
                    f"{_describe((kind, nullable))}"
                )
        found.extend(
            f"{table}.{name}: column is not in the contract"
            for name in actual
            if name not in contract.columns
        )
        key = con.execute(
            "SELECT constraint_column_names FROM duckdb_constraints() "
            "WHERE table_name = ? AND constraint_type = 'PRIMARY KEY'",
            [table],
        ).fetchall()
        actual_key = tuple(key[0][0]) if key else ()
        if actual_key != contract.primary_key:
            found.append(
                f"{table}: primary key is {list(actual_key)}, contract says "
                f"{list(contract.primary_key)}"
            )
    return found


def _describe(column: tuple[str, bool]) -> str:
    return f"{column[0]} {'NULL' if column[1] else 'NOT NULL'}"
