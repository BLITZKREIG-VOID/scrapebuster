"""Tests for canary definition hashing and manifest serialization using tmp_path."""

import hashlib
import json
from pathlib import Path

from sb.canary.hashing import canary_hash, normalize_for_match

from ._defs import load_canaries


def test_definitions_manifest_contract(tmp_path: Path):
    """Verify that current canary definitions can be bound into a frozen manifest dynamically."""
    definitions = load_canaries()
    assert len(definitions) > 0

    anchors = [normalize_for_match(c["anchor"]) for c in definitions]
    assert len(set(anchors)) == len(anchors), "Canary anchors must be unique"

    canonical = json.dumps(definitions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    definitions_sha256 = hashlib.sha256(canonical.encode()).hexdigest()

    canaries_payload = [
        {
            "canary_id": c["canary_id"],
            "content_version": c.get("content_version", "v2"),
            "sha256": canary_hash(c),
            "anchor": c["anchor"],
            "expected_exposure_locations": c.get("placements", []),
        }
        for c in definitions
    ]

    manifest = {
        "content_version": "v2",
        "frozen": True,
        "canaries": canaries_payload,
        "definitions_sha256": definitions_sha256,
    }

    manifest_file = tmp_path / "canary_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert loaded["frozen"] is True
    assert loaded["content_version"] == "v2"
    assert loaded["definitions_sha256"] == definitions_sha256
    assert [c["canary_id"] for c in loaded["canaries"]] == [c["canary_id"] for c in definitions]

    for definition, entry in zip(definitions, loaded["canaries"], strict=True):
        assert entry["sha256"] == canary_hash(definition)
        assert entry["anchor"] == definition["anchor"]
        assert entry["content_version"] == definition.get("content_version", "v2") == "v2"
        for other in definitions:
            if other["canary_id"] != definition["canary_id"]:
                assert normalize_for_match(definition["anchor"]) not in normalize_for_match(other["content"])
