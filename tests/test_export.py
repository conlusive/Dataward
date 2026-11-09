import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from jobmarket.export import (
    SCHEMA_FILE,
    ExportError,
    contracts,
    export_gold,
    private_tables,
    publish_copy,
)

SCHEMA = """
version: 2
models:
  - name: dim_thing
    config: {contract: {enforced: true}}
    columns:
      - name: thing_id
        data_type: varchar
      - name: size
        data_type: integer
  - name: not_published
    columns:
      - name: x
        data_type: integer
"""


@pytest.fixture
def schema(tmp_path: Path) -> Path:
    path = tmp_path / "schema.yml"
    path.write_text(SCHEMA, encoding="utf-8")
    return path


def _database(tmp_path: Path, create: str) -> Path:
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.execute(create)
    con.close()
    return path


GOOD = "CREATE TABLE dim_thing AS SELECT 'a' AS thing_id, 3 AS size UNION ALL SELECT 'b', 4"


def test_only_models_with_an_enforced_contract_are_published(schema: Path) -> None:
    assert contracts(schema) == {"dim_thing": [("thing_id", "VARCHAR"), ("size", "INTEGER")]}


def test_the_real_project_publishes_its_marts() -> None:
    published = set(contracts(SCHEMA_FILE))

    assert {"dim_skill", "fct_skill_pairs", "fct_vacancy_daily"} <= published


def test_a_table_is_written_as_parquet_with_a_summary(tmp_path: Path, schema: Path) -> None:
    db = _database(tmp_path, GOOD)
    out = tmp_path / "export"
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

    counts = export_gold(db, schema_file=schema, out_dir=out, now=now)

    assert counts == {"dim_thing": 2}
    rows = (
        duckdb.connect()
        .execute(f"SELECT thing_id, size FROM '{out / 'dim_thing.parquet'}' ORDER BY 1")
        .fetchall()
    )
    assert rows == [("a", 3), ("b", 4)]
    summary = json.loads((out / "last_update.json").read_text(encoding="utf-8"))
    assert summary["exported_at"] == "2026-11-09T12:00:00+00:00"
    assert summary["tables"]["dim_thing"]["rows"] == 2
    assert len(summary["tables"]["dim_thing"]["sha256"]) == 64


def test_a_column_with_the_wrong_type_stops_the_export_and_keeps_the_previous_files(
    tmp_path: Path, schema: Path
) -> None:
    out = tmp_path / "export"
    export_gold(_database(tmp_path, GOOD), schema_file=schema, out_dir=out)
    before = (out / "dim_thing.parquet").read_bytes()
    bad = tmp_path / "bad.duckdb"
    con = duckdb.connect(str(bad))
    con.execute("CREATE TABLE dim_thing AS SELECT 'a' AS thing_id, 'big' AS size")
    con.close()

    with pytest.raises(ExportError, match="do not match the contract"):
        export_gold(bad, schema_file=schema, out_dir=out)

    assert (out / "dim_thing.parquet").read_bytes() == before
    assert not (tmp_path / "export.tmp").exists()


def test_a_missing_table_says_to_build_first(tmp_path: Path, schema: Path) -> None:
    db = _database(tmp_path, "CREATE TABLE other AS SELECT 1 AS x")

    with pytest.raises(ExportError, match="table not found"):
        export_gold(db, schema_file=schema, out_dir=tmp_path / "export")


def test_skill_clusters_are_written_next_to_the_pairs_they_come_from(tmp_path: Path) -> None:
    schema = tmp_path / "schema.yml"
    schema.write_text(
        """
models:
  - name: fct_skill_pairs
    config: {contract: {enforced: true}}
    columns:
      - {name: skill_a, data_type: varchar}
      - {name: skill_b, data_type: varchar}
      - {name: npmi, data_type: double}
""",
        encoding="utf-8",
    )
    db = _database(
        tmp_path,
        "CREATE TABLE fct_skill_pairs AS "
        "SELECT skill_a, skill_b, npmi::DOUBLE AS npmi FROM (VALUES "
        "('python','django',0.8), ('python','flask',0.7), ('django','flask',0.6), "
        "('go','kafka',0.1)) t(skill_a, skill_b, npmi)",
    )
    out = tmp_path / "export"

    counts = export_gold(db, schema_file=schema, out_dir=out)

    assert counts == {"fct_skill_pairs": 4, "skill_clusters": 3}
    rows = (
        duckdb.connect()
        .execute(
            f"SELECT skill_id, cluster_id, cluster_size, cluster_label "
            f"FROM '{out / 'skill_clusters.parquet'}' ORDER BY skill_id"
        )
        .fetchall()
    )
    assert rows == [
        ("django", 1, 3, "python"),
        ("flask", 1, 3, "python"),
        ("python", 1, 3, "python"),
    ]


