"""Phase 7: detect accidental drift before a real scraper dataset is produced."""

import hashlib
import json

from sb.canary.hashing import canary_hash, normalize_for_match

from ._defs import REPO_ROOT, load_canaries


def test_frozen_manifest_matches_registry():
    definitions = load_canaries()
    manifest = json.loads((REPO_ROOT / "data/canary_manifest.json").read_text())
    canonical = json.dumps(definitions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert hashlib.sha256(canonical.encode()).hexdigest() == manifest["definitions_sha256"]
    assert manifest["frozen"] is True
    assert manifest["content_version"] == "v2"
    assert [c["canary_id"] for c in manifest["canaries"]] == [c["canary_id"] for c in definitions]
    anchors = [normalize_for_match(c["anchor"]) for c in definitions]
    assert len(set(anchors)) == len(anchors)
    for definition, entry in zip(definitions, manifest["canaries"], strict=True):
        assert entry["sha256"] == canary_hash(definition)
        assert entry["anchor"] == definition["anchor"]
        assert entry["content_version"] == definition["content_version"] == "v2"
        for other in definitions:
            if other["canary_id"] != definition["canary_id"]:
                assert normalize_for_match(definition["anchor"]) not in normalize_for_match(other["content"])
