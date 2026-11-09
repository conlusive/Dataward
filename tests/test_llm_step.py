import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from jobmarket.ops import OpsStore
from jobmarket.silver.model import ParsedVacancy
from jobmarket.silver.store import SilverStore
from jobmarket.skills import llm_step
from jobmarket.skills.llm import LlmError, Reply, Usage
from jobmarket.skills.llm_step import (
    cache_key,
    refresh_unknown_skills,
    renormalize_llm_skills,
    run_llm_extraction,
)
from jobmarket.skills.normalize import Normalizer
from jobmarket.skills.taxonomy import Skill, Taxonomy, load_taxonomy

TAXONOMY = load_taxonomy()
NORMALIZER = Normalizer(TAXONOMY)


class FakeClient:
    """Answers from a table keyed by a word of the vacancy; counts every request."""

    model = "gpt-4o-mini"

    def __init__(
        self, answers: dict[str, list[tuple[str, str]]], *, tokens: tuple[int, int] = (1000, 100)
    ) -> None:
        self._answers = answers
        self._tokens = tokens
        self.requests: list[str] = []
        self.fail_on: str | None = None

    async def complete(self, system: str, user: str) -> Reply:
        self.requests.append(user)
        if self.fail_on and self.fail_on in user:
            raise LlmError("boom")
        skills: list[dict[str, str]] = []
        for word, found in self._answers.items():
            if word in user:
                skills += [{"name": name, "importance": importance} for name, importance in found]
        return Reply(json.dumps({"skills": skills}), Usage(*self._tokens))


@pytest.fixture
def stores(tmp_path: Path) -> tuple[SilverStore, OpsStore]:
    return SilverStore(tmp_path / "test.duckdb"), OpsStore(tmp_path / "test.duckdb")


def _add(silver: SilverStore, vid: str, title: str, description: str) -> None:
    silver.upsert(
        ParsedVacancy(
            id=vid,
            source=vid.split(":")[0],
            url=f"https://example.com/{vid.replace(':', '/')}",
            title=title,
            company="Acme",
            category=None,
            description_text=description,
            published_at=None,
        ),
        run_id="parse-1",
        loaded_at=datetime(2026, 11, 6),
        source_file="x",
        fetched_at=datetime(2026, 11, 6),
    )


def _rows(silver: SilverStore, sql: str) -> list[tuple[Any, ...]]:
    return silver._con.execute(sql).fetchall()


ANSWERS = {
    "ALPHA": [("Python", "required"), ("Kafka", "nice"), ("Quantum basketry", "required")],
    "BETA": [("Postgres", "required"), ("PostgreSQL", "nice"), ("Quantum basketry", "nice")],
}


async def _run(
    silver: SilverStore, ops: OpsStore, client: FakeClient, **kwargs: Any
) -> llm_step.LlmRunStats:
    return await run_llm_extraction(
        silver, ops, client, NORMALIZER, source=None, run_id=kwargs.pop("run_id", "llm-1"), **kwargs
    )


