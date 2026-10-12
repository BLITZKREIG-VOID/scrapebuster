"""Unit tests for response transformation, canary injection, and decoy handling."""

import html
import json
from types import SimpleNamespace

import pytest
from sb.canary import hashing, registry
from sb.offense.decoys import decoy_index_html
from sb.offense.honeypots import get_configured_trap_api_path, get_hidden_link_html
from sb.offense.injector import (
    _note_exposure,
    handle_decoy,
    inject_json_canary,
    insert_canary,
    insert_hidden_link,
    transform_response,
    inject_jsonld_watermark,
    inject_beacon,
    inject_honeykey,
    inject_synthetic_json_canary,
    apply_watermark_matrix,
    get_watermark_matrix_info,
    select_placement_strategy,
    watermark_fallback_core,
)
from sb.store import db


def test_insert_hidden_link(monkeypatch):
    monkeypatch.setenv("SB_TRAP_PATHS", '["/trap/decoy"]')
    hidden_link = get_hidden_link_html()
    if not hidden_link:
        return

    html_input = '<body class="x"><p>Hello world</p></body>'
    result = insert_hidden_link(html_input)

    assert result.startswith('<body class="x">' + hidden_link)
    assert result.count(hidden_link) == 1

    # Idempotent: inserting again does not add a second link
    second = insert_hidden_link(result)
    assert second == result
    assert second.count(hidden_link) == 1

    # Without <body> tag, returned unchanged
    no_body = "<p>No body</p>"
    assert insert_hidden_link(no_body) == no_body


def test_insert_canary_before_last_main():
    html_input = '<main id="content"><p>Doc</p></main>'
    block = "Secret canary text"
    result = insert_canary(html_input, block, canary_id="CAN-1")
    assert '<main id="content"><p>Doc</p><p class="sb-canary"' in result
    assert html.escape(block) in result

    # No main tag: falls back to before </body> or appends
    with_body = "<body><div>No main</div></body>"
    res_body = insert_canary(with_body, block)
    assert '<p class="sb-canary">' in res_body
    assert "</body>" in res_body


def test_inject_json_canary():
    data = {"items": [1, 2, 3], "status": "ok"}
    mutated = inject_json_canary(data, "SB-CAN-01", "TOKEN-VAL")

    assert "_sb_canary" in mutated
    assert mutated["_sb_canary"]["canary_id"] == "SB-CAN-01"
    assert mutated["_sb_canary"]["token"] == "TOKEN-VAL"
    assert mutated["items"] == [1, 2, 3]


def test_transform_response_html_mutation():
    ctx = SimpleNamespace(
        path="/docs/guide",
        method="GET",
        headers={},
        session_id="sess-test-1",
    )
    session = SimpleNamespace(
        session_id="sess-test-1",
        state="SANDBOX",
        canaries_exposed=[],
    )
    upstream = SimpleNamespace(
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8"},
        content=b"<html><body><main id=\"content\"><p>Guide Content</p></main></body></html>",
    )

    body = transform_response(ctx, session, upstream)
    text = body.decode("utf-8")

    assert "Guide Content" in text
    assert "sb-canary" in text


def test_transform_response_preserves_binary():
    ctx = SimpleNamespace(path="/image.png", method="GET")
    session = SimpleNamespace(session_id="sess-1", canaries_exposed=[])
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    upstream = SimpleNamespace(
        status_code=200,
        headers={"content-type": "image/png"},
        content=png_bytes,
    )

    body = transform_response(ctx, session, upstream)
    assert body == png_bytes


def test_transform_response_preserves_head():
    ctx = SimpleNamespace(path="/docs/page", method="HEAD")
    session = SimpleNamespace(session_id="sess-1", canaries_exposed=[])
    upstream = SimpleNamespace(
        status_code=200,
        headers={"content-type": "text/html"},
        content=b"",
    )

    body = transform_response(ctx, session, upstream)
    assert body == b""


def test_transform_response_preserves_204():
    ctx = SimpleNamespace(path="/api/action", method="POST")
    session = SimpleNamespace(session_id="sess-1", canaries_exposed=[])
    upstream = SimpleNamespace(
        status_code=204,
        headers={"content-type": "text/html"},
        content=b"",
    )

    body = transform_response(ctx, session, upstream)
    assert body == b""