def test_the_vacancy_catalog_is_private_and_the_workflow_uploads_only_the_public_copy() -> None:
    """The repository is public: listings of other people must not reach the CI artifact."""
    workflow = Path(".github/workflows/pipeline-daily.yml").read_text(encoding="utf-8")

    assert "fct_vacancy_catalog" in private_tables(SCHEMA_FILE)
    assert "uv run jobmarket export-public" in workflow
    upload = workflow[workflow.index("Upload gold export") :]
    assert "path: data/export_public" in upload and "path: data/export\n" not in upload


def _export_with_a_private_table(tmp_path: Path) -> tuple[Path, Path]:
    schema = tmp_path / "schema.yml"
    schema.write_text(
        SCHEMA.replace(
            "  - name: not_published\n",
            "  - name: secret\n    meta: {private: true}\n"
            "    config: {contract: {enforced: true}}\n    columns:\n      - name: x\n"
            "        data_type: integer\n  - name: not_published\n",
        ),
        encoding="utf-8",
    )
    database = _database(
        tmp_path,
        GOOD + "; CREATE TABLE secret AS SELECT 1 AS x",
    )
    export_gold(database, schema_file=schema, out_dir=tmp_path / "export")
    return schema, tmp_path / "export"


def test_the_public_copy_leaves_out_private_tables_and_their_summary_entry(tmp_path: Path) -> None:
    schema, export = _export_with_a_private_table(tmp_path)
    assert (export / "secret.parquet").exists()  # the local export keeps it

    copied = publish_copy(export, tmp_path / "public", schema_file=schema)

    assert copied == ["dim_thing"]
    assert sorted(p.name for p in (tmp_path / "public").iterdir()) == [
        "dim_thing.parquet", "last_update.json",
    ]  # fmt: skip
    summary = json.loads((tmp_path / "public" / "last_update.json").read_text(encoding="utf-8"))
    assert list(summary["tables"]) == ["dim_thing"]
    assert (
        "secret" in json.loads((export / "last_update.json").read_text(encoding="utf-8"))["tables"]
    )


def test_the_public_copy_replaces_the_previous_one_whole(tmp_path: Path) -> None:
    schema, export = _export_with_a_private_table(tmp_path)
    public = tmp_path / "public"
    public.mkdir()
    (public / "stale.parquet").write_text("old", encoding="utf-8")

    publish_copy(export, public, schema_file=schema)

    assert not (public / "stale.parquet").exists()


def test_other_files_of_the_export_are_copied_as_they_are(tmp_path: Path) -> None:
    schema, export = _export_with_a_private_table(tmp_path)
    (export / "status.json").write_text('{"ok": true}', encoding="utf-8")

    publish_copy(export, tmp_path / "public", schema_file=schema)

    assert (tmp_path / "public" / "status.json").read_text(encoding="utf-8") == '{"ok": true}'


def test_there_is_nothing_to_publish_without_an_export(tmp_path: Path) -> None:
    with pytest.raises(ExportError, match="make export"):
        publish_copy(tmp_path / "none", tmp_path / "public")


def test_only_a_model_with_the_meta_flag_is_private(schema: Path, tmp_path: Path) -> None:
    assert private_tables(schema) == set()

    flagged = tmp_path / "flagged.yml"
    flagged.write_text(
        SCHEMA.replace("  - name: dim_thing\n", "  - name: dim_thing\n    meta: {private: true}\n"),
        encoding="utf-8",
    )
    assert private_tables(flagged) == {"dim_thing"}
