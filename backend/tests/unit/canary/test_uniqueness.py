"""T-CA-2: canary anchor uniqueness, placement verification, and collision resistance."""

import json

from sb.canary.hashing import normalize_for_match

from ._defs import REPO_ROOT, load_canaries

ANCHORS = [normalize_for_match(c["anchor"]) for c in load_canaries()]
SAMPLE = REPO_ROOT / "contracts" / "fixtures" / "scraped_dataset_sample.jsonl"


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_canary_anchors_are_unique():
    """All configured canary anchors must be unique and non-overlapping."""
    canaries = load_canaries()
    anchors = [c["anchor"] for c in canaries]
    assert len(anchors) == len(set(anchors)), "Canary anchors must be distinct"
    assert len(ANCHORS) == len(set(ANCHORS)), "Normalized canary anchors must be distinct"


def test_canary_ids_are_unique():
    """All canary identifiers must be unique."""
    canaries = load_canaries()
    ids = [c["canary_id"] for c in canaries]
    assert len(ids) == len(set(ids)), "Canary IDs must be distinct"


def test_sample_dataset_shape_and_canary_placement():
    """Sample fixture: exactly the placement pages carry their canary content."""
    if not SAMPLE.is_file():
        return
    records = _jsonl(SAMPLE)
    assert len(records) >= 5
    for rec in records:
        assert set(rec) == {"url", "fetched_at", "title", "text"}
    by_path = {"/" + rec["url"].split("/", 3)[3]: rec["text"] for rec in records}
    for canary in load_canaries():
        pages = [p for p in canary["placements"] if p.startswith("/")]
        for page in pages:
            if page in by_path:
                assert canary["content"] in by_path[page].split("\n\n"), (canary["canary_id"], page)
        others = [p for p in by_path if p not in pages]
        for page in others:
            assert normalize_for_match(canary["anchor"]) not in normalize_for_match(by_path[page])
