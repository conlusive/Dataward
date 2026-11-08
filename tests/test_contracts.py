from pathlib import Path

import duckdb
import pytest

from jobmarket.contracts import SILVER_CONTRACT, TableContract, load_contracts, violations
from jobmarket.silver.store import SilverStore


def test_a_fresh_silver_database_satisfies_the_silver_contract(tmp_path: Path) -> None:
    SilverStore(tmp_path / "t.duckdb").close()
    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)

    assert violations(con, load_contracts(SILVER_CONTRACT)) == []


def test_a_database_from_before_the_migrations_is_brought_to_the_contract(tmp_path: Path) -> None:
    path = tmp_path / "old.duckdb"
    SilverStore(path).close()
    con = duckdb.connect(str(path))
    for column in ("experience_years_text", "seniority"):  # what the migrations add
        con.execute(f"ALTER TABLE silver_vacancies DROP COLUMN {column}")
    assert violations(con, load_contracts(SILVER_CONTRACT)) != []
    con.close()

    SilverStore(path).close()  # opening the store runs the migrations
    con = duckdb.connect(str(path), read_only=True)

    assert violations(con, load_contracts(SILVER_CONTRACT)) == []


CONTRACT = {
    "t": TableContract(
        columns={"id": ("INTEGER", False), "name": ("VARCHAR", True)}, primary_key=("id",)
    )
}


@pytest.mark.parametrize(
    ("ddl", "expected"),
    [
        ("CREATE TABLE t (id INTEGER PRIMARY KEY, name VARCHAR)", []),
        ("CREATE TABLE t (name VARCHAR, id INTEGER PRIMARY KEY)", []),  # order is not part of it
        ("CREATE TABLE t (id INTEGER PRIMARY KEY)", ["t.name: column is missing"]),
        (
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name VARCHAR, extra INTEGER)",
            ["t.extra: column is not in the contract"],
        ),
        (
            "CREATE TABLE t (id BIGINT PRIMARY KEY, name VARCHAR)",
            ["t.id: is BIGINT NOT NULL, contract says INTEGER NOT NULL"],
        ),
        (
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)",
            ["t.name: is VARCHAR NOT NULL, contract says VARCHAR NULL"],
        ),
        (
            "CREATE TABLE t (id INTEGER NOT NULL, name VARCHAR)",
            ["t: primary key is [], contract says ['id']"],
        ),
    ],
)
def test_each_kind_of_drift_is_reported(ddl: str, expected: list[str]) -> None:
    con = duckdb.connect()
    con.execute(ddl)

    assert violations(con, CONTRACT) == expected


def test_a_missing_table_is_reported() -> None:
    assert violations(duckdb.connect(), CONTRACT) == ["t: table is missing"]
