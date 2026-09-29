"""Unit tests for response transformation, canary injection, and decoy handling."""

import html
import json
from contextlib import closing
from types import SimpleNamespace

from sb.canary import hashing, registry
from sb.store import db
from sb.trap.decoys import decoy_index_html
from sb.trap.honeypots import DECOY_API_PATH, HIDDEN_LINK_HTML
from sb.trap.injector import (
    _note_exposure,
    handle_decoy,
    insert_canary,
    insert_hidden_link,
    transform_response,
)

CANARY_TEST_CASES = [
    ("SB-CAN-0001", "/docs/team", "Oriel Vantrask"),
    ("SB-CAN-0002", "/docs/architecture", "Hexaquorum"),
    ("SB-CAN-0003", "/docs/api", "quasar-reconcile"),
    ("SB-CAN-0004", "/docs/operations", "velvet-anchor"),
    ("SB-CAN-0005", "/docs/metrics", "ORCHID-7"),
]


def test_insert_hidden_link():
    html_input = '<body class="x"><p>Hello world</p></body>'
    result = insert_hidden_link(html_input)

    assert result.startswith('<body class="x">' + HIDDEN_LINK_HTML)
    assert result.count(HIDDEN_LINK_HTML) == 1

    # Idempotent: inserting again does not add a second link
    second = insert_hidden_link(result)
    assert second == result
    assert second.count(HIDDEN_LINK_HTML) == 1

    # Without <body> tag, returned unchanged
    no_body = "<p>No body</p>"
    assert insert_hidden_link(no_body) == no_body


def test_insert_canary_before_last_main():
    html_input = '<main id="content"><p>Doc</p></main>'
    block = "Secret canary text"
    result = insert_canary(html_input, block)
    expected = f'<main id="content"><p>Doc</p><p>{html.escape(block)}</p></main>'
    assert result == expected

    # Multiple main tags: inserts before the LAST main
    multi_main = "<main><p>First</p></main><main><p>Second</p></main>"
    result_multi = insert_canary(multi_main, block)
    assert result_multi == f"<main><p>First</p></main><main><p>Second</p><p>{html.escape(block)}</p></main>"

    # No main tag: returns unchanged
    assert insert_canary("<div>No main</div>", block) == "<div>No main</div>"


def test_new_verified_session_no_canary_and_no_exposure():
    for state in ("NEW", "VERIFIED"):
        ctx = SimpleNamespace(
            path="/docs/architecture",
            ip="127.0.0.1",
            user_agent="browser-user",
            method="GET",
            headers={"accept-language": "en-US"},
        )
        session = SimpleNamespace(
            session_id=f"sess-{state}",
            state=state,
            client_key="ck-1",
            classification="HUMAN",
        )
        upstream = SimpleNamespace(
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><head><title>T</title></head><body><main id=\"content\"><p>Architecture</p></main></body></html>",
        )

        body = transform_response(ctx, session, upstream)
        text = body.decode("utf-8")

        assert HIDDEN_LINK_HTML in text
        assert "Hexaquorum" not in text

        # No exposures recorded for non-TRAPPED sessions
        assert len(registry.list_exposures()) == 0


def test_trapped_session_all_five_placements():
    for canary_id, path, anchor in CANARY_TEST_CASES:
        canary = registry.get(canary_id)
        assert canary is not None
        assert canary.status == "ACTIVE"

        session = SimpleNamespace(
            session_id=f"sess-trapped-{canary_id}",
            state="TRAPPED",
            client_key=f"ck-{canary_id}",
            classification="BOT",
        )
        ctx = SimpleNamespace(
            path=path,
            ip="127.0.0.1",
            user_agent="crawler-bot",
            method="GET",
            headers={"referer": "http://example.com/docs/"},
        )
        upstream = SimpleNamespace(
            headers={"content-type": "text/html"},
            content=f"<html><head><title>{canary_id}</title></head><body><main id=\"content\"><p>Doc for {path}</p></main></body></html>".encode(),
        )

        body = transform_response(ctx, session, upstream)
        text = body.decode("utf-8")

        # Canary block inserted before </main>
        expected_p = f"<p>{html.escape(canary.canonical_content)}</p></main>"
        assert expected_p in text
        assert anchor in text
        assert HIDDEN_LINK_HTML in text

        # Exactly one exposure row recorded
        exposures = registry.list_exposures(canary_id)
        assert len(exposures) == 1
        exp = exposures[0]
        assert exp.content_sha256 == hashing.block_hash(canary.canonical_content)
        assert exp.session_id == f"sess-trapped-{canary_id}"
        assert exp.resource == path

        # Canary status transitions to EXPOSED
        updated_canary = registry.get(canary_id)
        assert updated_canary.status == "EXPOSED"


def test_trapped_session_non_placement():
    ctx = SimpleNamespace(
        path="/docs/",
        ip="127.0.0.1",
        user_agent="crawler-bot",
        method="GET",
        headers={},
    )
    session = SimpleNamespace(
        session_id="sess-non-placement",
        state="TRAPPED",
        client_key="ck-np",
        classification="BOT",
    )
    upstream = SimpleNamespace(
        headers={"content-type": "text/html"},
        content=b"<html><head><title>Index</title></head><body><main id=\"content\"><p>Docs Home</p></main></body></html>",
    )

    body = transform_response(ctx, session, upstream)
    text = body.decode("utf-8")

    assert HIDDEN_LINK_HTML in text
    for _, _, anchor in CANARY_TEST_CASES:
        assert anchor not in text

    assert len(registry.list_exposures()) == 0


