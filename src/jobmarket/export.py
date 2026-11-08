"""Gold marts -> parquet files for the dashboards and notebooks, plus `last_update.json`.

The columns and types of every published table are the dbt contracts in `warehouse/models/marts/`
(one source of truth). A table whose real columns differ from its contract is not exported, and
nothing is written unless every table passes, so a consumer never sees a half-updated set.
"""

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import yaml

SCHEMA_FILE = Path("warehouse/models/marts/schema.yml")
EXPORT_DIR = Path("data/export")
SUMMARY_FILE = "last_update.json"


class ExportError(Exception):
    """A table is missing or does not match its contract."""


def contracts(schema_file: Path = SCHEMA_FILE) -> dict[str, list[tuple[str, str]]]:
    """model name -> [(column, type)] for every model with an enforced contract."""
    schema = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
    found: dict[str, list[tuple[str, str]]] = {}
    for model in schema.get("models", []):
        if not (model.get("config", {}).get("contract") or {}).get("enforced"):
            continue
        found[model["name"]] = [(c["name"], str(c["data_type"]).upper()) for c in model["columns"]]
    return found


def _check(con: duckdb.DuckDBPyConnection, table: str, expected: list[tuple[str, str]]) -> None:
    rows = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    if not rows:
        raise ExportError(f"{table}: table not found (run `make dbt-build` first)")
    actual = [(name, str(kind).upper()) for name, kind in rows]
    if actual != expected:
        raise ExportError(f"{table}: columns {actual} do not match the contract {expected}")


def export_gold(
    db_path: Path,
    *,
    schema_file: Path = SCHEMA_FILE,
    out_dir: Path = EXPORT_DIR,
    now: datetime | None = None,
) -> dict[str, int]:
    """Write one parquet file per contracted table and `last_update.json`; returns row counts."""
    expected = contracts(schema_file)
    if not expected:
        raise ExportError(f"no contracted models in {schema_file}")
    staging = out_dir.with_name(out_dir.name + ".tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for table, columns in expected.items():
            _check(con, table, columns)
        counts: dict[str, int] = {}
        files: dict[str, dict[str, object]] = {}
        for table in expected:
            target = staging / f"{table}.parquet"
            # table names come from our own schema.yml, never from user input
            con.execute(f"COPY (SELECT * FROM {table}) TO '{target}' (FORMAT parquet)")
            counts[table] = int(con.execute(f"SELECT count(*) FROM {table}").fetchall()[0][0])
            files[table] = {
                "rows": counts[table],
                "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        con.close()

    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    (staging / SUMMARY_FILE).write_text(
        json.dumps({"exported_at": stamp, "tables": files}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(out_dir, ignore_errors=True)
    staging.rename(out_dir)
    return counts
