"""Edge pipeline — request decision flow for Phase0.

Pipeline: context -> session -> telemetry/decoy -> upstream-fetch -> unconditional-mutation -> response.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request, Response

from ..config import SB_MUTATION_MODE, SB_TRAP_API_PATH, SB_TRAP_PATHS
from ..store.db import get_connection
from ..store.sessions import save_session
from .context import RequestContext, build_context
from .intel import init_request, record_decision
from .proxy import UpstreamResponse, proxy
from .session import Session, sessions

logger = logging.getLogger("sb.edge.pipeline")

TRAFFIC_STAGES = frozenset({"OFFENSE", "ORIGIN"})
TRAFFIC_LAYERS = TRAFFIC_STAGES  # Alias for backward compatibility
TRAFFIC_DECISIONS = frozenset({
    "FAST_PATH",
    "SANDBOX",
})


def _get_offense_hooks():
    """Resolve offense hooks directly from sb.offense with loudly logged unavailable fallback."""
    try:
        from sb.offense.injector import handle_decoy, transform_response

        return handle_decoy, transform_response
    except ImportError as exc:
        logger.error("sb.offense hooks unavailable: %s", exc)
        return None, None


def _append_fault_record(record: dict[str, Any]) -> None:
    """Append fault record to durable store and ledger without unchained silent failure."""
    try:
        from ..store.ledger import append_event

        append_event("fault", record)
        return
    except ImportError:
        pass
    try:
        from sb.store.ledger import append_event

        append_event("fault", record)
        return
    except ImportError:
        pass
    except Exception as exc:
        logger.error("Failed to append fault event to ledger: %s", exc)


def is_trap_path(path: str) -> bool:
    """Check if the path matches runtime-configured trap paths.

    No hard-coded decoy routes; returns False if not configured.
    """
    if not SB_TRAP_PATHS and not SB_TRAP_API_PATH:
        return False
    norm_path = path.rstrip("/") if path != "/" else "/"
    trap_paths = [p.rstrip("/") if p != "/" else "/" for p in SB_TRAP_PATHS]
    if norm_path in trap_paths:
        return True
    if SB_TRAP_API_PATH:
        api_norm = SB_TRAP_API_PATH.rstrip("/") if SB_TRAP_API_PATH != "/" else "/"
        if norm_path == api_norm:
            return True
    return False


def is_control_endpoint(path: str) -> bool:
    """Check if endpoint is an internal management endpoint bypassing proxy.

    Registered FastAPI management endpoints handle before proxy catchall;
    all origin endpoints reaching proxy must mutate when eligible.
    """
    return False


def is_eligible_for_mutation(method: str, status_code: int, content_type: str) -> bool:
    """Return True if response is eligible for sandboxed offensive mutation."""
    if method in {"HEAD", "OPTIONS"}:
        return False
    if status_code in {204, 205, 304}:
        return False
    ct = content_type.lower()
    return "text/html" in ct or "application/json" in ct


def _deterministic_offensive_fallback(
    ctx: RequestContext,
    session: Session,
    upstream: UpstreamResponse | Any,
) -> tuple[bytes, bool]:
    """Deterministic offensive fallback using W2 session-bound canary binding.

    Returns (body_bytes, mutated_bool). Malformed source returns unmutated bytes
    with explicit fault logging per total-error rule.
    """
    content_bytes = getattr(upstream, "content", b"") or b""
    if not isinstance(content_bytes, bytes):
        content_bytes = bytes(content_bytes)

    content_type = ""
    headers = getattr(upstream, "headers", {}) or {}
    if hasattr(headers, "get"):
        content_type = (headers.get("content-type", "") or "").lower()

    if "text/html" in content_type:
        binding = None
        try:
            from sb.canary.registry import bind_session_canary

            binding = bind_session_canary(session.session_id, vector="html")
        except Exception as exc:
            logger.error("Failed to bind session canary for HTML fallback: %s", exc)

        canary_id = binding.canary_id if binding else f"SB-CANARY-FALLBACK-{session.session_id[:8]}"
        canary_value = binding.value if binding else f"CONFIDENTIAL-REF-{canary_id}"

        if canary_id not in session.canaries_exposed:
            session.canaries_exposed.append(canary_id)

        try:
            from sb.canary.registry import record_exposure

            record_exposure(canary_id, session, ctx, ctx.path, canary_value, vector="html")
        except Exception:
            pass

        text = content_bytes.decode("utf-8", errors="replace")

        try:
            from sb.offense.injector import insert_canary

            mutated_text = insert_canary(text, canary_value, canary_id=canary_id)
            return mutated_text.encode("utf-8"), True
        except Exception:
            pass

        # Deterministic additive marker before </main> or </body>; no hardcoded trap paths
        p_tag = f'<p class="sb-canary" data-canary-id="{canary_id}">{canary_value}</p>'
        lower = text.lower()
        main_idx = lower.rfind("</main>")
        if main_idx != -1:
            mutated_text = text[:main_idx] + p_tag + text[main_idx:]
        else:
            body_idx = lower.rfind("</body>")
            if body_idx != -1:
                mutated_text = text[:body_idx] + p_tag + text[body_idx:]
            else:
                mutated_text = text + p_tag
        return mutated_text.encode("utf-8"), True

    if "application/json" in content_type:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception as parse_err:
            logger.error(
                "Eligible JSON mutation failed on malformed source for %s: %s; returning unmutated bytes per total-error rule",
                ctx.path,
                parse_err,
            )
            _append_fault_record({
                "event_type": "malformed_json_source",
                "session_id": session.session_id,
                "client_key": ctx.client_key,
                "path": ctx.path,
                "error": str(parse_err),
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            return content_bytes, False

        if not isinstance(data, (dict, list)):
            logger.error(
                "Eligible JSON mutation cannot mutate scalar source for %s without changing semantics; returning unmutated bytes",
                ctx.path,
            )
            _append_fault_record({
                "event_type": "json_scalar_source_unmutatable",
                "session_id": session.session_id,
                "client_key": ctx.client_key,
                "path": ctx.path,
                "error": "scalar JSON source cannot mutate additively",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            return content_bytes, False

        binding = None
        try:
            from sb.canary.registry import bind_session_canary

            binding = bind_session_canary(session.session_id, vector="json")
        except Exception as exc:
            logger.error("Failed to bind session canary for JSON fallback: %s", exc)

        canary_id = binding.canary_id if binding else f"SB-CANARY-FALLBACK-{session.session_id[:8]}"
        canary_value = binding.value if binding else f"CONFIDENTIAL-REF-{canary_id}"

        if canary_id not in session.canaries_exposed:
            session.canaries_exposed.append(canary_id)

        try:
            from sb.canary.registry import record_exposure

            record_exposure(canary_id, session, ctx, ctx.path, canary_value, vector="json")
        except Exception:
            pass

        try:
            from sb.offense.injector import inject_json_canary

            mutated_data = inject_json_canary(data, canary_id, canary_value)
            return json.dumps(mutated_data).encode("utf-8"), True
        except Exception:
            pass

        # Deterministic additive JSON injection
        canary_meta = {"canary_id": canary_id, "token": canary_value}
        if isinstance(data, dict):
            mutated_dict = dict(data)
            mutated_dict["_sb_canary"] = canary_meta
            return json.dumps(mutated_dict).encode("utf-8"), True
        elif isinstance(data, list):
            mutated_list = list(data)
            if mutated_list and isinstance(mutated_list[0], dict):
                first = dict(mutated_list[0])
                first["_sb_canary"] = canary_meta
                mutated_list[0] = first
            else:
                mutated_list.append({"_sb_canary": canary_meta})
            return json.dumps(mutated_list).encode("utf-8"), True

    return content_bytes, False


def log_event(
    ctx: RequestContext,
    session: Session,
    layer: str,
    decision: str,
    status_code: int,
    reasons: list | None = None,
    risk_score: int | None = None,
) -> None:
    """Log a traffic event to database and append to forensic ledger."""
    if reasons is None:
        reasons = []
    if layer not in TRAFFIC_STAGES and layer not in TRAFFIC_LAYERS:
        raise ValueError(f"Unsupported traffic stage/layer: {layer}")
    if decision not in TRAFFIC_DECISIONS:
        raise ValueError(f"Unsupported traffic decision: {decision}")

    ts = datetime.now(timezone.utc).isoformat()
    event_id = f"evt-{uuid.uuid4().hex[:8]}"

    if event_id not in session.event_ids:
        session.event_ids.append(event_id)

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code,
                user_agent, header_fp, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                ts,
                session.session_id,
                ctx.client_key,
                ctx.ip,
                ctx.request.method,
                ctx.path,
                status_code,
                ctx.user_agent,
                ctx.header_fp,
                layer,
                decision,
                0 if risk_score is None else risk_score,
                json.dumps(reasons),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    record = {
        "event_id": event_id,
        "session_id": session.session_id,
        "client_key": ctx.client_key,
        "ip": ctx.ip,
        "method": ctx.request.method,
        "path": ctx.path,
        "status_code": status_code,
        "user_agent": ctx.user_agent,
        "header_fp": ctx.header_fp,
        "layer": layer,
        "decision": decision,
        "risk_score": 0 if risk_score is None else risk_score,
        "reasons": reasons,
        "ts": ts,
    }
    try:
        from ..store.ledger import append_event

        append_event("traffic", record)
    except ImportError:
        try:
            from sb.store.ledger import append_event

            append_event("traffic", record)
        except ImportError:
            pass
    except Exception as ledger_err:
        logger.error("Failed to append traffic event to ledger: %s", ledger_err)


async def handle(request: Request) -> Response:
    """Handle an incoming request through the edge pipeline."""
    ctx = build_context(request)
    session = sessions.get_or_create(ctx)

    try:
        init_request(ctx, session)
        save_session(session)
        return await _handle_request(ctx, session)
    finally:
        save_session(session)


async def _handle_request(ctx: RequestContext, session: Session) -> Response:
    """Execute edge pipeline flow: decoy check -> upstream proxy -> unconditional mutation."""
    # 1. Decoy / trap handling (only if runtime configured)
    if is_trap_path(ctx.path):
        handle_decoy_fn, _ = _get_offense_hooks()
        if handle_decoy_fn is not None:
            decoy_resp = handle_decoy_fn(ctx, session)
            if decoy_resp is not None:
                session.state = "SANDBOX"
                if ctx.path not in session.traps_triggered:
                    session.traps_triggered.append(ctx.path)
                log_event(ctx, session, "OFFENSE", "SANDBOX", decoy_resp.status_code, ["TRAP_DECOY_HIT"])
                record_decision(session, "OFFENSE", "SANDBOX")
                save_session(session)
                return decoy_resp

    # 2. Upstream fetch
    try:
        upstream = await proxy(ctx)
    except Exception as exc:
        logger.error(
            "Upstream proxy request failed for %s %s: %s",
            ctx.request.method,
            ctx.path,
            exc,
        )
        _append_fault_record({
            "event_type": "proxy_origin_error",
            "session_id": session.session_id,
            "client_key": ctx.client_key,
            "path": ctx.path,
            "method": ctx.request.method,
            "status_code": 502,
            "error": str(exc),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # Origin outage cannot be fabricated as successful pass-through
        return Response(
            content=b"Bad Gateway: Origin unreachable",
            status_code=502,
            media_type="text/plain",
        )

    # 3. Post-upstream processing with fault resilience
    try:
        content_type = upstream.headers.get("content-type", "")
        eligible = is_eligible_for_mutation(
            ctx.request.method, upstream.status_code, content_type
        )

        if eligible and SB_MUTATION_MODE != "passthrough":
            _, transform_response_fn = _get_offense_hooks()
            mutated = False
            if transform_response_fn is not None:
                try:
                    body = transform_response_fn(ctx, session, UpstreamResponse(upstream))
                    mutated = True
                except Exception as mut_err:
                    logger.error(
                        "Offense mutation failed for %s: %s; using deterministic offensive fallback",
                        ctx.path,
                        mut_err,
                    )
                    _append_fault_record({
                        "event_type": "mutation_hook_error",
                        "session_id": session.session_id,
                        "client_key": ctx.client_key,
                        "path": ctx.path,
                        "error": str(mut_err),
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                    body, mutated = _deterministic_offensive_fallback(ctx, session, upstream)
            else:
                body, mutated = _deterministic_offensive_fallback(ctx, session, upstream)

            decision = "SANDBOX" if mutated else "FAST_PATH"
        else:
            body = upstream.content
            decision = "FAST_PATH"

        log_event(ctx, session, "ORIGIN", decision, upstream.status_code, [])
        record_decision(session, "ORIGIN", decision)
        save_session(session)

        out_headers = dict(upstream.headers)
        out_headers.pop("content-length", None)
        out_headers.pop("transfer-encoding", None)
        out_headers.pop("content-encoding", None)

        return Response(
            content=body,
            status_code=upstream.status_code,
            headers=out_headers,
        )
    except Exception as pipeline_err:
        logger.exception(
            "Internal proxy pipeline fault on %s: %s; returning captured upstream bytes",
            ctx.path,
            pipeline_err,
        )
        _append_fault_record({
            "event_type": "internal_pipeline_fault",
            "session_id": session.session_id,
            "client_key": ctx.client_key,
            "path": ctx.path,
            "error": str(pipeline_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        fallback_headers = dict(upstream.headers)
        fallback_headers.pop("content-length", None)
        fallback_headers.pop("transfer-encoding", None)
        fallback_headers.pop("content-encoding", None)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=fallback_headers,
        )
