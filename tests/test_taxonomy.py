from typing import Any

import pytest

from jobmarket.skills.taxonomy import TaxonomyError, load_taxonomy, validate


def _raw(*skills: dict[str, Any]) -> dict[str, Any]:
    return {"categories": ["language", "tool"], "skills": list(skills)}


def _skill(id_: str = "python", **extra: Any) -> dict[str, Any]:
    return {"id": id_, "name": id_.title(), "category": "language", **extra}


def test_the_shipped_taxonomy_is_valid_and_big_enough() -> None:
    taxonomy = load_taxonomy()

    assert len(taxonomy.skills) >= 400
    assert all(s.context for s in taxonomy.skills.values() if s.strict)
    assert "python" in taxonomy.skills and taxonomy.skills["spring-boot"].parent == "spring"


def test_a_valid_minimal_taxonomy_has_no_problems() -> None:
    assert validate(_raw(_skill("python"), _skill("django", parent="python"))) == []


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        (_raw(_skill("python"), _skill("python")), "used 2 times"),
        (_raw(_skill("Python")), "lower-case slug"),
        (_raw(_skill("python", category="nope")), "unknown category"),
        (_raw(_skill("python", parent="ghost")), "parent 'ghost' does not exist"),
        (_raw(_skill("python", parent="python")), "does not exist"),
        (_raw(_skill("go", strict=True)), "needs `context`"),
        (_raw(_skill("a", aliases=["x"]), _skill("b", aliases=["X"])), "belongs to several skills"),
        (_raw(_skill("a", aliases=["x", "X"])), "repeated alias"),
        (_raw(_skill("a", aliases=[" "])), "empty alias"),
        (_raw(_skill("a"), _skill("b", aliases=["a"])), "belongs to several skills"),
    ],
)
def test_each_rule_is_enforced(raw: dict[str, Any], fragment: str) -> None:
    assert any(fragment in problem for problem in validate(raw))


def test_a_name_that_is_not_an_alias_does_not_collide() -> None:
    raw = _raw(
        _skill("monitoring", name_is_alias=False, aliases=["observability"]),
        _skill("m", name="Monitoring"),
    )

    assert validate(raw) == []


def test_loading_an_invalid_file_lists_every_problem(tmp_path: Any) -> None:
    path = tmp_path / "t.yaml"
    path.write_text(
        "categories: [language]\nskills:\n"
        "  - {id: a, name: A, category: nope}\n"
        "  - {id: a, name: A2, category: language}\n",
        encoding="utf-8",
    )

    with pytest.raises(TaxonomyError) as error:
        load_taxonomy(path)

    assert "unknown category" in str(error.value) and "used 2 times" in str(error.value)
