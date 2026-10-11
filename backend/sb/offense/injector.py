"""Response transformation, canary injection, decoy handling, and OffenseHooks for ScrapeBuster Phase 1."""

from __future__ import annotations

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
