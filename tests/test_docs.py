"""The documentation points at things that exist: files it links to and make targets it names."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PAGES = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
MAKE = re.compile(r"`make ([a-z][a-z-]*)")
TARGETS = set(re.findall(r"^([a-z][a-z-]*):", (ROOT / "Makefile").read_text(), flags=re.M))


def _relative_links(page: Path) -> list[str]:
    found = LINK.findall(page.read_text(encoding="utf-8"))
    return [link for link in found if not link.startswith(("http://", "https://", "mailto:", "#"))]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_relative_link_points_at_an_existing_file(page: Path) -> None:
    for link in _relative_links(page):
        target = (page.parent / link.split("#")[0]).resolve()
        assert target.exists(), f"{page.relative_to(ROOT)} links to {link}, which does not exist"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_make_target_the_docs_name_exists(page: Path) -> None:
    for target in MAKE.findall(page.read_text(encoding="utf-8")):
        assert target in TARGETS, (
            f"{page.relative_to(ROOT)} names `make {target}`, which is not a target"
        )


def test_the_readme_is_not_the_old_phase_one_note() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Status: phase 1" not in text and "## Reliability" in text
