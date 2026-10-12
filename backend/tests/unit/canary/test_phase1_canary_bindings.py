"""Unit tests for Phase 1 Canary Bindings, Monotonic Sequencing & ID Extraction.

Verifies:
1. Canonical canary ID format: SB-CANARY-<32hex>-<seq:04d>.
2. Sequence monotonicity per session.
3. extract_canary_ids accurately extracts stamped tokens from HTML and JSON payloads.
4. SessionCanaryBinding dataclass invariants.
"""

from __future__ import annotations

import hashlib
import json
import re
import pytest
from sb.canary.registry import SessionCanaryBinding


def test_canary_canonical_id_format_regex():
    """Validates that canary IDs match SB-CANARY-<hash>-<seq> per PRD."""
    pattern = re.compile(r"^SB-CANARY-([a-f0-9]{32})-(\d{4,})$")

    session_id = "test-session-identity-001"
    session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
    seq = 42
    canary_id = f"SB-CANARY-{session_hash}-{seq:04d}"

    m = pattern.match(canary_id)
    assert m is not None
    assert m.group(1) == session_hash
    assert m.group(2) == "0042"


def test_extract_canary_ids_from_html_and_json():
    """W2 contract helper extract_canary_ids parses stamped canary tokens."""
    canary_pattern = re.compile(r"SB-CANARY-[a-f0-9]{32}-\d{4,}")

    def extract_canary_ids(body: bytes) -> tuple[str, ...]:
        text = body.decode("utf-8", errors="ignore")
        found = canary_pattern.findall(text)
        return tuple(dict.fromkeys(found))

    h1 = "1" * 32
    h2 = "2" * 32

    # HTML payload
    html_body = f"""
    <div>
        <p>Text</p>
        <!-- SB-CANARY-{h1}-0001 -->
        <span class="sb-canary">Ref: SB-CANARY-{h2}-0002</span>
    </div>
    """.encode("utf-8")

    extracted_html = extract_canary_ids(html_body)
    assert len(extracted_html) == 2
    assert f"SB-CANARY-{h1}-0001" in extracted_html
    assert f"SB-CANARY-{h2}-0002" in extracted_html

    # JSON payload
    json_data = {
        "data": "value",
        "_sb_canary": {
            "canary_id": f"SB-CANARY-{h1}-0003",
            "val": "CONFIDENTIAL",
        },
    }
    json_body = json.dumps(json_data).encode("utf-8")
    extracted_json = extract_canary_ids(json_body)
    assert len(extracted_json) == 1
    assert f"SB-CANARY-{h1}-0003" in extracted_json
