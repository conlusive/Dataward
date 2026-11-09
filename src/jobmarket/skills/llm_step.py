"""Method B over silver: extract with the LLM (cached), map onto the taxonomy, record the cost.

Nothing is asked twice: the answer is cached under a key made of the title, the description hash,
the prompt (version and text) and the model. Changing any of them asks again; changing the
taxonomy does not, `renormalize_llm_skills` re-maps the stored answers instead.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from jobmarket.ops import OpsStore
from jobmarket.silver.model import text_hash
from jobmarket.silver.store import SilverStore
from jobmarket.skills.llm import (
    DEFAULT_PROMPT_VERSION,
    ExtractionResult,
    LlmClient,
    LlmError,
    Usage,
    estimate_cost,
    extract,
    load_prompt,
    user_message,
)
from jobmarket.skills.normalize import Normalizer, clean_term

BATCH_SIZE = 40
CONFIDENCE = {"exact": 0.9, "fuzzy": 0.7}  # the model's own certainty is not available
ESTIMATED_COMPLETION_TOKENS = 150
CHARS_PER_TOKEN = 4


@dataclass
class LlmRunStats:
    vacancies: int = 0
    cache_hits: int = 0
    calls: int = 0  # requests that were answered (a retry of bad JSON counts once per request)
    failed: int = 0
    not_run: int = 0  # still to do: beyond --limit, or stopped by the cost cap
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    estimated: bool = False  # True for a dry run: the figures above are estimates


def cache_key(
    title: str, content_hash: str, *, model: str, prompt_version: str, prompt: str
) -> str:
    material = "|".join(
        [
            text_hash(title),
            content_hash,
            prompt_version,
            hashlib.sha1(prompt.encode()).hexdigest(),
            model,
        ]
    )
    return hashlib.sha1(material.encode()).hexdigest()


def _terms(raw_json: str) -> list[tuple[str, str]]:
    """(cleaned term, importance) once per term; 'required' wins over 'nice'."""
    result = ExtractionResult.model_validate(json.loads(raw_json))
    best: dict[str, str] = {}
    for skill in result.skills:
        term = clean_term(skill.name)
        if term and (term not in best or skill.importance == "required"):
            best[term] = skill.importance
    return list(best.items())


def _skill_rows(
    vacancy_id: str,
    terms: list[tuple[str, str]],
    normalizer: Normalizer,
    model: str,
    prompt_version: str,
) -> list[tuple[str, str, str, float, str, str]]:
    best: dict[str, tuple[str, float]] = {}
    for term, importance in terms:
        match = normalizer.normalize(term)
        if match.skill_id is None or match.how is None:
            continue
        confidence = CONFIDENCE[match.how]
        previous = best.get(match.skill_id)
        better = (
            previous is None
            or (previous[0] == "nice" and importance == "required")
            or (previous[0] == importance and confidence > previous[1])
        )
        if better:
            best[match.skill_id] = (importance, confidence)
    return [
        (vacancy_id, skill_id, importance, confidence, model, prompt_version)
        for skill_id, (importance, confidence) in sorted(best.items())
    ]


def refresh_unknown_skills(silver: SilverStore, normalizer: Normalizer) -> int:
    """Rebuild silver_unknown_skills from the stored terms; decisions on terms are kept."""
    statuses = silver.unknown_statuses()
    rows = []
    for term, (vacancies, first, last) in sorted(silver.term_dates().items()):
        match = normalizer.normalize(term)
        if match.skill_id is None:
            rows.append((term, vacancies, first, last, match.suggestion, statuses.get(term, "new")))
    silver.replace_unknown_skills(rows)
    return len(rows)


async def run_llm_extraction(
    silver: SilverStore,
    ops: OpsStore,
    client: LlmClient,
    normalizer: Normalizer,
    *,
    source: str | None,
    run_id: str,
    only_ids: set[str] | None = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    limit: int | None = None,
    max_cost_usd: float | None = None,
    concurrency: int = 8,
    dry_run: bool = False,
    raw_dir: Path | None = None,
) -> LlmRunStats:
    prompt = load_prompt(prompt_version)
    inputs = silver.llm_inputs(source)
    if only_ids is not None:  # e.g. the vacancies of the gold sheet: nothing else is asked
        inputs = [row for row in inputs if row[0] in only_ids]
    keys = {
        vid: cache_key(
            title, chash, model=client.model, prompt_version=prompt_version, prompt=prompt
        )
        for vid, title, _, chash in inputs
    }
    cached = silver.cache_get_many(sorted(set(keys.values())))
    stats = LlmRunStats(vacancies=len(inputs))
    stats.cache_hits = sum(keys[vid] in cached for vid, *_ in inputs)

    # Identical title + description share a key, so they are asked once.
    wanted: dict[str, tuple[str, str]] = {}
    content_hashes: dict[str, str] = {}
    for vid, title, description, chash in inputs:
        if keys[vid] not in cached and keys[vid] not in wanted:
            wanted[keys[vid]] = (title, description)
            content_hashes[keys[vid]] = chash
    todo = list(wanted.items())
    if limit is not None:
        stats.not_run += max(0, len(todo) - limit)
        todo = todo[:limit]

    if dry_run:
        stats.estimated = True
        stats.calls = len(todo)
        stats.prompt_tokens = sum(
            (len(prompt) + len(user_message(t, d))) // CHARS_PER_TOKEN for _, (t, d) in todo
        )
        stats.completion_tokens = ESTIMATED_COMPLETION_TOKENS * len(todo)
        stats.cost_usd = estimate_cost(
            client.model, Usage(stats.prompt_tokens, stats.completion_tokens)
        )
        return stats

    semaphore = asyncio.Semaphore(concurrency)

    async def ask(key: str, title: str, description: str) -> tuple[str, str | None, Usage]:
        async with semaphore:
            try:
                extraction = await extract(client, title, description, prompt=prompt)
            except LlmError as exc:
                logger.warning("{}: {}", key[:10], exc)
                return key, None, Usage()
            return key, extraction.raw, extraction.usage

    new_answers: dict[str, str] = {}
    for start in range(0, len(todo), BATCH_SIZE):
        if max_cost_usd is not None and stats.cost_usd >= max_cost_usd:
            stats.not_run += len(todo) - start
            logger.warning(
                "cost cap ${} reached; {} vacancies left for later", max_cost_usd, stats.not_run
            )
            break
        batch = todo[start : start + BATCH_SIZE]
        for key, raw, usage in await asyncio.gather(*(ask(k, t, d) for k, (t, d) in batch)):
            stats.prompt_tokens += usage.prompt_tokens
            stats.completion_tokens += usage.completion_tokens
            cost = estimate_cost(client.model, usage)
            stats.cost_usd += cost
            if raw is None:
                stats.failed += 1
                continue
            stats.calls += 1
            new_answers[key] = raw
            silver.cache_put(
                key,
                content_hash=content_hashes[key],
                model=client.model,
                prompt_version=prompt_version,
                raw_json=raw,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_usd=cost,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            _append_raw(raw_dir, key, client.model, prompt_version, usage, raw)

    answers = {**cached, **new_answers}
    ids, term_rows, skill_rows = [], [], []
    for vid, _, _, _ in inputs:
        raw_json = answers.get(keys[vid])
        if raw_json is None:
            continue  # failed or not run: whatever was stored for it stays
        terms = _terms(raw_json)
        ids.append(vid)
        term_rows += [(vid, t, i, client.model, prompt_version) for t, i in terms]
        skill_rows += _skill_rows(vid, terms, normalizer, client.model, prompt_version)
    silver.replace_llm_results(
        ids, term_rows, skill_rows, run_id=run_id, loaded_at=datetime.now(UTC).replace(tzinfo=None)
    )
    refresh_unknown_skills(silver, normalizer)
    ops.add_llm_usage(
        run_id,
        client.model,
        prompt_version,
        vacancies=stats.vacancies,
        calls=stats.calls,
        cache_hits=stats.cache_hits,
        failed=stats.failed,
        prompt_tokens=stats.prompt_tokens,
        completion_tokens=stats.completion_tokens,
        cost_usd=stats.cost_usd,
    )
    return stats


def _append_raw(
    raw_dir: Path | None, key: str, model: str, prompt_version: str, usage: Usage, raw: str
) -> None:
    """Keep each fresh answer as a JSON line, like bronze keeps pages (the cache can be rebuilt)."""
    if raw_dir is None:
        return
    day = datetime.now(UTC).date().isoformat()
    path = raw_dir / f"dt={day}" / "calls.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "key": key,
        "model": model,
        "prompt_version": prompt_version,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "answer": raw,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def renormalize_llm_skills(silver: SilverStore, normalizer: Normalizer, *, run_id: str) -> int:
    """Map the stored LLM terms onto the *current* taxonomy again, without asking the model.

    Returns the number of vacancies whose skills were rewritten.
    """
    by_vacancy: dict[str, list[tuple[str, str, str, str, str]]] = {}
    for row in silver.llm_terms():
        by_vacancy.setdefault(row[0], []).append(row)
    ids = sorted(by_vacancy)
    term_rows = [row for vid in ids for row in by_vacancy[vid]]
    skill_rows = []
    for vid in ids:
        rows = by_vacancy[vid]
        skill_rows += _skill_rows(
            vid, [(r[1], r[2]) for r in rows], normalizer, rows[0][3], rows[0][4]
        )
    silver.replace_llm_results(
        ids, term_rows, skill_rows, run_id=run_id, loaded_at=datetime.now(UTC).replace(tzinfo=None)
    )
    refresh_unknown_skills(silver, normalizer)
    return len(ids)
