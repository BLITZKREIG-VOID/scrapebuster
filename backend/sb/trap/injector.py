"""Response transformation, canary injection, decoy handling, and TrapHooks."""

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
from sb.store import db
from sb.trap import layer3
from sb.trap.decoys import (
    INTERNAL_INDEX_PATHS,
    decoy_api_payload,
    decoy_index_html,
)
from sb.trap.honeypots import DECOY_API_PATH, HIDDEN_LINK_HTML, ROBOTS_PREFIX

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
    """Insert HIDDEN_LINK_HTML immediately after the first <body...> open tag.

    If the page already contains it or has no <body>, return unchanged.
    """
    if HIDDEN_LINK_HTML in html:
        return html
    m = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    if not m:
        return html
    end = m.end()
    return html[:end] + HIDDEN_LINK_HTML + html[end:]


def insert_canary(html: str, block_text: str) -> str:
    """Insert f"<p>{html.escape(block_text)}</p>" immediately before the LAST </main>.

    Unchanged if no </main>.
    """
    matches = list(re.finditer(r"</main\s*>", html, flags=re.IGNORECASE))
    if not matches:
        return html
    last_match = matches[-1]
    start = last_match.start()
    p_tag = f"<p>{html_lib.escape(block_text)}</p>"
    return html[:start] + p_tag + html[start:]


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


def transform_response(ctx: Any, session: Any, upstream: Any) -> bytes:
    """Transform response: hidden link for every session, canary injected if session is TRAPPED."""
    headers = getattr(upstream, "headers", {}) or {}
    content_type = ""
    if hasattr(headers, "get"):
        content_type = headers.get("content-type", "") or ""
    elif isinstance(headers, Mapping):
        for k, v in headers.items():
            if str(k).lower() == "content-type":
                content_type = str(v)
                break

    if "text/html" not in content_type.lower():
        content = getattr(upstream, "content", b"")
        return content if isinstance(content, bytes) else bytes(content or b"")

    content_bytes = getattr(upstream, "content", b"") or b""
    html_text = content_bytes.decode("utf-8", errors="replace")

    # Insert hidden link for EVERY session
    html_text = insert_hidden_link(html_text)

    # Inject canary only if session is TRAPPED
    state = getattr(session, "state", None)
    if state == "TRAPPED":
        raw_path = getattr(ctx, "path", "") or ""
        norm_path = raw_path.rstrip("/") if raw_path != "/" else "/"
        placements_map = placements()
        if norm_path in placements_map:
            canary = placements_map[norm_path]
            db_canary = registry.get(canary.canary_id)
            if db_canary is None:
                logger.warning(
                    "Unregistered canary %s for placement path %s",
                    canary.canary_id,
                    raw_path,
                )
            else:
                block_text = registry.injected_block_text(db_canary)
                html_text = insert_canary(html_text, block_text)
                registry.record_exposure(
                    canary_id=db_canary.canary_id,
                    session=session,
                    ctx=ctx,
                    resource=raw_path,
                    block_text=block_text,
                )
                _note_exposure(session, db_canary.canary_id)

    return html_text.encode("utf-8")


def handle_decoy(ctx: Any, session: Any) -> Response | None:
    """Handle decoy routes: API decoy carrying canary 0003 or HTML index linking docs."""
    raw_path = getattr(ctx, "path", "") or ""
    norm_path = raw_path.rstrip("/") if raw_path != "/" else "/"
    decoy_api_norm = DECOY_API_PATH.rstrip("/")

    # 1. DECOY_API_PATH
    if norm_path == decoy_api_norm:
        canary = registry.get("SB-CAN-0003")
        if canary is None:
            logger.warning("Canary SB-CAN-0003 not found for decoy API path %s", raw_path)
            return JSONResponse(
                content={
                    "service": "nimbus-reconcile",
                    "version": "v3",
                    "status": "deprecated",
                },
                status_code=503,
            )

        payload = decoy_api_payload(canary)
        if getattr(session, "state", None) == "TRAPPED":
            block_text = registry.injected_block_text(canary)
            registry.record_exposure(
                canary_id=canary.canary_id,
                session=session,
                ctx=ctx,
                resource=raw_path,
                block_text=block_text,
            )
            _note_exposure(session, canary.canary_id)
        return JSONResponse(content=payload)

    # 2. INTERNAL_INDEX_PATHS or under /internal/
    internal_index_norms = {p.rstrip("/") for p in INTERNAL_INDEX_PATHS}
    if norm_path in internal_index_norms or raw_path.startswith("/internal/"):
        html_content = decoy_index_html("ExampleCorp Internal Documentation Index")
        robots_area = norm_path == ROBOTS_PREFIX.rstrip("/") or raw_path.startswith(ROBOTS_PREFIX)
        if robots_area and getattr(session, "state", None) == "TRAPPED":
            html_content = _inject_all_canaries(html_content, ctx, session, raw_path)
        return HTMLResponse(content=insert_hidden_link(html_content))

    return None


def _inject_all_canaries(html_text: str, ctx: Any, session: Any, resource: str) -> str:
    """TRAP-ROBOTS-01 payload: every published canary, each recorded as an exposure.

    Upstreams without canary placement pages (e.g. the CampusCart SPA, which has no
    ``</main>`` to inject into) still expose all canaries through the trap itself.
    """
    for canary in registry.list_canaries():
        if canary.status == "DRAFT":
            continue
        block_text = registry.injected_block_text(canary)
        html_text = insert_canary(html_text, block_text)
        registry.record_exposure(
            canary_id=canary.canary_id,
            session=session,
            ctx=ctx,
            resource=resource,
            block_text=block_text,
        )
        _note_exposure(session, canary.canary_id)
    return html_text

    return None


class ScapeBustersTrapHooks:
    """Layer 3 TrapHooks implementation conforming to sb.hooks.TrapHooks protocol."""

    def classify_request(self, ctx: Any, session: Any) -> layer3.TrapHit | None:
        return layer3.classify_request(ctx, session)

    def handle_decoy(self, ctx: Any, session: Any) -> Response | None:
        return handle_decoy(ctx, session)

    def transform_response(self, ctx: Any, session: Any, upstream: Any) -> bytes:
        return transform_response(ctx, session, upstream)

    def reset(self) -> None:
        """No-op: trap_hits and exposures reside in SQLite, reset by db.reset_db()."""
