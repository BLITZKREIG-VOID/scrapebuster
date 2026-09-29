"""T-CA-2: no canary anchor appears in the CampusCart control dataset or the baseline corpus.

The origin is CampusCart (plan Part I, C1): its rendered content is captured, without the edge,
in ``data/control/control_clean.jsonl`` by ``scripts/build_control_dataset.py``.
"""

import json

from sb.canary.hashing import normalize_for_match

from ._defs import REPO_ROOT, load_canaries

ANCHORS = [normalize_for_match(c["anchor"]) for c in load_canaries()]
CAMPUSCART_ORIGIN = "https://campuscart-c73de.web.app/"
CONTROL = REPO_ROOT / "data" / "control" / "control_clean.jsonl"
BASELINE = REPO_ROOT / "data" / "baseline" / "public_baseline.jsonl"
SAMPLE = REPO_ROOT / "contracts" / "fixtures" / "scraped_dataset_sample.jsonl"


def _leaked(text: str) -> list[str]:
    norm = normalize_for_match(text)
    return [a for a in ANCHORS if a in norm]


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_no_anchor_in_campuscart_control_dataset():
    records = _jsonl(CONTROL)
    assert len(records) >= 10
    for rec in records:
        assert set(rec) == {"url", "fetched_at", "title", "text"}
        assert rec["url"].startswith(CAMPUSCART_ORIGIN), rec["url"]  # origin, never the edge
        assert "Campus" in rec["text"], rec["url"]  # rendered SPA content, not an empty shell
        assert not _leaked(rec["title"] + "\n" + rec["text"]), rec["url"]


def test_no_anchor_in_baseline():
    records = _jsonl(BASELINE)
    assert len(records) >= 25
    for rec in records:
        assert not _leaked(rec["title"] + "\n" + rec["text"]), rec["url"]


def test_sample_dataset_shape_and_canary_placement():
    """Sample fixture: 8 pages; exactly the 5 placement pages carry their canary paragraph."""
    records = _jsonl(SAMPLE)
    assert len(records) == 8
    for rec in records:
        assert set(rec) == {"url", "fetched_at", "title", "text"}
    by_path = {"/" + rec["url"].split("/", 3)[3]: rec["text"] for rec in records}
    for canary in load_canaries():
        pages = [p for p in canary["placements"] if p.startswith("/")]
        for page in pages:
            assert canary["content"] in by_path[page].split("\n\n"), (canary["canary_id"], page)
        others = [p for p in by_path if p not in pages]
        for page in others:
            assert normalize_for_match(canary["anchor"]) not in normalize_for_match(by_path[page])
