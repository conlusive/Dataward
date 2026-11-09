from pathlib import Path
from typing import Any

import pytest

from jobmarket.lineage import LINEAGE_FILE, build_mermaid, load_manifest, render_page
from tests.test_dbt_lifecycle import DBT

ROOT = Path(__file__).parent.parent

MANIFEST: dict[str, Any] = {
    "nodes": {
        "model.p.stg_a": {
            "resource_type": "model",
            "name": "stg_a",
            "original_file_path": "models/staging/stg_a.sql",
        },
        "model.p.fct_b": {
            "resource_type": "model",
            "name": "fct_b",
            "original_file_path": "models/marts/fct_b.sql",
        },
        "seed.p.map": {
            "resource_type": "seed",
            "name": "map",
            "original_file_path": "seeds/map.csv",
        },
        "snapshot.p.hist": {
            "resource_type": "snapshot",
            "name": "hist",
            "original_file_path": "snapshots/hist.sql",
        },
        "test.p.not_null_b": {
            "resource_type": "test",
            "name": "not_null_b",
            "original_file_path": "models/marts/schema.yml",
        },
    },
    "sources": {"source.p.silver.raw": {"name": "raw"}},
    "parent_map": {
        "model.p.stg_a": ["source.p.silver.raw", "seed.p.map"],
        "model.p.fct_b": ["model.p.stg_a"],
        "test.p.not_null_b": ["model.p.fct_b"],  # a test is not part of the lineage
        "snapshot.p.hist": ["source.p.silver.raw"],
    },
}


def test_nodes_are_grouped_by_layer_and_edges_point_from_parent_to_child() -> None:
    graph = build_mermaid(MANIFEST).splitlines()

    assert graph[0] == "graph LR"
    assert '  subgraph sources["Silver tables written by the Python pipeline"]' in graph
    assert (
        "    src_raw[raw]" in graph and "    stg_a[stg_a]" in graph and "    fct_b[fct_b]" in graph
    )
    assert {
        "  src_raw --> stg_a",
        "  map --> stg_a",
        "  stg_a --> fct_b",
        "  src_raw --> hist",
    } <= set(graph)


def test_tests_are_not_drawn() -> None:
    assert "not_null_b" not in build_mermaid(MANIFEST)


def test_the_output_does_not_depend_on_the_order_of_the_manifest() -> None:
    reordered = {**MANIFEST, "nodes": dict(reversed(MANIFEST["nodes"].items()))}

    assert build_mermaid(reordered) == build_mermaid(MANIFEST)


@pytest.mark.skipif(not DBT.exists(), reason="dbt is not installed")
def test_the_committed_lineage_page_matches_the_dbt_project() -> None:
    expected = render_page(load_manifest(ROOT / "warehouse"))

    assert (ROOT / LINEAGE_FILE).read_text(encoding="utf-8") == expected, "run `make lineage`"