# Phase 3: Watermark Matrix Tests


def test_inject_jsonld_watermark():
    html_input = '<html><head></head><body><p>Test</p></body></html>'
    result = inject_jsonld_watermark(html_input, "SB-CANARY-abc123-0001", "TOKEN-VAL", "sess-001")
    
    assert 'application/ld+json' in result
    assert '"canary_id":"SB-CANARY-abc123-0001"' in result
    assert '"watermark_token":"TOKEN-VAL"' in result
    assert '"session_id":"sess-001"' in result
    assert '"@context":"https://schema.org"' in result
    assert '"@type":"WebPage"' in result
    
    # Idempotent: second injection doesn't duplicate
    result2 = inject_jsonld_watermark(result, "SB-CANARY-abc123-0001", "TOKEN-VAL", "sess-001")
    assert result2 == result


def test_inject_beacon():
    html_input = '<html><body><p>Test</p></body></html>'
    result = inject_beacon(html_input, "SB-CANARY-beacon-0001", "BEACON-TOKEN", "https://example.com")
    
    assert 'beacon.gif' in result
    assert 'SB-CANARY-beacon-0001' in result
    assert 'BEACON-TOKEN' in result
    assert 'width="1"' in result and 'height="1"' in result
    
    # Idempotent
    result2 = inject_beacon(result, "SB-CANARY-beacon-0001", "BEACON-TOKEN", "https://example.com")
    assert result2 == result
    
    # Without public_base_url
    result3 = inject_beacon(html_input, "SB-CANARY-bc-0002", "TOKEN2")
    assert 'beacon.gif' in result3


def test_inject_honeykey():
    html_input = '<html><head></head><body><p>Test</p></body></html>'
    result = inject_honeykey(html_input, "SB-CANARY-hk-0001", "HONEY-TOKEN")
    
    assert 'HoneyKey' in result
    assert 'SB-CANARY-hk-0001' in result
    assert 'HONEY-TOKEN' in result
    assert '<!--' in result
    
    # Idempotent
    result2 = inject_honeykey(result, "SB-CANARY-hk-0001", "HONEY-TOKEN")
    assert result2 == result


def test_inject_synthetic_json_canary():
    data = {"items": [1, 2, 3], "status": "ok"}
    result = inject_synthetic_json_canary(data, "SB-CANARY-sj-0001", "SYNTHETIC-TOKEN")
    
    assert "_sb_watermark" in result
    assert result["_sb_watermark"]["canary_id"] == "SB-CANARY-sj-0001"
    assert result["_sb_watermark"]["token"] == "SYNTHETIC-TOKEN"
    assert result["_sb_watermark"]["type"] == "synthetic_json_watermark"
    assert "injected_at" in result["_sb_watermark"]
    assert result["items"] == [1, 2, 3]
    
    # List input
    list_data = [{"a": 1}, {"b": 2}]
    result_list = inject_synthetic_json_canary(list_data, "SB-CAN-0002", "TOKEN2")
    assert result_list[0]["_sb_watermark"]["canary_id"] == "SB-CAN-0002"
    assert result_list[1]["b"] == 2  # Second element unchanged


def test_select_placement_strategy():
    from sb.offense.injector import PLACEMENT_STRATEGIES
    
    # Same session_id should produce same strategy (deterministic)
    s1 = select_placement_strategy("session-001")
    s2 = select_placement_strategy("session-001")
    assert s1 == s2
    
    # Different sessions should potentially produce different strategies
    strategies = {select_placement_strategy(f"session-{i:03d}") for i in range(100)}
    assert len(strategies) > 1  # Should distribute across strategies
    
    # All strategies should be valid
    for s in strategies:
        assert s in PLACEMENT_STRATEGIES


def test_get_watermark_matrix_info():
    info = get_watermark_matrix_info()
    
    assert "vectors" in info
    assert "placement_strategies" in info
    assert info["total_vectors"] == 6  # TEXT, API, JSONLD, BEACON, HONEYKEY, SYNTHETIC_JSON
    assert info["total_strategies"] == 9
    assert "TEXT" in info["vectors"]
    assert "JSONLD" in info["vectors"]
    assert "BEACON" in info["vectors"]
    assert "HONEYKEY" in info["vectors"]
    assert "SYNTHETIC_JSON" in info["vectors"]


