"""Response transformation, canary injection, decoy handling, and OffenseHooks."""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
from collections.abc import Mapping
from contextlib import closing
from typing import Any

from fastapi import Response
from fastapi.responses import HTMLResponse, JSONResponse
from sb.canary import registry
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


def insert_canary(html: str, block_text: str, canary_id: str | None = None) -> str:
    """Insert canary markup additively before </main>, or before </body> as fallback.

    Additive-safe: returns unchanged if text already present or no insertion boundary.
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


def _note_exposure(session: Any, canary_id: str) -> None:
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
            with closing(db.get_connection()) as conn, conn:
                row = conn.execute(
                    "SELECT canaries_exposed FROM sessions WHERE session_id = ?",
                    (str(session_id),),
                ).fetchone()
                if row is not None:
                    raw = row["canaries_exposed"]
                    exposed_list = json.loads(raw) if raw else []
                    if canary_id not in exposed_list:
                        exposed_list.append(canary_id)
                        conn.execute(
                            "UPDATE sessions SET canaries_exposed = ? WHERE session_id = ?",
                            (json.dumps(exposed_list), str(session_id)),
                        )
        except Exception as exc:
            logger.warning("Could not persist canary exposure to session store: %s", exc)


def deterministic_fallback(ctx: Any, session: Any, upstream: Any) -> bytes:
    """Deterministic fallback returning unmodified upstream content."""
    if upstream is None:
        return b""
    content = getattr(upstream, "content", b"")
    return content if isinstance(content, bytes) else bytes(content or b"")


def transform_response(ctx: Any, session: Any, upstream: Any) -> bytes:
    """Transform eligible HTML and JSON unconditionally with deterministic fallback on error.

    Maintains integrity of binary, HEAD, 204, and 304 responses.
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
        binding = None
        try:
            html_text = content_bytes.decode("utf-8", errors="replace")
            html_text = insert_hidden_link(html_text)

            binding = registry.bind_session_canary(
                session_id=str(session_id),
                vector="TEXT",
            )
            block_text = f"Security Verification Token: {binding.value}"
            html_text = insert_canary(html_text, block_text, canary_id=binding.canary_id)

            # Record exposure only AFTER actual response injection succeeds
            registry.record_exposure(
                canary_id=binding.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=block_text,
                vector="TEXT",
                outcome="success",
            )
            _note_exposure(session, binding.canary_id)

            # Inject placed seed canary if path matches placement
            norm_path = raw_path.rstrip("/") if raw_path != "/" else "/"
            placements_map = placements()
            if norm_path in placements_map:
                seed_canary = placements_map[norm_path]
                db_canary = registry.get(seed_canary.canary_id)
                if db_canary:
                    seed_text = registry.injected_block_text(db_canary)
                    html_text = insert_canary(html_text, seed_text, canary_id=db_canary.canary_id)
                    registry.record_exposure(
                        canary_id=db_canary.canary_id,
                        session=session,
                        ctx=ctx,
                        resource=raw_path,
                        block_text=seed_text,
                        vector="TEXT",
                        outcome="success",
                    )
                    _note_exposure(session, db_canary.canary_id)

            return html_text.encode("utf-8")
        except Exception as exc:
            logger.warning("Deterministic fallback for HTML mutation error: %s", exc)
            try:
                registry.record_injection_outcome(
                    canary_id=binding.canary_id if binding else None,
                    vector="TEXT",
                    session_id=str(session_id),
                    time=registry.now_iso(),
                    outcome="fallback",
                    error=str(exc),
                    resource=raw_path,
                )
            except Exception:
                pass
            return deterministic_fallback(ctx, session, upstream)

    if is_json:
        binding = None
        try:
            json_text = content_bytes.decode("utf-8", errors="replace")
            data = json.loads(json_text)

            binding = registry.bind_session_canary(
                session_id=str(session_id),
                vector="API",
            )
            mutated_data = inject_json_canary(data, binding.canary_id, binding.value)
            serialized = json.dumps(mutated_data, ensure_ascii=False)

            # Record exposure only AFTER actual response injection succeeds
            registry.record_exposure(
                canary_id=binding.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=binding.value,
                vector="API",
                outcome="success",
            )
            _note_exposure(session, binding.canary_id)

            return serialized.encode("utf-8")
        except Exception as exc:
            logger.warning("Deterministic fallback for JSON mutation error: %s", exc)
            try:
                registry.record_injection_outcome(
                    canary_id=binding.canary_id if binding else None,
                    vector="API",
                    session_id=str(session_id),
                    time=registry.now_iso(),
                    outcome="fallback",
                    error=str(exc),
                    resource=raw_path,
                )
            except Exception:
                pass
            return deterministic_fallback(ctx, session, upstream)

    return content_bytes


def handle_decoy(ctx: Any, session: Any) -> Response | None:
    """Handle decoy routes: configured API decoy payload or synthetic index HTML."""
    raw_path = getattr(ctx, "path", "") or ""
    norm_path = raw_path.rstrip("/") if raw_path != "/" else "/"

    decoy_api_path = get_configured_trap_api_path()
    if decoy_api_path:
        norm_decoy = decoy_api_path.rstrip("/") if decoy_api_path != "/" else "/"
        if norm_path == norm_decoy:
            canary = registry.get("SB-CAN-0003")
            if canary is None:
                canaries = registry.list_canaries()
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
            )
            _note_exposure(session, canary_id)
            return JSONResponse(content=payload)

    configured_trap_paths = get_configured_trap_paths()
    if configured_trap_paths:
        matched = False
        for tp in configured_trap_paths:
            norm_tp = tp.rstrip("/") if tp != "/" else "/"
            if norm_path == norm_tp or raw_path.startswith(tp if tp.endswith("/") else tp + "/"):
                matched = True
                break

        if matched:
            html_content = decoy_index_html()
            for c in registry.list_canaries():
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
                )
                _note_exposure(session, c.canary_id)
            return HTMLResponse(content=insert_hidden_link(html_content))

    return None


class ScapeBustersOffenseHooks:
    """OffenseHooks implementation conforming to sb.hooks.OffenseHooks protocol."""

    def classify_request(self, ctx: Any, session: Any) -> layer3.TrapHit | None:
        return layer3.classify_request(ctx, session)

    def handle_decoy(self, ctx: Any, session: Any) -> Response | None:
        return handle_decoy(ctx, session)

    def transform_response(self, ctx: Any, session: Any, upstream: Any) -> bytes:
        return transform_response(ctx, session, upstream)

    def reset(self) -> None:
        """Reset durable session bindings and counters."""
        registry.reset_session_bindings()
