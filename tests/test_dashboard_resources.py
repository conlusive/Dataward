from pathlib import Path

import pytest

from jobmarket import dashboard_resources as rs
from jobmarket.skills.taxonomy import load_taxonomy


def test_every_curated_skill_is_in_the_taxonomy() -> None:
    names = {skill.name for skill in load_taxonomy().skills.values()}

    assert set(rs.load()) <= names


def test_every_resource_is_an_https_link_with_a_known_kind_and_language() -> None:
    for skill, items in rs.load().items():
        for item in items:
            assert item.url.startswith("https://") and item.title, (skill, item)
            assert item.kind in rs.KINDS and item.lang in rs.LANG_LABELS


def test_a_skill_does_not_list_the_same_link_twice() -> None:
    for skill, items in rs.load().items():
        assert len({i.url for i in items}) == len(items), skill


def test_the_skills_of_the_trainer_all_have_curated_resources() -> None:
    from jobmarket import dashboard_interview as iv

    bank = rs.load()
    for skill in iv.skills_in_bank(iv.load_bank()):
        assert len(bank.get(skill, [])) >= 2, skill


def test_the_first_resource_of_a_skill_is_a_good_place_to_start() -> None:
    first = [items[0] for items in rs.load().values()]

    assert (
        sum(1 for r in first if r.kind in {"docs", "course", "practice", "book"})
        >= len(first) * 0.9
    )


def _file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "r.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_malformed_file_is_refused_with_the_reason(tmp_path: Path) -> None:
    ok = '{title: T, url: "https://a.test", kind: docs, lang: en}'

    with pytest.raises(rs.ResourceError, match="https"):
        rs.load(_file(tmp_path, f"resources:\n  X:\n    - {ok.replace('https', 'http')}\n"))
    with pytest.raises(rs.ResourceError, match="unknown kind"):
        rs.load(_file(tmp_path, f"resources:\n  X:\n    - {ok.replace('docs', 'magic')}\n"))
    with pytest.raises(rs.ResourceError, match="lacks"):
        rs.load(_file(tmp_path, "resources:\n  X:\n    - {title: T}\n"))
    with pytest.raises(rs.ResourceError, match="repeated"):
        rs.load(_file(tmp_path, f"resources:\n  X:\n    - {ok}\n    - {ok}\n"))


def test_a_skill_without_a_list_gets_two_search_links_that_say_they_are_not_curated() -> None:
    links = rs.for_skill("Qwertyuiop", {})

    assert len(links) == 2 and not any(link.curated for link in links)
    assert all(link.kind == "search" for link in links)


def test_search_links_survive_awkward_names() -> None:
    for name in ("C++", "C#", "CI/CD", "Machine Learning", "Node.js & Co"):
        for link in rs.search_links(name):
            assert (
                " " not in link.url
                and "#" not in link.url.split("?", 1)[1]
                and "&" not in link.url.split("q=")[-1].split("search_query=")[-1]
            )


def test_a_curated_skill_is_not_replaced_by_search() -> None:
    assert all(item.curated for item in rs.for_skill("Python"))


def test_progress_counts_the_finished_resources() -> None:
    bank = rs.load()
    first, second = bank["Python"][0].url, bank["Python"][1].url

    assert rs.progress("Python", {first: "2026-11-01", second: "2026-11-02"}, bank)[0] == 2
    assert rs.progress("Python", {}, bank) == (0, len(bank["Python"]))
    assert rs.progress("Unlisted", {first: "d"}, bank) == (0, 0)