async def test_skills_terms_and_unknown_skills_are_written(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    _add(silver, "dou:2", "Dev", "BETA needs things")

    stats = await _run(silver, ops, FakeClient(ANSWERS))

    assert (stats.vacancies, stats.calls, stats.cache_hits, stats.failed) == (2, 2, 0, 0)
    assert _rows(
        silver,
        "SELECT vacancy_id, skill_id, importance, confidence, model, prompt_version "
        "FROM silver_vacancy_skills WHERE method = 'llm' ORDER BY 1, 2",
    ) == [
        ("dou:1", "kafka", "nice", 0.9, "gpt-4o-mini", "extract_v1"),
        ("dou:1", "python", "required", 0.9, "gpt-4o-mini", "extract_v1"),
        (
            "dou:2",
            "postgresql",
            "required",
            0.9,
            "gpt-4o-mini",
            "extract_v1",
        ),  # "Postgres" and "PostgreSQL" collapse
    ]
    assert _rows(silver, "SELECT term, vacancies, status FROM silver_unknown_skills") == [
        ("quantum basketry", 2, "new")
    ]
    assert _rows(
        silver, "SELECT calls, cache_hits, prompt_tokens, completion_tokens FROM ops_llm_usage"
    ) == [(2, 0, 2000, 200)]


async def test_a_second_run_asks_nothing_and_changes_nothing(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    first_client = FakeClient(ANSWERS)
    await _run(silver, ops, first_client)
    before = _rows(
        silver, "SELECT * EXCLUDE (_run_id, _loaded_at) FROM silver_vacancy_skills ORDER BY 1, 2"
    )

    second_client = FakeClient(ANSWERS)
    stats = await _run(silver, ops, second_client, run_id="llm-2")

    assert second_client.requests == [] and (stats.calls, stats.cache_hits) == (0, 1)
    assert (
        _rows(
            silver,
            "SELECT * EXCLUDE (_run_id, _loaded_at) FROM silver_vacancy_skills ORDER BY 1, 2",
        )
        == before
    )


async def test_only_the_changed_vacancy_is_asked_again(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    _add(silver, "dou:2", "Dev", "BETA needs things")
    await _run(silver, ops, FakeClient(ANSWERS))

    _add(silver, "dou:2", "Dev", "BETA needs other things")
    client = FakeClient(ANSWERS)
    stats = await _run(silver, ops, client, run_id="llm-2")

    assert len(client.requests) == 1 and "other things" in client.requests[0]
    assert (stats.calls, stats.cache_hits) == (1, 1)


async def test_identical_vacancies_share_one_request(stores: tuple[SilverStore, OpsStore]) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    _add(silver, "djinni:1", "Dev", "ALPHA needs things")
    client = FakeClient(ANSWERS)

    stats = await _run(silver, ops, client)

    assert len(client.requests) == 1 and stats.calls == 1
    assert _rows(
        silver, "SELECT count(DISTINCT vacancy_id) FROM silver_vacancy_skills WHERE method = 'llm'"
    ) == [(2,)]


def test_the_cache_key_changes_with_anything_that_changes_the_answer() -> None:
    base = {"model": "m", "prompt_version": "v1", "prompt": "P"}
    key = cache_key("Title", "hash", **base)

    assert key == cache_key("Title", "hash", **base)
    assert key != cache_key("Other title", "hash", **base)
    assert key != cache_key("Title", "other hash", **base)
    assert key != cache_key("Title", "hash", **{**base, "model": "m2"})
    assert key != cache_key("Title", "hash", **{**base, "prompt_version": "v2"})
    assert key != cache_key("Title", "hash", **{**base, "prompt": "P edited without a new version"})


async def test_limit_stops_early_and_leaves_the_rest_untouched(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    _add(silver, "dou:2", "Dev", "BETA needs things")

    stats = await _run(silver, ops, FakeClient(ANSWERS), limit=1)

    assert (stats.calls, stats.not_run) == (1, 1)
    assert _rows(silver, "SELECT DISTINCT vacancy_id FROM silver_llm_terms") == [("dou:1",)]


async def test_only_the_listed_vacancies_are_asked_and_the_others_are_left_alone(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    _add(silver, "dou:2", "Dev", "BETA needs things")
    _add(silver, "dou:3", "Dev", "ALPHA needs other things")
    client = FakeClient(ANSWERS)

    stats = await _run(silver, ops, client, only_ids={"dou:1", "dou:3"})

    assert (stats.vacancies, stats.calls) == (2, 2) and len(client.requests) == 2
    assert not any("BETA" in request for request in client.requests)
    assert _rows(silver, "SELECT DISTINCT vacancy_id FROM silver_llm_terms ORDER BY 1") == [
        ("dou:1",),
        ("dou:3",),
    ]


async def test_the_cost_cap_stops_new_batches(
    stores: tuple[SilverStore, OpsStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    silver, ops = stores
    monkeypatch.setattr(llm_step, "BATCH_SIZE", 1)
    for i in range(4):
        _add(silver, f"dou:{i}", "Dev", f"ALPHA task {i}")
    client = FakeClient(ANSWERS, tokens=(1_000_000, 0))  # $0.15 per request with gpt-4o-mini prices

    stats = await _run(silver, ops, client, max_cost_usd=0.2)

    assert stats.calls == 2 and stats.not_run == 2
    assert stats.cost_usd == pytest.approx(0.30)


async def test_a_dry_run_counts_and_estimates_but_calls_and_writes_nothing(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    client = FakeClient(ANSWERS)

    stats = await _run(silver, ops, client, dry_run=True)

    assert client.requests == [] and stats.estimated and stats.calls == 1 and stats.cost_usd > 0
    assert _rows(silver, "SELECT count(*) FROM llm_cache") == [(0,)]
    assert _rows(silver, "SELECT count(*) FROM ops_llm_usage") == [(0,)]


async def test_one_failing_vacancy_does_not_stop_the_others(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    _add(silver, "dou:2", "Dev", "BETA needs things")
    client = FakeClient(ANSWERS)
    client.fail_on = "BETA"

    stats = await _run(silver, ops, client)

    assert (stats.calls, stats.failed) == (1, 1)
    assert _rows(
        silver, "SELECT DISTINCT vacancy_id FROM silver_vacancy_skills WHERE method = 'llm'"
    ) == [("dou:1",)]
    assert _rows(silver, "SELECT count(*) FROM llm_cache") == [(1,)]  # the failure is not cached


async def test_a_vacancy_that_fails_later_keeps_the_skills_it_already_had(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:2", "Dev", "BETA needs things")
    await _run(silver, ops, FakeClient(ANSWERS))
    before = _rows(silver, "SELECT skill_id FROM silver_vacancy_skills WHERE method = 'llm'")
    assert before  # it had skills

    _add(silver, "dou:2", "Dev", "BETA needs changed things")  # new text, so it must be asked again
    client = FakeClient(ANSWERS)
    client.fail_on = "BETA"
    stats = await _run(silver, ops, client, run_id="llm-2")

    assert stats.failed == 1
    assert (
        _rows(silver, "SELECT skill_id FROM silver_vacancy_skills WHERE method = 'llm'") == before
    )
    assert _rows(silver, "SELECT count(*) FROM silver_llm_terms") != [(0,)]


async def test_every_fresh_answer_is_also_kept_as_a_json_line(
    stores: tuple[SilverStore, OpsStore], tmp_path: Path
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    raw_dir = tmp_path / "llm_raw"

    await _run(silver, ops, FakeClient(ANSWERS), raw_dir=raw_dir)

    (file,) = raw_dir.glob("dt=*/calls.jsonl")
    line = json.loads(file.read_text(encoding="utf-8").splitlines()[0])
    assert (
        line["model"] == "gpt-4o-mini"
        and "Python" in line["answer"]
        and line["prompt_tokens"] == 1000
    )


async def test_review_decisions_on_unknown_terms_survive_a_refresh(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    await _run(silver, ops, FakeClient(ANSWERS))
    silver._con.execute("UPDATE silver_unknown_skills SET status = 'rejected'")

    refresh_unknown_skills(silver, NORMALIZER)

    assert _rows(silver, "SELECT term, status FROM silver_unknown_skills") == [
        ("quantum basketry", "rejected")
    ]


async def test_a_taxonomy_change_is_applied_without_asking_the_model_again(
    stores: tuple[SilverStore, OpsStore],
) -> None:
    silver, ops = stores
    _add(silver, "dou:1", "Dev", "ALPHA needs things")
    await _run(silver, ops, FakeClient(ANSWERS))
    assert _rows(silver, "SELECT count(*) FROM silver_unknown_skills") == [(1,)]
    basketry = Skill(
        "quantum-basketry", "Quantum basketry", "tool", None, (), False, (), None, True
    )
    bigger = Taxonomy(TAXONOMY.categories, {**TAXONOMY.skills, basketry.id: basketry})

    rewritten = renormalize_llm_skills(silver, Normalizer(bigger), run_id="renormalize")

    assert rewritten == 1
    assert ("dou:1", "quantum-basketry", "required") in _rows(
        silver,
        "SELECT vacancy_id, skill_id, importance FROM silver_vacancy_skills WHERE method = 'llm'",
    )
    assert _rows(silver, "SELECT count(*) FROM silver_unknown_skills") == [(0,)]
    assert _rows(silver, "SELECT count(*) FROM llm_cache") == [(1,)]