def test_apply_watermark_matrix_html():
    from sb.offense.injector import apply_watermark_matrix
    
    html_content = b"<html><head></head><body><main><p>Test Content</p></main></body></html>"
    session_id = "test-session-001"
    ctx = SimpleNamespace(path="/test", public_base_url="https://example.com")
    
    mutated_bytes, applied = apply_watermark_matrix(
        content_bytes=html_content,
        content_type="text/html",
        session_id=session_id,
        ctx=ctx,
    )
    
    assert len(applied) >= 4  # TEXT, JSONLD, BEACON, HONEYKEY minimum
    
    # Check all expected vectors present
    vectors = {w["vector"] for w in applied}
    assert "TEXT" in vectors
    assert "JSONLD" in vectors
    assert "BEACON" in vectors
    assert "HONEYKEY" in vectors
    
    # Check mutated content contains watermarks
    mutated_html = mutated_bytes.decode("utf-8")
    assert "Security Verification Token" in mutated_html or "sb-canary" in mutated_html
    assert 'application/ld+json' in mutated_html
    assert 'beacon.gif' in mutated_html
    assert 'HoneyKey' in mutated_html
    
    # Each watermark should have unique canary_id
    canary_ids = {w["canary_id"] for w in applied}
    assert len(canary_ids) == len(applied)  # All unique


def test_apply_watermark_matrix_json():
    from sb.offense.injector import apply_watermark_matrix
    
    json_content = b'{"items": [1, 2, 3], "status": "ok"}'
    session_id = "test-session-json"
    ctx = SimpleNamespace()
    
    mutated_bytes, applied = apply_watermark_matrix(
        content_bytes=json_content,
        content_type="application/json",
        session_id=session_id,
        ctx=ctx,
    )
    
    assert len(applied) >= 2  # API + SYNTHETIC_JSON minimum
    
    vectors = {w["vector"] for w in applied}
    assert "API" in vectors
    assert "SYNTHETIC_JSON" in vectors
    
    # Check mutated content
    mutated_json = json.loads(mutated_bytes.decode("utf-8"))
    assert "_sb_canary" in mutated_json  # API canary
    assert "_sb_watermark" in mutated_json  # Synthetic JSON watermark


def test_apply_watermark_matrix_non_eligible():
    from sb.offense.injector import apply_watermark_matrix
    
    # Binary content should pass through unchanged
    binary_content = b"\x89PNG\r\n\x1a\n"
    session_id = "test-session-binary"
    
    mutated_bytes, applied = apply_watermark_matrix(
        content_bytes=binary_content,
        content_type="image/png",
        session_id=session_id,
    )
    
    assert mutated_bytes == binary_content
    assert applied == []


def test_watermark_fallback_core():
    from sb.offense.injector import watermark_fallback_core
    
    ctx = SimpleNamespace(path="/test", public_base_url="https://example.com")
    session = SimpleNamespace(session_id="test-fallback-001", canaries_exposed=[])
    upstream = SimpleNamespace(
        status_code=200,
        headers={"content-type": "text/html"},
        content=b"<html><body><main><p>Fallback Test</p></main></body></html>",
    )
    
    body, mutated = watermark_fallback_core(ctx, session, upstream)
    
    assert mutated is True
    assert len(body) > 0
    
    text = body.decode("utf-8")
    # Check for any watermark presence - could be TEXT canary, JSONLD, BEACON, or HONEYKEY
    assert "Security Verification Token" in text or "sb-canary" in text or 'application/ld+json' in text
    # At minimum should have JSONLD and BEACON and HONEYKEY
    assert 'application/ld+json' in text
    assert 'beacon.gif' in text
    assert 'HoneyKey' in text


def test_watermark_fallback_json():
    from sb.offense.injector import watermark_fallback_core
    
    ctx = SimpleNamespace(path="/api/test")
    session = SimpleNamespace(session_id="test-fallback-json", canaries_exposed=[])
    upstream = SimpleNamespace(
        status_code=200,
        headers={"content-type": "application/json"},
        content=b'{"data": "test"}',
    )
    
    body, mutated = watermark_fallback_core(ctx, session, upstream)
    
    assert mutated is True
    data = json.loads(body.decode("utf-8"))
    assert "_sb_canary" in data
    assert "_sb_watermark" in data
