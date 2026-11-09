"""Where to learn a skill: a curated list of resources and a search fallback for the rest.

No Streamlit import. The list is ``learning_resources.yaml`` (official docs first, then practice and
courses); a skill without an entry gets two search links instead, marked as not curated. What the
person has finished is kept in the profile (``Profile.done``: resource url -> day).
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

import yaml

RESOURCES_FILE = Path(__file__).with_name("learning_resources.yaml")
KINDS = ("docs", "practice", "course", "roadmap", "book", "search")
KIND_LABELS = {
    "docs": "документація", "practice": "практика", "course": "курс", "roadmap": "роадмап",
    "book": "книга", "search": "пошук",
}  # fmt: skip
LANG_LABELS = {"uk": "укр", "en": "англ"}


class ResourceError(Exception):
    """The resource file is malformed."""


@dataclass(frozen=True)
class Resource:
    title: str
    url: str
    kind: str
    lang: str
    note: str = ""
    curated: bool = True


def load(path: Path = RESOURCES_FILE) -> dict[str, list[Resource]]:
    """Every curated resource by skill, checked: https links, a known kind and language."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    found: dict[str, list[Resource]] = {}
    for skill, items in (raw.get("resources") or {}).items():
        seen: set[str] = set()
        for item in items:
            try:
                resource = Resource(
                    title=str(item["title"]).strip(), url=str(item["url"]).strip(),
                    kind=str(item["kind"]), lang=str(item["lang"]), note=str(item.get("note", "")),
                )  # fmt: skip
            except KeyError as error:
                raise ResourceError(f"{skill}: a resource lacks {error}") from error
            if not resource.url.startswith("https://"):
                raise ResourceError(f"{skill}: {resource.url} is not an https link")
            if resource.kind not in KINDS or resource.lang not in LANG_LABELS:
                raise ResourceError(f"{skill}: unknown kind or language in {resource.title!r}")
            if not resource.title or resource.url in seen:
                raise ResourceError(f"{skill}: an empty title or a repeated link")
            seen.add(resource.url)
            found.setdefault(str(skill), []).append(resource)
    return found


def search_links(skill: str) -> list[Resource]:
    """Two search links for a skill nobody curated: not recommendations, a place to start."""
    query = quote_plus(f"{skill} tutorial for beginners")
    return [
        Resource(f"Пошук: {skill} для початківців", f"https://www.google.com/search?q={query}",
                 "search", "en", curated=False),
        Resource(f"YouTube: {skill} для початківців",
                 f"https://www.youtube.com/results?search_query={query}", "search", "en",
                 curated=False),
    ]  # fmt: skip


def for_skill(skill: str, bank: dict[str, list[Resource]] | None = None) -> list[Resource]:
    """The curated resources of a skill, or search links when there are none."""
    bank = load() if bank is None else bank
    return bank.get(skill) or search_links(skill)


def progress(skill: str, done: dict[str, str], bank: dict[str, list[Resource]]) -> tuple[int, int]:
    """(finished, total) of a skill's curated resources; (0, 0) when it has none."""
    curated = bank.get(skill, [])
    return sum(1 for r in curated if r.url in done), len(curated)


def skills_with_resources(bank: dict[str, list[Resource]]) -> list[str]:
    """The skills that have a curated list, alphabetically."""
    return sorted(bank)
