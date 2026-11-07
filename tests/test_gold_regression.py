"""Guards the dictionary method against getting worse once a gold set exists.

It runs only where the labelled texts are present (they are kept local, see .gitignore) and the gold
file sets `regression_min_f1`. Both are decided after the first evaluation, so until then it skips.
"""

import pytest
import yaml

from jobmarket.gold import GOLD_FILE, TEXTS_FILE, load_gold, score
from jobmarket.skills.dictionary import DictionaryExtractor
from jobmarket.skills.taxonomy import load_taxonomy


def test_the_dictionary_method_keeps_its_f1_on_the_gold_set() -> None:
    if not (GOLD_FILE.exists() and TEXTS_FILE.exists()):
        pytest.skip("no gold set with texts here: label with `make gold`, see README")
    threshold = yaml.safe_load(GOLD_FILE.read_text(encoding="utf-8")).get("regression_min_f1")
    if threshold is None:
        pytest.skip("set `regression_min_f1` in the gold file after the first `gold-eval`")

    gold = {vid: set(entry["skills"]) for vid, entry in load_gold().items()}
    texts = yaml.safe_load(TEXTS_FILE.read_text(encoding="utf-8"))["vacancies"]
    extractor = DictionaryExtractor(load_taxonomy())
    predicted = {
        t["id"]: set(extractor.extract(t["title"], t["description"]))
        for t in texts
        if t["id"] in gold
    }

    metrics = score({vid: gold[vid] for vid in predicted}, predicted)

    assert metrics.f1 >= threshold, f"F1 {metrics.f1:.2f} fell below {threshold}"