def test_non_html_response_unchanged():
    ctx = SimpleNamespace(path="/docs/architecture")
    session = SimpleNamespace(session_id="sess-json", state="TRAPPED")
    upstream = SimpleNamespace(
        headers={"content-type": "application/json"},
        content=b'{"doc": "architecture", "status": "ok"}',
    )

    result = transform_response(ctx, session, upstream)
    assert result == b'{"doc": "architecture", "status": "ok"}'
    assert len(registry.list_exposures()) == 0


def test_handle_decoy_api():
    # TRAPPED session -> returns JSON and records exposure for SB-CAN-0003
    session_trapped = SimpleNamespace(
        session_id="sess-decoy-api-t",
        state="TRAPPED",
        client_key="ck-decoy",
        classification="BOT",
    )
    ctx = SimpleNamespace(
        path=DECOY_API_PATH,
        ip="127.0.0.1",
        user_agent="bot",
        method="GET",
        headers={},
    )

    resp = handle_decoy(ctx, session_trapped)
    assert resp is not None
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"

    data = json.loads(resp.body)
    canary = registry.get("SB-CAN-0003")
    assert data["service"] == "nimbus-reconcile"
    assert data["version"] == "v3"
    assert data["status"] == "deprecated"
    assert data["notes"] == canary.canonical_content

    exps = registry.list_exposures("SB-CAN-0003")
    assert len(exps) == 1
    assert exps[0].session_id == "sess-decoy-api-t"
    assert exps[0].resource == DECOY_API_PATH

    # NEW session -> returns JSON, but records ZERO new exposures
    session_new = SimpleNamespace(
        session_id="sess-decoy-api-new",
        state="NEW",
        client_key="ck-new",
        classification="UNKNOWN",
    )
    resp_new = handle_decoy(ctx, session_new)
    assert resp_new is not None
    assert resp_new.status_code == 200
    exps_after = registry.list_exposures("SB-CAN-0003")
    assert len(exps_after) == 1


def _exposures(session_id: str) -> list:
    with closing(db.get_connection()) as conn:
        return conn.execute(
            "SELECT canary_id, resource FROM exposures WHERE session_id = ? ORDER BY rowid", (session_id,)
        ).fetchall()


def test_handle_decoy_html_pages_and_anchors():
    session = SimpleNamespace(session_id="sess-decoy-html", state="TRAPPED")
    anchors = [anchor for _, _, anchor in CANARY_TEST_CASES]
    robots_area = ["/internal/", "/internal", "/internal/deep/path"]
    hidden_index = ["/docs/archive/legacy-index", "/docs/archive/legacy-index/"]

    for p in robots_area + hidden_index:
        before = len(_exposures(session.session_id))
        ctx = SimpleNamespace(path=p)
        resp = handle_decoy(ctx, session)
        assert resp is not None, f"Expected decoy response for {p}"
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

        body_text = resp.body.decode("utf-8")
        assert HIDDEN_LINK_HTML in body_text

        # Must contain links to all 5 docs pages
        for doc_path in ("/docs/architecture", "/docs/api", "/docs/team", "/docs/operations", "/docs/metrics"):
            assert f'href="{doc_path}"' in body_text

        # OD-4: the TRAP-ROBOTS-01 area delivers every canary to a trapped session (one exposure
        # each); the hidden legacy index never carries canaries.
        for anchor in anchors:
            present = anchor.lower() in body_text.lower()
            assert present == (p in robots_area), f"anchor '{anchor}' on {p}: present={present}"
        new_rows = _exposures(session.session_id)[before:]
        if p in robots_area:
            assert sorted(r["canary_id"] for r in new_rows) == [cid for cid, _, _ in CANARY_TEST_CASES]
            assert {r["resource"] for r in new_rows} == {p}
        else:
            assert new_rows == []

    # Non-decoy path returns None
    assert handle_decoy(SimpleNamespace(path="/docs/api"), session) is None


def test_robots_decoy_withholds_canaries_from_untrapped_session():
    session = SimpleNamespace(session_id="sess-decoy-untrapped", state="VERIFIED")
    resp = handle_decoy(SimpleNamespace(path="/internal/"), session)
    body_text = resp.body.decode("utf-8").lower()
    for _, _, anchor in CANARY_TEST_CASES:
        assert anchor.lower() not in body_text
    assert _exposures(session.session_id) == []


def test_decoy_index_html_no_canary_anchors():
    content = decoy_index_html()
    for _, _, anchor in CANARY_TEST_CASES:
        assert anchor.lower() not in content.lower()


def test_note_exposure_in_memory_and_db():
    session_id = "sess-note-test"
    # Create DB row in sessions
    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, client_key, state, canaries_exposed)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, "ck-test", "TRAPPED", json.dumps(["SB-CAN-0001"])),
        )

    session_obj = SimpleNamespace(
        session_id=session_id,
        canaries_exposed=["SB-CAN-0001"],
    )

    _note_exposure(session_obj, "SB-CAN-0002")

    # In-memory updated
    assert session_obj.canaries_exposed == ["SB-CAN-0001", "SB-CAN-0002"]

    # DB updated
    with closing(db.get_connection()) as conn, conn:
        row = conn.execute("SELECT canaries_exposed FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        assert row is not None
        saved = json.loads(row["canaries_exposed"])
        assert saved == ["SB-CAN-0001", "SB-CAN-0002"]

    # Calling again is idempotent (no duplicates)
    _note_exposure(session_obj, "SB-CAN-0002")
    assert session_obj.canaries_exposed == ["SB-CAN-0001", "SB-CAN-0002"]
