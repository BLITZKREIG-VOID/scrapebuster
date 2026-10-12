"""Response transformation, canary injection, decoy handling, and OffenseHooks for ScrapeBuster Phase 1."""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import logging
import re
import sqlite3
from collections.abc import Mapping
from typing import Any

from fastapi import Response
from fastapi.responses import HTMLResponse, JSONResponse
from sb.canary import registry
from sb.canary._defs import extract_canary_ids
from sb.contracts import Canary
from sb.offense import layer3
from sb.offense.decoys import (
    decoy_api_payload,
    decoy_index_html,
)
from sb.offense.honeypots import (
    get_configured_trap_api_path,
    get_configured_trap_paths,
    get_hidden_link_html,
)
from sb.store import db

logger = logging.getLogger(__name__)

__all__ = [
    "ScapeBustersOffenseHooks",
    "decoy_api_payload",
    "decoy_index_html",
    "deterministic_fallback",
    "deterministic_fallback_core",
    "extract_canary_ids",
    "handle_decoy",
    "inject_json_canary",
    "insert_canary",
    "insert_hidden_link",
    "placements",
    "transform_response",
]


def _append_fault_record(record: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
    """Loudly append fault record to durable ledger without silent swallow."""
    try:
        from sb.store.ledger import append_event

        append_event("fault", record, conn=conn)
    except Exception as exc:
        logger.error("Failed to append fault record to ledger: %s", exc)


def placements() -> dict[str, Canary]:
    """Map placement paths and keys to Canary models."""
    mapping: dict[str, Canary] = {}
    for canary in registry.list_canaries():
        for p in canary.placements or []:
            if isinstance(p, str) and p.startswith("/"):
                norm = p.rstrip("/") if p != "/" else "/"
                mapping[norm] = canary
            elif p == "TRAP-DECOY-01":
                mapping["TRAP-DECOY-01"] = canary
    return mapping


def insert_hidden_link(html: str) -> str:
    """Insert configured hidden honeypot link immediately after the first <body...> open tag.

    If no trap paths configured, the page already contains it, or has no <body>, return unchanged.
    """
    hidden_link = get_hidden_link_html()
    if not hidden_link or hidden_link in html:
        return html
    m = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    if not m:
        return html
    end = m.end()
    return html[:end] + hidden_link + html[end:]


def _detect_and_decode_html(content_bytes: bytes, content_type: str) -> tuple[str, str]:
    """Detect charset from content-type or meta tag and decode HTML, preserving legitimate non-ASCII characters."""
    encoding = "utf-8"
    ct_lower = content_type.lower()
    if "charset=" in ct_lower:
        try:
            encoding = ct_lower.split("charset=")[1].split(";")[0].strip().strip('"').strip("'")
        except Exception:
            encoding = "utf-8"
    else:
        sample = content_bytes[:1024].decode("ascii", errors="ignore")
        match = re.search(r'<meta[^>]+charset=["\']?([a-zA-Z0-9_\-]+)', sample, re.IGNORECASE)
        if match:
            encoding = match.group(1).lower()

    try:
        return content_bytes.decode(encoding), encoding
    except Exception:
        return content_bytes.decode("utf-8", errors="replace"), "utf-8"


def _ensure_utf8_meta(html_text: str) -> str:
    """Ensure HTML meta charset tag is coherent with UTF-8 byte encoding."""
    if re.search(r'<meta[^>]+charset=["\']?utf-8["\']?', html_text, re.IGNORECASE):
        return html_text
    return re.sub(
        r'(<meta[^>]+charset=["\']?)[a-zA-Z0-9_\-]+(["\']?)',
        r'\g<1>utf-8\g<2>',
        html_text,
        count=1,
        flags=re.IGNORECASE,
    )


def insert_canary(html: str, block_text: str, canary_id: str | None = None) -> str:
    """Insert canary markup additively before </main>, or before </body> as fallback.

    Additive-safe: returns unchanged if text already present.
    """
    if block_text in html:
        return html

    escaped_text = html_lib.escape(block_text)
    cid_attr = f' data-canary-id="{html_lib.escape(canary_id)}"' if canary_id else ""
    p_tag = f'<p class="sb-canary"{cid_attr}>{escaped_text}</p>'

    matches = list(re.finditer(r"</main\s*>", html, flags=re.IGNORECASE))
    if matches:
        last_match = matches[-1]
        start = last_match.start()
        return html[:start] + p_tag + html[start:]

    body_matches = list(re.finditer(r"</body\s*>", html, flags=re.IGNORECASE))
    if body_matches:
        last_match = body_matches[-1]
        start = last_match.start()
        return html[:start] + p_tag + html[start:]

    return html + p_tag


def inject_json_canary(data: Any, canary_id: str, canary_value: str) -> Any:
    """Inject canary token additively into parsed JSON structure."""
    canary_meta = {"canary_id": canary_id, "token": canary_value}
    if isinstance(data, dict):
        mutated = dict(data)
        mutated["_sb_canary"] = canary_meta
        return mutated
    if isinstance(data, list):
        mutated = list(data)
        if mutated and isinstance(mutated[0], dict):
            first_elem = dict(mutated[0])
            first_elem["_sb_canary"] = canary_meta
            mutated[0] = first_elem
        else:
            mutated.append({"_sb_canary": canary_meta})
        return mutated
    return data


def _note_exposure(
    session: Any,
    canary_id: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Record canary_id in session.canaries_exposed and update DB sessions row if present."""
    if (
        session is not None
        and hasattr(session, "canaries_exposed")
        and isinstance(session.canaries_exposed, list)
        and canary_id not in session.canaries_exposed
    ):
        session.canaries_exposed.append(canary_id)

    session_id = getattr(session, "session_id", None)
    if session_id is not None:
        try:
            manage_conn = conn is None
            target_conn = db.get_connection() if manage_conn else conn
            try:
                row = target_conn.execute(
                    "SELECT canaries_exposed FROM sessions WHERE session_id = ?",
                    (str(session_id),),
                ).fetchone()
                if row is not None:
                    raw = row["canaries_exposed"]
                    exposed_list = json.loads(raw) if raw else []
                    if canary_id not in exposed_list:
                        exposed_list.append(canary_id)
                        target_conn.execute(
                            "UPDATE sessions SET canaries_exposed = ? WHERE session_id = ?",
                            (json.dumps(exposed_list), str(session_id)),
                        )
                        if manage_conn:
                            target_conn.commit()
            finally:
                if manage_conn:
                    target_conn.close()
        except Exception as exc:
            logger.warning("Could not persist canary exposure to session store: %s", exc)


def deterministic_fallback_core(
    ctx: Any,
    session: Any,
    upstream: Any,
    conn: sqlite3.Connection | None = None,
) -> tuple[bytes, bool]:
    """Genuine deterministic session-bound registered HTML/JSON fallback.

    Chains actual binding/injection outcomes exactly once.
    Returns (mutated_bytes, mutated_bool).
    Preserves binary, HEAD, 204/304 semantics.
    Strictly honest: never records exposure or modifies session.canaries_exposed
    if fallback mutation encounters an error or malformed source.
    """
    # Use shared connection for all registry calls to avoid connection overhead
    # Each registry call manages its own transaction; we just reuse the connection
    manage_conn = conn is None
    if manage_conn:
        from sb.store.db import get_connection
        conn = get_connection()

    try:
        return _deterministic_fallback_core_impl(ctx, session, upstream, conn)
    finally:
        if manage_conn:
            conn.close()


def _deterministic_fallback_core_impl(
    ctx: Any,
    session: Any,
    upstream: Any,
    conn: sqlite3.Connection,
) -> tuple[bytes, bool]:
    """Implementation of deterministic fallback with shared connection."""
    if upstream is None:
        return b"", False

    status_code = getattr(upstream, "status_code", 200)
    if status_code in (204, 304):
        content = getattr(upstream, "content", b"") or b""
        return (content if isinstance(content, bytes) else bytes(content or b"")), False

    method = getattr(ctx, "method", "")
    if not method and hasattr(ctx, "request"):
        method = getattr(ctx.request, "method", "")
    if str(method).upper() == "HEAD":
        content = getattr(upstream, "content", b"") or b""
        return (content if isinstance(content, bytes) else bytes(content or b"")), False

    content_bytes = getattr(upstream, "content", b"") or b""
    if not isinstance(content_bytes, bytes):
        content_bytes = bytes(content_bytes or b"")

    if not content_bytes:
        return b"", False

    headers = getattr(upstream, "headers", {}) or {}
    content_type = ""
    if hasattr(headers, "get"):
        content_type = headers.get("content-type", "") or ""
    elif isinstance(headers, Mapping):
        for k, v in headers.items():
            if str(k).lower() == "content-type":
                content_type = str(v)
                break

    ct_lower = content_type.lower()
    is_html = "text/html" in ct_lower or "application/xhtml+xml" in ct_lower
    is_json = "application/json" in ct_lower or "+json" in ct_lower

    if not is_html and not is_json:
        # Non-eligible binary or plain content passes through untouched
        return content_bytes, False

    session_id = getattr(session, "session_id", None) or getattr(ctx, "session_id", None) or "anon"
    raw_path = getattr(ctx, "path", "") or ""

    if is_html:
        try:
            binding = registry.bind_session_canary(
                session_id=str(session_id),
                vector="TEXT",
                conn=conn,
            )
            html_text, _ = _detect_and_decode_html(content_bytes, content_type)
            html_text = insert_hidden_link(html_text)
            block_text = f"Security Verification Token: {binding.value}"
            mutated_text = insert_canary(html_text, block_text, canary_id=binding.canary_id)
            mutated_text = _ensure_utf8_meta(mutated_text)
            mutated_bytes = mutated_text.encode("utf-8")

            if not mutated_bytes or mutated_bytes == content_bytes:
                logger.warning("Deterministic HTML fallback produced identity bytes; returning unmutated")
                return content_bytes, False

            # Record exposure and injection outcome exactly once
            registry.record_exposure(
                canary_id=binding.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=block_text,
                vector="TEXT",
                outcome="success",
                conn=conn,
            )
            _note_exposure(session, binding.canary_id, conn=conn)
            registry.record_injection_outcome(
                canary_id=binding.canary_id,
                vector="TEXT",
                session_id=str(session_id),
                time=registry.now_iso(),
                outcome="success",
                resource=raw_path,
                conn=conn,
            )

            return mutated_bytes, True
        except Exception as exc:
            logger.error("HTML deterministic fallback error for %s: %s", raw_path, exc)
            _append_fault_record(
                {
                    "event_type": "html_deterministic_fallback_error",
                    "session_id": str(session_id),
                    "client_key": getattr(ctx, "client_key", ""),
                    "path": raw_path,
                    "error": str(exc),
                    "ts": registry.now_iso(),
                },
                conn=conn,
            )
            return content_bytes, False

    if is_json:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception as parse_err:
            logger.error(
                "Eligible JSON mutation failed on malformed source for %s: %s; returning unmutated bytes per total-error rule",
                raw_path,
                parse_err,
            )
            _append_fault_record(
                {
                    "event_type": "malformed_json_source",
                    "session_id": str(session_id),
                    "client_key": getattr(ctx, "client_key", ""),
                    "path": raw_path,
                    "error": str(parse_err),
                    "ts": registry.now_iso(),
                },
                conn=conn,
            )
            return content_bytes, False

        if not isinstance(data, (dict, list)):
            logger.error(
                "Eligible JSON mutation cannot mutate scalar source for %s without changing semantics; returning unmutated bytes",
                raw_path,
            )
            _append_fault_record(
                {
                    "event_type": "json_scalar_source_unmutatable",
                    "session_id": str(session_id),
                    "client_key": getattr(ctx, "client_key", ""),
                    "path": raw_path,
                    "error": "scalar JSON source cannot mutate additively",
                    "ts": registry.now_iso(),
                },
                conn=conn,
            )
            return content_bytes, False

        try:
            binding = registry.bind_session_canary(
                session_id=str(session_id),
                vector="API",
                conn=conn,
            )
            mutated_data = inject_json_canary(data, binding.canary_id, binding.value)
            mutated_bytes = json.dumps(mutated_data, ensure_ascii=False).encode("utf-8")

            if not mutated_bytes or mutated_bytes == content_bytes:
                logger.warning("Deterministic JSON fallback produced identity bytes; returning unmutated")
                return content_bytes, False

            # Record exposure and injection outcome exactly once
            registry.record_exposure(
                canary_id=binding.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=binding.value,
                vector="API",
                outcome="success",
                conn=conn,
            )
            _note_exposure(session, binding.canary_id, conn=conn)
            registry.record_injection_outcome(
                canary_id=binding.canary_id,
                vector="API",
                session_id=str(session_id),
                time=registry.now_iso(),
                outcome="success",
                resource=raw_path,
                conn=conn,
            )

            return mutated_bytes, True
        except Exception as exc:
            logger.error("JSON deterministic fallback error for %s: %s", raw_path, exc)
            _append_fault_record(
                {
                    "event_type": "json_deterministic_fallback_error",
                    "session_id": str(session_id),
                    "client_key": getattr(ctx, "client_key", ""),
                    "path": raw_path,
                    "error": str(exc),
                    "ts": registry.now_iso(),
                },
                conn=conn,
            )
            return content_bytes, False

    return content_bytes, False


def deterministic_fallback(
    ctx: Any,
    session: Any,
    upstream: Any,
    conn: sqlite3.Connection | None = None,
) -> bytes:
    """Genuine deterministic session-bound registered HTML/JSON fallback returning bytes."""
    body, _ = deterministic_fallback_core(ctx, session, upstream, conn=conn)
    return body


def transform_response(
    ctx: Any,
    session: Any,
    upstream: Any,
    conn: sqlite3.Connection | None = None,
) -> bytes:
    """Transform eligible HTML and JSON unconditionally with deterministic fallback on error.

    Maintains integrity of binary, HEAD, 204, and 304 responses.
    Strictly honest: session.canaries_exposed records only genuinely served bindings.
    """
    if upstream is None:
        return b""

    # Preserve status codes that must not carry modified body
    status_code = getattr(upstream, "status_code", 200)
    if status_code in (204, 304):
        content = getattr(upstream, "content", b"")
        return content if isinstance(content, bytes) else bytes(content or b"")

    # Preserve HEAD requests without corrupting empty/special content
    method = getattr(ctx, "method", "")
    if not method and hasattr(ctx, "request"):
        method = getattr(ctx.request, "method", "")
    if str(method).upper() == "HEAD":
        content = getattr(upstream, "content", b"")
        return content if isinstance(content, bytes) else bytes(content or b"")

    content_bytes = getattr(upstream, "content", b"") or b""
    if not isinstance(content_bytes, bytes):
        content_bytes = bytes(content_bytes or b"")

    if not content_bytes:
        return b""

    headers = getattr(upstream, "headers", {}) or {}
    content_type = ""
    if hasattr(headers, "get"):
        content_type = headers.get("content-type", "") or ""
    elif isinstance(headers, Mapping):
        for k, v in headers.items():
            if str(k).lower() == "content-type":
                content_type = str(v)
                break

    ct_lower = content_type.lower()
    is_html = "text/html" in ct_lower or "application/xhtml+xml" in ct_lower
    is_json = "application/json" in ct_lower or "+json" in ct_lower

    # Non-eligible content types pass through unmodified
    if not is_html and not is_json:
        return content_bytes

    session_id = getattr(session, "session_id", None) or getattr(ctx, "session_id", None) or "anon"
    raw_path = getattr(ctx, "path", "") or ""

    if is_html:
        try:
            html_text, _ = _detect_and_decode_html(content_bytes, content_type)
            html_text = insert_hidden_link(html_text)

            binding = registry.bind_session_canary(
                session_id=str(session_id),
                vector="TEXT",
                conn=conn,
            )
            block_text = f"Security Verification Token: {binding.value}"
            mutated_text = insert_canary(html_text, block_text, canary_id=binding.canary_id)

            # Placements check (record only after mutation succeeds)
            norm_path = raw_path.rstrip("/") if raw_path != "/" else "/"
            placements_map = placements()
            seed_canary_to_record = None
            if norm_path in placements_map:
                seed_canary = placements_map[norm_path]
                db_canary = registry.get(seed_canary.canary_id, conn=conn)
                if db_canary:
                    seed_text = registry.injected_block_text(db_canary)
                    mutated_text = insert_canary(mutated_text, seed_text, canary_id=db_canary.canary_id)
                    seed_canary_to_record = (db_canary.canary_id, seed_text)

            mutated_text = _ensure_utf8_meta(mutated_text)
            mutated_bytes = mutated_text.encode("utf-8")

            # Verify transform is not None/invalid/identity bytes
            if not mutated_bytes or mutated_bytes == content_bytes:
                logger.warning("Primary HTML transform yielded identity bytes; falling back")
                return deterministic_fallback(ctx, session, upstream, conn=conn)

            # Mutation verified! Record exposures and outcomes for served canaries
            registry.record_exposure(
                canary_id=binding.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=block_text,
                vector="TEXT",
                outcome="success",
                conn=conn,
            )
            _note_exposure(session, binding.canary_id, conn=conn)
            registry.record_injection_outcome(
                canary_id=binding.canary_id,
                vector="TEXT",
                session_id=str(session_id),
                time=registry.now_iso(),
                outcome="success",
                resource=raw_path,
                conn=conn,
            )

            if seed_canary_to_record is not None:
                seed_cid, seed_txt = seed_canary_to_record
                registry.record_exposure(
                    canary_id=seed_cid,
                    session=session,
                    ctx=ctx,
                    resource=raw_path,
                    block_text=seed_txt,
                    vector="TEXT",
                    outcome="success",
                    conn=conn,
                )
                _note_exposure(session, seed_cid, conn=conn)

            return mutated_bytes
        except Exception as exc:
            logger.warning("Primary HTML mutation error: %s; using deterministic fallback", exc)
            return deterministic_fallback(ctx, session, upstream, conn=conn)

    if is_json:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception as parse_err:
            logger.error(
                "Eligible JSON mutation failed on malformed source for %s: %s; returning unmutated bytes per total-error rule",
                raw_path,
                parse_err,
            )
            _append_fault_record(
                {
                    "event_type": "malformed_json_source",
                    "session_id": str(session_id),
                    "client_key": getattr(ctx, "client_key", ""),
                    "path": raw_path,
                    "error": str(parse_err),
                    "ts": registry.now_iso(),
                },
                conn=conn,
            )
            return content_bytes

        if not isinstance(data, (dict, list)):
            logger.error(
                "Eligible JSON mutation cannot mutate scalar source for %s without changing semantics; returning unmutated bytes",
                raw_path,
            )
            _append_fault_record(
                {
                    "event_type": "json_scalar_source_unmutatable",
                    "session_id": str(session_id),
                    "client_key": getattr(ctx, "client_key", ""),
                    "path": raw_path,
                    "error": "scalar JSON source cannot mutate additively",
                    "ts": registry.now_iso(),
                },
                conn=conn,
            )
            return content_bytes

        try:
            binding = registry.bind_session_canary(
                session_id=str(session_id),
                vector="API",
                conn=conn,
            )
            mutated_data = inject_json_canary(data, binding.canary_id, binding.value)
            mutated_bytes = json.dumps(mutated_data, ensure_ascii=False).encode("utf-8")

            if not mutated_bytes or mutated_bytes == content_bytes:
                logger.warning("Primary JSON transform yielded identity bytes; falling back")
                return deterministic_fallback(ctx, session, upstream, conn=conn)

            # Mutation verified! Record exposure and outcome
            registry.record_exposure(
                canary_id=binding.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=binding.value,
                vector="API",
                outcome="success",
                conn=conn,
            )
            _note_exposure(session, binding.canary_id, conn=conn)
            registry.record_injection_outcome(
                canary_id=binding.canary_id,
                vector="API",
                session_id=str(session_id),
                time=registry.now_iso(),
                outcome="success",
                resource=raw_path,
                conn=conn,
            )

            return mutated_bytes
        except Exception as exc:
            logger.warning("Primary JSON mutation error: %s; using deterministic fallback", exc)
            return deterministic_fallback(ctx, session, upstream, conn=conn)

    return content_bytes


# =============================================================================
# Phase 3: Watermark Matrix & RAG Mutation Engine
# =============================================================================

# Watermark vector types (Phase 3)
WATERMARK_VECTORS = {
    "TEXT": "visible linguistic canary in HTML",
    "API": "additive JSON canary in API responses",
    "JSONLD": "schema.org JSON-LD watermark",
    "BEACON": "1x1 pixel beacon with session-bound token",
    "HONEYKEY": "synthetic API key/secret embedded in content",
    "SYNTHETIC_JSON": "synthetic JSON records with canary fields",
}

# Placement strategies for randomization across sessions
PLACEMENT_STRATEGIES = {
    "html_before_main": "before </main> tag",
    "html_before_body": "before </body> tag",
    "html_after_body_open": "after <body> open tag",
    "html_in_comment": "inside HTML comment",
    "json_top_level": "top-level _sb_watermark field",
    "json_nested": "nested in first object/array element",
    "jsonld_script": "in <script type='application/ld+json'>",
    "beacon_img": "1x1 pixel <img> with token in src",
    "honeykey_in_comment": "fake API key in HTML/JS comment",
}


def generate_session_watermark_token(session_id: str, vector: str, conn=None) -> tuple[str, str]:
    """Generate a session-bound watermark token using the canary registry.
    
    Returns (canary_id, token_value).
    """
    norm_vector = registry.normalize_vector(vector)
    binding = registry.bind_session_canary(
        session_id=str(session_id),
        vector=norm_vector,
        conn=conn,
    )
    return binding.canary_id, binding.value


def inject_jsonld_watermark(
    html: str,
    canary_id: str,
    token_value: str,
    session_id: str,
    schema_type: str = "WebPage",
) -> str:
    """Inject schema.org JSON-LD watermark into HTML.
    
    Adds a <script type="application/ld+json"> block with watermark data.
    Additive-safe: returns unchanged if already present.
    """
    # Check for both spaced and compact JSON formats
    check_patterns = [
        f'"canary_id":"{canary_id}"',  # compact format
        f'"canary_id": "{canary_id}"',  # spaced format
    ]
    if any(pattern in html for pattern in check_patterns):
        return html
    
    jsonld = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "canary_id": canary_id,
        "watermark_token": token_value,
        "session_id": session_id,
        "injected_at": registry.now_iso(),
    }
    
    jsonld_text = json.dumps(jsonld, ensure_ascii=False, separators=(",", ":"))
    script_tag = f'<script type="application/ld+json">{jsonld_text}</script>'
    
    # Insert before </head> or </body>
    for tag in ["</head>", "</body>"]:
        idx = html.rfind(tag)
        if idx >= 0:
            return html[:idx] + script_tag + html[idx:]
    
    return html + script_tag


def inject_beacon(
    html: str,
    canary_id: str,
    token_value: str,
    public_base_url: str = "",
) -> str:
    """Inject 1x1 pixel beacon image with session-bound token.
    
    The beacon src includes the token for callback correlation.
    Additive-safe: returns unchanged if beacon already present.
    """
    beacon_src = f"{public_base_url}/beacon.gif?c={canary_id}&t={token_value}"
    beacon_img = f'<img src="{beacon_src}" width="1" height="1" alt="" style="display:none;" data-beacon-canary="{canary_id}">'
    
    if beacon_img in html:
        return html
    
    # Insert after <body> open tag
    m = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    if m:
        end = m.end()
        return html[:end] + beacon_img + html[end:]
    
    return html + beacon_img


def inject_honeykey(
    html: str,
    canary_id: str,
    token_value: str,
) -> str:
    """Inject synthetic honey key (fake API key/secret) in HTML/JS comment.
    
    Additive-safe: returns unchanged if honey key already present.
    """
    honeykey_comment = f"<!-- HoneyKey: {canary_id} | token={token_value} -->"
    
    if honeykey_comment in html:
        return html
    
    # Insert in a JS comment near the end of <head> or before </body>
    for tag in ["</head>", "</body>"]:
        idx = html.rfind(tag)
        if idx >= 0:
            return html[:idx] + honeykey_comment + "\n" + html[idx:]
    
    return html + "\n" + honeykey_comment


def inject_synthetic_json_canary(
    data: Any,
    canary_id: str,
    token_value: str,
    watermark_field: str = "_sb_watermark",
) -> Any:
    """Inject synthetic JSON canary with session-bound fields.
    
    Adds watermark_field with canary_id, token, and metadata.
    """
    watermark_meta = {
        "canary_id": canary_id,
        "token": token_value,
        "injected_at": registry.now_iso(),
        "type": "synthetic_json_watermark",
    }
    
    if isinstance(data, dict):
        mutated = dict(data)
        mutated[watermark_field] = watermark_meta
        return mutated
    if isinstance(data, list):
        mutated = list(data)
        if mutated and isinstance(mutated[0], dict):
            first_elem = dict(mutated[0])
            first_elem[watermark_field] = watermark_meta
            mutated[0] = first_elem
        else:
            mutated.append({watermark_field: watermark_meta})
        return mutated
    return data


def select_placement_strategy(session_id: str) -> str:
    """Select a randomized placement strategy based on session ID for consistent per-session placement.
    
    Uses session_id hash to ensure consistent but randomized placement across sessions.
    """
    strategies = list(PLACEMENT_STRATEGIES.keys())
    # Use hash of session_id for deterministic but distributed selection
    hash_val = int(hashlib.sha256(session_id.encode()).hexdigest()[:8], 16)
    return strategies[hash_val % len(strategies)]


def apply_watermark_matrix(
    content_bytes: bytes,
    content_type: str,
    session_id: str,
    ctx: Any = None,
    conn=None,
) -> tuple[bytes, list[dict]]:
    """Apply the full watermark matrix to eligible content.
    
    Returns (mutated_bytes, list_of_applied_watermarks) where each watermark dict contains:
    - canary_id, vector, value, placement_strategy, placement_location
    
    Supports: HTML (TEXT, JSONLD, BEACON, HONEYKEY) and JSON (API, SYNTHETIC_JSON)
    
    Uses session mutation cache to avoid re-computing watermarks for identical content.
    """
    # Session mutation cache: {session_id: {content_hash: (mutated_bytes, applied)}}
    # Cache is per-session to ensure session-bound canaries are not shared
    if not hasattr(apply_watermark_matrix, "_session_cache"):
        apply_watermark_matrix._session_cache = {}
    
    # Compute content hash for cache key
    import hashlib
    content_hash = hashlib.sha256(content_bytes).hexdigest()[:16]
    cache_key = (session_id, content_hash)
    
    # Check cache first
    session_cache = apply_watermark_matrix._session_cache.get(session_id, {})
    if cache_key in session_cache:
        cached_bytes, cached_applied = session_cache[cache_key]
        # Return cached result (fresh copy)
        return bytes(cached_bytes), list(cached_applied)
    
    applied = []
    
    if not content_bytes:
        return content_bytes, applied
    
    ct_lower = content_type.lower()
    is_html = "text/html" in ct_lower or "application/xhtml+xml" in ct_lower
    is_json = "application/json" in ct_lower or "+json" in ct_lower
    
    if not is_html and not is_json:
        return content_bytes, applied
    
    # HTML content
    if is_html:
        html_text, encoding = _detect_and_decode_html(content_bytes, content_type)
        
        # Get public base URL for beacon
        public_base_url = ""
        if ctx and hasattr(ctx, "public_base_url"):
            public_base_url = ctx.public_base_url
        elif ctx and hasattr(ctx, "request"):
            from sb.config import get_public_base_url
            try:
                public_base_url = get_public_base_url()
            except Exception:
                pass
        
        # Apply TEXT canary (primary linguistic watermark)
        canary_id, token = generate_session_watermark_token(session_id, "TEXT", conn)
        strategy = select_placement_strategy(session_id + "_text")
        
        if strategy == "html_before_main":
            block_text = f"Security Verification Token: {token}"
            html_text = insert_canary(html_text, block_text, canary_id=canary_id)
            applied.append({"canary_id": canary_id, "vector": "TEXT", "value": token, "strategy": strategy})
        elif strategy == "html_before_body":
            block_text = f"Security Verification Token: {token}"
            html_text = insert_canary(html_text, block_text, canary_id=canary_id)
            applied.append({"canary_id": canary_id, "vector": "TEXT", "value": token, "strategy": strategy})
        elif strategy == "html_in_comment":
            comment_text = f"<!-- Watermark: {canary_id} | {token} -->"
            # Insert before </body>
            idx = html_text.rfind("</body>")
            if idx >= 0:
                html_text = html_text[:idx] + comment_text + "\n" + html_text[idx:]
            applied.append({"canary_id": canary_id, "vector": "TEXT", "value": token, "strategy": strategy})
        
        # Apply JSON-LD watermark
        canary_id_ld, token_ld = generate_session_watermark_token(session_id, "JSONLD", conn)
        html_text = inject_jsonld_watermark(html_text, canary_id_ld, token_ld, session_id)
        applied.append({"canary_id": canary_id_ld, "vector": "JSONLD", "value": token_ld, "strategy": "jsonld_script"})
        
        # Apply BEACON
        canary_id_bc, token_bc = generate_session_watermark_token(session_id, "BEACON", conn)
        html_text = inject_beacon(html_text, canary_id_bc, token_bc, public_base_url)
        applied.append({"canary_id": canary_id_bc, "vector": "BEACON", "value": token_bc, "strategy": "beacon_img"})
        
        # Apply HONEYKEY
        canary_id_hk, token_hk = generate_session_watermark_token(session_id, "HONEYKEY", conn)
        html_text = inject_honeykey(html_text, canary_id_hk, token_hk)
        applied.append({"canary_id": canary_id_hk, "vector": "HONEYKEY", "value": token_hk, "strategy": "honeykey_in_comment"})
        
        html_text = _ensure_utf8_meta(html_text)
        mutated_bytes = html_text.encode("utf-8")
        
    # JSON content
    elif is_json:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception:
            return content_bytes, applied
        
        if not isinstance(data, (dict, list)):
            return content_bytes, applied
        
        # Apply API canary
        canary_id, token = generate_session_watermark_token(session_id, "API", conn)
        data = inject_json_canary(data, canary_id, token)
        applied.append({"canary_id": canary_id, "vector": "API", "value": token, "strategy": "json_top_level"})
        
        # Apply SYNTHETIC_JSON watermark
        canary_id_sj, token_sj = generate_session_watermark_token(session_id, "SYNTHETIC_JSON", conn)
        data = inject_synthetic_json_canary(data, canary_id_sj, token_sj)
        applied.append({"canary_id": canary_id_sj, "vector": "SYNTHETIC_JSON", "value": token_sj, "strategy": "json_top_level"})
        
        mutated_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    
    else:
        return content_bytes, applied
    
    # Store in session cache
    if session_id not in apply_watermark_matrix._session_cache:
        apply_watermark_matrix._session_cache[session_id] = {}
    apply_watermark_matrix._session_cache[session_id][cache_key] = (
        bytes(mutated_bytes),
        [dict(w) for w in applied],  # Deep copy
    )
    
    return mutated_bytes, applied


def watermark_fallback_core(
    ctx: Any,
    session: Any,
    upstream: Any,
    conn=None,
) -> tuple[bytes, bool]:
    """Fallback watermark injection that applies full watermark matrix.
    
    Used when primary mutation fails or for explicit watermark-only mode.
    """
    if upstream is None:
        return b"", False
    
    status_code = getattr(upstream, "status_code", 200)
    if status_code in (204, 304):
        content = getattr(upstream, "content", b"") or b""
        return (content if isinstance(content, bytes) else bytes(content or b"")), False
    
    method = getattr(ctx, "method", "")
    if not method and hasattr(ctx, "request"):
        method = getattr(ctx.request, "method", "")
    if str(method).upper() == "HEAD":
        content = getattr(upstream, "content", b"") or b""
        return (content if isinstance(content, bytes) else bytes(content or b"")), False
    
    content_bytes = getattr(upstream, "content", b"") or b""
    if not isinstance(content_bytes, bytes):
        content_bytes = bytes(content_bytes or b"")
    
    if not content_bytes:
        return b"", False
    
    headers = getattr(upstream, "headers", {}) or {}
    content_type = ""
    if hasattr(headers, "get"):
        content_type = headers.get("content-type", "") or ""
    elif isinstance(headers, Mapping):
        for k, v in headers.items():
            if str(k).lower() == "content-type":
                content_type = str(v)
                break
    
    session_id = getattr(session, "session_id", None) or getattr(ctx, "session_id", None) or "anon"
    
    try:
        mutated_bytes, applied = apply_watermark_matrix(
            content_bytes=content_bytes,
            content_type=content_type,
            session_id=session_id,
            ctx=ctx,
            conn=conn,
        )
        
        if not applied:
            return content_bytes, False
        
        # Record all applied watermarks
        for wm in applied:
            registry.record_exposure(
                canary_id=wm["canary_id"],
                session=session,
                ctx=ctx,
                resource=getattr(ctx, "path", ""),
                block_text=wm["value"],
                vector=wm["vector"],
                outcome="success",
                conn=conn,
            )
            _note_exposure(session, wm["canary_id"], conn=conn)
            registry.record_injection_outcome(
                canary_id=wm["canary_id"],
                vector=wm["vector"],
                session_id=str(session_id),
                time=registry.now_iso(),
                outcome="success",
                resource=getattr(ctx, "path", ""),
                conn=conn,
            )
        
        return mutated_bytes, True
    
    except Exception as exc:
        logger.error("Watermark matrix fallback error: %s", exc)
        _append_fault_record({
            "event_type": "watermark_matrix_fallback_error",
            "session_id": str(session_id),
            "client_key": getattr(ctx, "client_key", ""),
            "path": getattr(ctx, "path", ""),
            "error": str(exc),
            "ts": registry.now_iso(),
        }, conn=conn)
        return content_bytes, False


def get_watermark_matrix_info() -> dict:
    """Return information about available watermark vectors and placement strategies."""
    return {
        "vectors": WATERMARK_VECTORS,
        "placement_strategies": PLACEMENT_STRATEGIES,
        "total_vectors": len(WATERMARK_VECTORS),
        "total_strategies": len(PLACEMENT_STRATEGIES),
    }


def handle_decoy(
    ctx: Any,
    session: Any,
    conn: sqlite3.Connection | None = None,
) -> Response | None:
    """Handle decoy routes: configured API decoy payload or synthetic index HTML.

    Uses shared canonical segment-safe runtime-config predicate (Phase 0 Hard Rule).
    """
    from sb.config import is_trap_path

    raw_path = getattr(ctx, "path", "") or ""
    if not is_trap_path(raw_path):
        return None

    norm_path = raw_path.rstrip("/") if raw_path != "/" else "/"

    decoy_api_path = get_configured_trap_api_path()
    if decoy_api_path:
        norm_decoy = decoy_api_path.rstrip("/") if decoy_api_path != "/" else "/"
        decoy_prefix = norm_decoy if norm_decoy.endswith("/") else norm_decoy + "/"
        if norm_path == norm_decoy or raw_path.startswith(decoy_prefix):
            canary = registry.get("SB-CAN-0003", conn=conn)
            if canary is None:
                canaries = registry.list_canaries(conn=conn)
                canary = canaries[0] if canaries else None

            payload = decoy_api_payload(canary)
            canary_id = getattr(canary, "canary_id", "SB-CAN-0003")
            block_text = getattr(canary, "canonical_content", "") or str(payload)

            registry.record_exposure(
                canary_id=canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=block_text,
                vector="API",
                outcome="success",
                conn=conn,
            )
            _note_exposure(session, canary_id, conn=conn)
            return JSONResponse(content=payload)

    configured_trap_paths = get_configured_trap_paths()
    if configured_trap_paths:
        html_content = decoy_index_html()
        for c in registry.list_canaries(conn=conn):
            if c.status == "DRAFT":
                continue
            block_text = registry.injected_block_text(c)
            html_content = insert_canary(html_content, block_text, canary_id=c.canary_id)
            registry.record_exposure(
                canary_id=c.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=block_text,
                vector="TEXT",
                outcome="success",
                conn=conn,
            )
            _note_exposure(session, c.canary_id, conn=conn)
        return HTMLResponse(content=insert_hidden_link(html_content))

    return None


class ScapeBustersOffenseHooks:
    """OffenseHooks implementation conforming to sb.hooks.OffenseHooks protocol."""

    def classify_request(
        self,
        ctx: Any,
        session: Any,
        conn: sqlite3.Connection | None = None,
    ) -> layer3.TrapHit | None:
        return layer3.classify_request(ctx, session, conn=conn)

    def handle_decoy(
        self,
        ctx: Any,
        session: Any,
        conn: sqlite3.Connection | None = None,
    ) -> Response | None:
        return handle_decoy(ctx, session, conn=conn)

    def transform_response(
        self,
        ctx: Any,
        session: Any,
        upstream: Any,
        conn: sqlite3.Connection | None = None,
    ) -> bytes:
        return transform_response(ctx, session, upstream, conn=conn)

    def extract_canary_ids(self, body: bytes) -> tuple[str, ...]:
        return extract_canary_ids(body)

    def reset(self) -> None:
        """Reset durable session bindings cache and in-memory indices."""
        registry.reset_session_bindings()
