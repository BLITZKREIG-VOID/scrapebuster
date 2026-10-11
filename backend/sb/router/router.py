"""Dynamic Router for ScrapeBuster Phase 2 (PRD M2 / FR-2.3, FR-2.4, FR-2.6).

Evaluates real-time request paths against session asset ratio and route baselines:
- FAST_PATH: high-trust browser sessions bypass sandboxing with ZERO response mutation.
- SANDBOX: low-trust sessions, cold starts, and anomaly-locked scrapers undergo full canary injection.
- Fail-offensive: any classifier/router failure routes strictly to SANDBOX with a visible fault record.
Preserves an in-memory audit trail of recent routing decisions.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..classifier.classifier import ARClassifier, ClassificationResult, classifier as default_classifier
from ..edge.context import RequestContext
from ..edge.session import Session

logger = logging.getLogger("sb.router")

MAX_AUDIT_TRAIL_LEN = 1000


@dataclass
class RouterDecision:
    decision: str  # "FAST_PATH" | "SANDBOX"
    state: str  # "FAST" | "SANDBOX" | "ADAPTIVE"
    trust_score: float
    confidence_score: float
    route_class: str
    reasons: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    ts: str = ""
    ar_classifier_decision: str = ""
    router_decision: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "state": self.state,
            "trust_score": self.trust_score,
            "confidence_score": self.confidence_score,
            "route_class": self.route_class,
            "reasons": list(self.reasons),
            "latency_ms": self.latency_ms,
            "ts": self.ts,
            "ar_classifier_decision": self.ar_classifier_decision,
            "router_decision": self.router_decision,
        }


class DynamicRouter:
    """Real-time dynamic router connecting edge request context and AR classifier."""

    def __init__(self, classifier_instance: ARClassifier | None = None) -> None:
        self.classifier = classifier_instance or default_classifier
        self._lock = threading.RLock()
        self._audit_trail: list[dict[str, Any]] = []

    def normalize_route(self, path: str) -> str:
        """Normalize path to consistent route key."""
        if not path:
            return "/"
        # Strip query string or fragment if present
        clean_path = path.split("?")[0].split("#")[0].strip()
        if not clean_path.startswith("/"):
            clean_path = "/" + clean_path
        return clean_path

    def evaluate(self, ctx: RequestContext, session: Session) -> RouterDecision:
        """Evaluate route decision for incoming request in the active request path."""
        t_start = time.perf_counter()
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        route_key = self.normalize_route(getattr(ctx, "path", "/"))

        try:
            is_locked = bool(getattr(session, "locked_sandbox", False))

            # Static asset requests: inherit session's active state and decision as part of cascade,
            # preserving session trust score without immature individual static route reset
            if getattr(ctx, "is_static", False):
                duration_ms = round((time.perf_counter() - t_start) * 1000.0, 4)
                current_state = "SANDBOX" if is_locked else getattr(session, "state", "SANDBOX")
                current_decision = "SANDBOX" if (is_locked or current_state == "SANDBOX") else "FAST_PATH"
                r_class = "locked_sandbox" if is_locked else ("browser_cascade" if current_decision == "FAST_PATH" else "static_asset")
                reasons_list = ["STATIC_ASSET_LOCKED"] if is_locked else (["STATIC_ASSET_FAST_PATH"] if current_decision == "FAST_PATH" else ["STATIC_ASSET_SANDBOX"])

                router_decision = RouterDecision(
                    decision=current_decision,
                    state=current_state,
                    trust_score=getattr(session, "trust_score", 0.0),
                    confidence_score=getattr(session, "confidence_score", 0.0) if current_decision == "SANDBOX" else (getattr(session, "confidence_score", 1.0) or 1.0),
                    route_class=r_class,
                    reasons=reasons_list,
                    latency_ms=duration_ms,
                    ts=now_iso,
                )
                with self._lock:
                    self._audit_trail.append({
                        "ts": now_iso,
                        "session_id": getattr(session, "session_id", "unknown"),
                        "path": route_key,
                        "decision": router_decision.decision,
                        "state": router_decision.state,
                        "trust_score": router_decision.trust_score,
                        "confidence_score": router_decision.confidence_score,
                        "route_class": router_decision.route_class,
                        "reasons": list(router_decision.reasons),
                        "latency_ms": duration_ms,
                    })
                    if len(self._audit_trail) > MAX_AUDIT_TRAIL_LEN:
                        self._audit_trail = self._audit_trail[-MAX_AUDIT_TRAIL_LEN:]
                return router_decision

            # 1. Update baseline with current session AR if session is not locked
            # and is an active document/page/API request establishing legitimate cascade patterns
            if not is_locked and (getattr(ctx, "is_document", False) or getattr(session, "asset_ratio", 0.0) > 0):
                try:
                    self.classifier.record_sample(route_key, session.asset_ratio)
                except Exception as rec_err:
                    logger.debug("Non-fatal error updating route baseline for %s: %s", route_key, rec_err)

            # 2. Query classifier
            result: ClassificationResult = self.classifier.classify_session(session, route_key)
            duration_ms = round((time.perf_counter() - t_start) * 1000.0, 4)

            router_decision = RouterDecision(
                decision=result.decision,
                state=result.state,
                trust_score=result.trust_score,
                confidence_score=result.confidence_score,
                route_class=result.route_class,
                reasons=list(result.reasons),
                latency_ms=duration_ms,
                ts=now_iso,
                ar_classifier_decision=result.ar_classifier_decision,
                router_decision=result.router_decision,
            )

            # 3. Append to audit trail
            with self._lock:
                entry = {
                    "ts": now_iso,
                    "session_id": getattr(session, "session_id", "unknown"),
                    "path": route_key,
                    "decision": router_decision.decision,
                    "state": router_decision.state,
                    "trust_score": router_decision.trust_score,
                    "confidence_score": router_decision.confidence_score,
                    "route_class": router_decision.route_class,
                    "reasons": list(router_decision.reasons),
                    "latency_ms": duration_ms,
                    "ar_classifier_decision": router_decision.ar_classifier_decision,
                    "router_decision": router_decision.router_decision,
                }
                self._audit_trail.append(entry)
                if len(self._audit_trail) > MAX_AUDIT_TRAIL_LEN:
                    self._audit_trail = self._audit_trail[-MAX_AUDIT_TRAIL_LEN:]

            return router_decision

        except Exception as exc:
            duration_ms = round((time.perf_counter() - t_start) * 1000.0, 4)
            logger.error("Classifier/router exception for %s: %s; fail-offensive to SANDBOX", route_key, exc)

            # Record visible fault record to persistent ledger
            try:
                from ..edge.pipeline import _append_fault_record

                _append_fault_record({
                    "event_type": "classifier_router_fault",
                    "session_id": getattr(session, "session_id", "unknown"),
                    "path": route_key,
                    "error": str(exc),
                    "fallback_decision": "SANDBOX",
                    "ts": now_iso,
                })
            except Exception:
                pass

            # Fail-offensive fallback
            router_decision = RouterDecision(
                decision="SANDBOX",
                state="SANDBOX",
                trust_score=0.0,
                confidence_score=0.0,
                route_class="router_fault_fallback",
                reasons=["CLASSIFIER_EXCEPTION_FAIL_OFFENSIVE"],
                latency_ms=duration_ms,
                ts=now_iso,
            )

            with self._lock:
                self._audit_trail.append({
                    "ts": now_iso,
                    "session_id": getattr(session, "session_id", "unknown"),
                    "path": route_key,
                    "decision": "SANDBOX",
                    "state": "SANDBOX",
                    "trust_score": 0.0,
                    "confidence_score": 0.0,
                    "route_class": "router_fault_fallback",
                    "reasons": ["CLASSIFIER_EXCEPTION_FAIL_OFFENSIVE"],
                    "latency_ms": duration_ms,
                })
                if len(self._audit_trail) > MAX_AUDIT_TRAIL_LEN:
                    self._audit_trail = self._audit_trail[-MAX_AUDIT_TRAIL_LEN:]

            return router_decision

    def get_audit_trail(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return snapshot of recent router decision audit trail."""
        with self._lock:
            return list(self._audit_trail[-limit:])

    def reset(self) -> None:
        """Reset router audit trail and internal state."""
        with self._lock:
            self._audit_trail.clear()


router = DynamicRouter()
