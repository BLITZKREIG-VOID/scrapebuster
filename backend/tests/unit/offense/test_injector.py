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
