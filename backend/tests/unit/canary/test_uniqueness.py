"""T-CA-2: no canary anchor appears in origin pages, the control dataset or the baseline corpus."""

import json

import pytest

from sb.canary.hashing import normalize_for_match

from ._defs import REPO_ROOT, load_canaries

ANCHORS = [normalize_for_match(c["anchor"]) for c in load_canaries()]
SITE_PAGES = REPO_ROOT / "demo_site" / "pages"
CONTROL = REPO_ROOT / "data" / "control" / "control_clean.jsonl"
BASELINE = REPO_ROOT / "data" / "baseline" / "public_baseline.jsonl"
SAMPLE = REPO_ROOT / "contracts" / "fixtures" / "scraped_dataset_sample.jsonl"


def _leaked(text: str) -> list[str]:
    norm = normalize_for_match(text)
    return [a for a in ANCHORS if a in norm]


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_no_anchor_in_demo_site_pages():
    if not SITE_PAGES.is_dir():
        pytest.skip("demo_site/pages/ does not exist yet (ATK-01, Arnav)")
    files = [p for p in SITE_PAGES.rglob("*") if p.is_file()]
    assert files, "demo_site/pages/ exists but is empty"
    for path in files:
        assert not _leaked(path.read_text(encoding="utf-8", errors="replace")), path


def test_no_anchor_in_control_dataset():
    if not CONTROL.is_file():
        pytest.skip("data/control/control_clean.jsonl not built yet (needs demo_site/pages/)")
    for rec in _jsonl(CONTROL):
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
