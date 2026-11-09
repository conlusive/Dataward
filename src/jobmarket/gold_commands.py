"""The gold-set commands: sample a label sheet, import the labels, evaluate the methods."""

from collections import Counter
from pathlib import Path

from loguru import logger

from jobmarket.gold import (
    GOLD_FILE,
    IDS_FILE,
    SHEET_FILE,
    TEXTS_FILE,
    Candidate,
    load_gold,
    load_labelled_by,
    load_wanted,
    parse_sheet,
    render_metrics,
    render_sheet,
    render_skill_ids,
    sample_candidates,
    score,
    top_errors,
    write_gold,
)
from jobmarket.silver.store import SilverStore
from jobmarket.skills.dictionary import DictionaryExtractor
from jobmarket.skills.taxonomy import load_taxonomy

METRICS_FILE = Path("docs/metrics.md")
WANTED_SHOWN = 40  # the most frequent missing skills shown on the metrics page
METHODS = ("dictionary", "llm")


def make_sheet(
    silver: SilverStore, n: int, seed: int, *, prefill: bool, force: bool, sheet: Path = SHEET_FILE
) -> int:
    if sheet.exists() and not force:
        logger.error("{} already exists and may hold labels. Use --force to replace it.", sheet)
        return 2
    taxonomy = load_taxonomy()
    candidates = sample_candidates(silver, n, seed)
    suggestions = None
    if prefill:
        extractor = DictionaryExtractor(taxonomy)
        suggestions = {c.id: sorted(extractor.extract(c.title, c.description)) for c in candidates}
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_text(render_sheet(candidates, suggestions), encoding="utf-8")
    IDS_FILE.write_text(render_skill_ids(taxonomy), encoding="utf-8")
    logger.info("wrote {} vacancies to {} (ids in {})", len(candidates), sheet, IDS_FILE)
    return 0


def import_labels(
    silver: SilverStore,
    *,
    labelled_by: str,
    sheet: Path = SHEET_FILE,
    gold_file: Path = GOLD_FILE,
    texts_file: Path = TEXTS_FILE,
) -> int:
    taxonomy = load_taxonomy()
    parsed = parse_sheet(sheet.read_text(encoding="utf-8"), set(taxonomy.skills))
    if parsed.problems:
        for problem in parsed.problems:
            logger.error(problem)
        logger.error("nothing was imported: fix the {} problem(s) above", len(parsed.problems))
        return 2
    rows = silver._con.execute(
        "SELECT id, title, company, description_text, content_hash FROM silver_vacancies "
        "WHERE id IN (SELECT unnest(?::VARCHAR[]))",
        [sorted(parsed.labels)],
    ).fetchall()
    candidates = {row[0]: Candidate(*row) for row in rows}
    missing = sorted(set(parsed.labels) - set(candidates))
    if missing:
        logger.warning(
            "{} labelled vacancies are no longer in silver and are skipped", len(missing)
        )
    if not parsed.labels:
        logger.error("no vacancy is labelled yet: nothing to import")
        return 2
    if parsed.unlabelled:
        logger.warning(
            "{} vacancies are not labelled yet and are left out (label them with `gold-label`)",
            len(parsed.unlabelled),
        )
    write_gold(
        parsed.labels,
        candidates,
        gold_file,
        texts_file,
        labelled_by=labelled_by,
        wanted=parsed.wanted,
    )
    wanted = sum(len(v) for v in parsed.wanted.values())
    logger.info(
        "imported {} vacancies; {} skills the taxonomy lacks were requested",
        len(candidates),
        wanted,
    )
    return 0


def evaluate(silver: SilverStore, *, gold_file: Path = GOLD_FILE, out: Path = METRICS_FILE) -> int:
    gold_entries = load_gold(gold_file)
    current = {
        row[0]: row[1]
        for row in silver._con.execute(
            "SELECT id, content_hash FROM silver_vacancies "
            "WHERE id IN (SELECT unnest(?::VARCHAR[]))",
            [sorted(gold_entries)],
        ).fetchall()
    }
    gold = {
        vid: set(entry["skills"])
        for vid, entry in gold_entries.items()
        if current.get(vid) == entry["content_hash"]
    }
    stale = len(gold_entries) - len(gold)
    if stale:
        logger.warning(
            "{} gold vacancies changed or vanished since labelling and are skipped", stale
        )
    if not gold:
        logger.error("no gold vacancy is usable")
        return 2

    # A method that ran on a vacancy and found nothing has no rows, yet it was asked: for the LLM
    # the cache says so, and a miss on such a vacancy must count (else it would leave the score).
    asked_llm = {
        row[0]
        for row in silver._con.execute(
            "SELECT id FROM silver_vacancies WHERE id IN (SELECT unnest(?::VARCHAR[])) "
            "AND content_hash IN (SELECT content_hash FROM llm_cache)",
            [sorted(gold)],
        ).fetchall()
    }
    rows, errors = [], {}
    for method in METHODS:
        predicted: dict[str, set[str]] = {}
        for vid, skill in silver._con.execute(
            "SELECT vacancy_id, skill_id FROM silver_vacancy_skills "
            "WHERE method = ? AND vacancy_id IN (SELECT unnest(?::VARCHAR[]))",
            [method, sorted(gold)],
        ).fetchall():
            predicted.setdefault(vid, set()).add(skill)
        if not predicted:
            logger.info("method {} has no results for the gold vacancies: skipped", method)
            continue
        evaluated = {
            vid: skills
            for vid, skills in gold.items()
            if vid in predicted or method == "dictionary" or (method == "llm" and vid in asked_llm)
        }
        rows.append((method, score(evaluated, predicted), _cost_per_10k(silver, method)))
        errors[method] = top_errors(evaluated, predicted)
    out.parent.mkdir(parents=True, exist_ok=True)
    wanted: Counter[str] = Counter()
    names: dict[str, str] = {}
    for vid, skills_wanted in load_wanted(gold_file).items():
        if vid in gold:
            for name in skills_wanted:
                wanted[name.casefold()] += 1
                names.setdefault(name.casefold(), name)
    gaps = [(names[key], count) for key, count in wanted.most_common(WANTED_SHOWN)]
    out.write_text(
        render_metrics(rows, gaps, errors, labelled_by=load_labelled_by(gold_file)),
        encoding="utf-8",
    )
    for name, metrics, _ in rows:
        logger.info(
            "{}: precision {:.2f} recall {:.2f} F1 {:.2f} on {} vacancies",
            name,
            metrics.precision,
            metrics.recall,
            metrics.f1,
            metrics.vacancies,
        )
    logger.info("written to {}", out)
    return 0


def _cost_per_10k(silver: SilverStore, method: str) -> float | None:
    if method != "llm":
        return 0.0
    row = silver._con.execute("SELECT sum(cost_usd), sum(calls) FROM ops_llm_usage").fetchone()
    if row is None or not row[1]:
        return None
    return float(row[0]) / float(row[1]) * 10_000
