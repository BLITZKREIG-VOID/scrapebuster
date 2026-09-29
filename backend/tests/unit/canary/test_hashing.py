"""T-CA-1 (hashing part): canonical hashing is deterministic and whitespace-insensitive."""

import hashlib
import json

from sb.canary.hashing import block_hash, canary_hash, normalize, normalize_for_match

from ._defs import load_canaries

RECORD = {
    "canary_id": "SB-CAN-0002",
    "type": "technical_fact",
    "content": "Nimbus Ledger commits writes using the Hexaquorum protocol across 47 shards with a 312 ms settle window.",
    "content_version": "v1",
}


def test_canary_hash_is_deterministic():
    assert canary_hash(RECORD) == canary_hash(dict(RECORD))


def test_canary_hash_ignores_whitespace_variants():
    variant = dict(RECORD, content="  Nimbus Ledger commits writes\n using the Hexaquorum\tprotocol across 47 shards with a 312 ms settle window.  ")
    assert canary_hash(variant) == canary_hash(RECORD)


def test_canary_hash_matches_canonical_json_spec():
    expected = hashlib.sha256(
        json.dumps(RECORD, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert canary_hash(RECORD) == expected


def test_canary_hash_changes_when_content_or_version_changes():
    base = canary_hash(RECORD)
    assert canary_hash(dict(RECORD, content=RECORD["content"].replace("47", "48"))) != base
    assert canary_hash(dict(RECORD, content_version="v2")) != base


def test_canary_hash_ignores_extra_fields():
    assert canary_hash(dict(RECORD, anchor="Hexaquorum", status="ACTIVE")) == canary_hash(RECORD)


def test_normalize_nfc_collapses_whitespace_and_strips():
    decomposed = "Cafe\u0301\n\n  menu "
    assert normalize(decomposed) == "Caf\u00e9 menu"


def test_normalize_for_match_lowercases_and_strips_markup():
    assert normalize_for_match("The **Hexaquorum** `protocol`_ ") == "the hexaquorum protocol"


def test_block_hash_is_whitespace_insensitive():
    assert block_hash("<p>a  b</p>\n") == block_hash("<p>a b</p>")
    assert block_hash("a b") != block_hash("a c")


def test_all_yaml_canaries_hash_uniquely():
    hashes = {canary_hash(c) for c in load_canaries()}
    assert len(hashes) == 5
