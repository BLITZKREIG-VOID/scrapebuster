"""Edge session model, tracking, and management for Phase 1 (PRD FR1.2, FR1.3).

Tracks the durable session 7-tuple:
    (session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen)
along with rolling asset ratio: static_count / max(1, api_count).
Preserves session state across server restarts via persistent store fallback.
Operationally bounds in-memory history arrays while full history persists to ledger/traffic.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .context import RequestContext

logger = logging.getLogger("sb.edge.session")

MAX_OPERATIONAL_LIST_LEN = 100


@dataclass
class Session:
    session_id: str
    client_key: str = ""
    client_ip: str = ""
    asn: int | None = None
    asn_status: str = "unavailable"
    ja3_hash: str | None = None
    ja4_hash: str | None = None
    tls_source: str = "none"
    user_agent: str = ""
    header_fp: str = ""
    first_seen: str = ""
    last_seen: str = ""
    request_count: int = 0
    static_count: int = 0
    api_count: int = 0
    asset_ratio: float = 0.0
    trust_score: float = 0.0
    ar_anomaly_streak: int = 0
    locked_sandbox: bool = False
    ar_classifier_decision: str | None = None
    confidence_score: float | None = None
    router_decision: str | None = None
    state: str = "SANDBOX"
    classification: str = "UNKNOWN"
    decision: str = "SANDBOX"
    risk_score: int = 0
    reasons: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    traps_triggered: list[str] = field(default_factory=list)
    canaries_exposed: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    request_window: list[str] = field(default_factory=list)

    def __init__(
        self,
        session_id: str,
        client_key: str = "",
        client_ip: str = "",
        asn: int | None = None,
        asn_status: str = "unavailable",
        ja3_hash: str | None = None,
        ja4_hash: str | None = None,
        tls_source: str = "none",
        user_agent: str = "",
        header_fp: str = "",
        first_seen: str = "",
        last_seen: str = "",
        request_count: int = 0,
        static_count: int = 0,
        api_count: int = 0,
        asset_ratio: float = 0.0,
        trust_score: float = 0.0,
        ar_anomaly_streak: int = 0,
        locked_sandbox: bool = False,
        ar_classifier_decision: str | None = None,
        confidence_score: float | None = None,
        router_decision: str | None = None,
        state: str = "SANDBOX",
        classification: str = "UNKNOWN",
        decision: str = "SANDBOX",
        risk_score: int = 0,
        reasons: list[str] | None = None,
        pages: list[str] | None = None,
        traps_triggered: list[str] | None = None,
        canaries_exposed: list[str] | None = None,
        event_ids: list[str] | None = None,
        request_window: list[str] | None = None,
        # Backward compatibility with ip kwarg
        ip: str = "",
        **extra: Any,
    ):
        self.session_id = session_id
        self.client_key = client_key
        self.client_ip = client_ip or ip or ""
        self.asn = asn
        self.asn_status = asn_status
        self.ja3_hash = ja3_hash
        self.ja4_hash = ja4_hash
        self.tls_source = tls_source
        self.user_agent = user_agent
        self.header_fp = header_fp
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.request_count = request_count
        self.static_count = static_count
        self.api_count = api_count
        self.asset_ratio = asset_ratio
        self.trust_score = float(trust_score or 0.0)
        self.ar_anomaly_streak = int(ar_anomaly_streak or 0)
        self.locked_sandbox = bool(locked_sandbox)
        self.ar_classifier_decision = ar_classifier_decision
        self.confidence_score = confidence_score
        self.router_decision = router_decision
        self.state = state or "SANDBOX"
        self.classification = classification or "UNKNOWN"
        self.decision = decision or "SANDBOX"
        self.risk_score = risk_score
        self.reasons = list(reasons) if reasons is not None else []
        self.pages = list(pages) if pages is not None else []
        self.traps_triggered = list(traps_triggered) if traps_triggered is not None else []
        self.canaries_exposed = list(canaries_exposed) if canaries_exposed is not None else []
        self.event_ids = list(event_ids) if event_ids is not None else []
        self.request_window = list(request_window) if request_window is not None else []

    @property
    def window_asset_ratio(self) -> float:
        if not self.request_window:
            return self.asset_ratio
        w_static = sum(1 for req in self.request_window if req == "static")
        w_api = sum(1 for req in self.request_window if req == "api")
        return round(w_static / max(1, w_api), 4)

    @property
    def ip(self) -> str:
        """Alias for client_ip for Phase 0 compatibility."""
        return self.client_ip

    @ip.setter
    def ip(self, val: str) -> None:
        self.client_ip = val

    def record_request(self, ctx: RequestContext) -> None:
        """Update session state, counters, rolling asset ratio, and bounds."""
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.first_seen:
            self.first_seen = now
        self.last_seen = now
        self.request_count += 1

        # Synchronize latest client context
        self.client_ip = ctx.ip
        self.client_key = ctx.client_key
        self.user_agent = ctx.user_agent
        self.header_fp = ctx.header_fp
        if ctx.asn is not None:
            self.asn = ctx.asn
            self.asn_status = ctx.asn_status
        if ctx.ja3_hash is not None:
            self.ja3_hash = ctx.ja3_hash
            self.ja4_hash = ctx.ja4_hash
            self.tls_source = ctx.tls_source

        # Asset ratio counter updates (FR1.3)
        if ctx.is_static:
            self.static_count += 1
            if not self.locked_sandbox:
                self.ar_anomaly_streak = 0
            self.request_window.append("static")
        elif ctx.is_api:
            self.api_count += 1
            # Anomaly streak: consecutive API calls with AR ~= 0.0 (FR-2.4)
            if self.asset_ratio < 0.05 or self.static_count == 0:
                self.ar_anomaly_streak += 1
            self.request_window.append("api")
        else:
            self.request_window.append("doc")

        if len(self.request_window) > 50:
            self.request_window = self.request_window[-50:]

        self.asset_ratio = round(self.static_count / max(1, self.api_count), 4)

        from ..config import get_ar_anomaly_streak

        if self.ar_anomaly_streak >= get_ar_anomaly_streak():
            self.locked_sandbox = True
            self.state = "SANDBOX"
            self.decision = "SANDBOX"
            self.trust_score = 0.0

        if self.locked_sandbox:
            self.state = "SANDBOX"
            self.decision = "SANDBOX"
            self.trust_score = 0.0

        # Operational list bounded append
        if ctx.path not in self.pages:
            self.pages.append(ctx.path)
            if len(self.pages) > MAX_OPERATIONAL_LIST_LEN:
                self.pages = self.pages[-MAX_OPERATIONAL_LIST_LEN:]

    def add_trap_triggered(self, path: str) -> None:
        """Record triggered trap path within bounded list."""
        if path not in self.traps_triggered:
            self.traps_triggered.append(path)
            if len(self.traps_triggered) > MAX_OPERATIONAL_LIST_LEN:
                self.traps_triggered = self.traps_triggered[-MAX_OPERATIONAL_LIST_LEN:]

    def add_canary_exposed(self, canary_id: str) -> None:
        """Record exposed canary token within bounded list."""
        if canary_id not in self.canaries_exposed:
            self.canaries_exposed.append(canary_id)
            if len(self.canaries_exposed) > MAX_OPERATIONAL_LIST_LEN:
                self.canaries_exposed = self.canaries_exposed[-MAX_OPERATIONAL_LIST_LEN:]

    def add_event_id(self, event_id: str) -> None:
        """Record processed event ID within bounded list."""
        if event_id not in self.event_ids:
            self.event_ids.append(event_id)
            if len(self.event_ids) > MAX_OPERATIONAL_LIST_LEN:
                self.event_ids = self.event_ids[-MAX_OPERATIONAL_LIST_LEN:]

    def add_reasons(self, reasons: list[str]) -> None:
        """Record decision reasons within bounded list."""
        for r in reasons:
            if r not in self.reasons:
                self.reasons.append(r)
        if len(self.reasons) > MAX_OPERATIONAL_LIST_LEN:
            self.reasons = self.reasons[-MAX_OPERATIONAL_LIST_LEN:]

    def to_snapshot(self) -> dict[str, Any]:
        """Produce an immutable snapshot dictionary for background persistence."""
        return {
            "session_id": self.session_id,
            "client_key": self.client_key,
            "client_ip": self.client_ip,
            "asn": self.asn,
            "asn_status": self.asn_status,
            "ja3_hash": self.ja3_hash,
            "ja4_hash": self.ja4_hash,
            "tls_source": self.tls_source,
            "user_agent": self.user_agent,
            "header_fp": self.header_fp,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "request_count": self.request_count,
            "static_count": self.static_count,
            "api_count": self.api_count,
            "asset_ratio": self.asset_ratio,
            "trust_score": self.trust_score,
            "ar_anomaly_streak": self.ar_anomaly_streak,
            "locked_sandbox": 1 if self.locked_sandbox else 0,
            "ar_classifier_decision": self.ar_classifier_decision,
            "confidence_score": self.confidence_score,
            "router_decision": self.router_decision,
            "state": self.state,
            "classification": self.classification,
            "decision": self.decision,
            "risk_score": self.risk_score,
            "reasons": list(self.reasons),
            "pages": list(self.pages),
            "traps_triggered": list(self.traps_triggered),
            "canaries_exposed": list(self.canaries_exposed),
            "event_ids": list(self.event_ids),
            "request_window": list(self.request_window),
        }

    def to_dict(self) -> dict[str, Any]:
        """Produce dictionary snapshot for store compatibility."""
        return self.to_snapshot()


class SessionsManager:
    """In-memory session manager with persistent store fallback."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, ctx: RequestContext) -> Session:
        # Deterministic opaque server-side session hash (PRD FR1.2)
        # hashlib.sha256(f"{ip}|{user_agent}|{ja3_hash}".encode()).hexdigest()[:16]
        sid_input = f"{ctx.ip}|{ctx.user_agent}|{ctx.ja3_hash}".encode("utf-8")
        sid = hashlib.sha256(sid_input).hexdigest()[:16]

        if sid not in self._sessions:
            # Check store to restore durable state across restarts
            stored: Any | None = None
            try:
                from ..store.sessions import get_session

                stored = get_session(sid)
            except Exception as exc:
                logger.debug("Could not restore session %s from store: %s", sid, exc)

            if stored is not None:
                # Instantiate and store authentic sb.edge.session.Session carrying over stored state
                # and updating with ctx properties (prevents TypeError on record_request and ensures to_snapshot exists)
                self._sessions[sid] = Session(
                    session_id=sid,
                    client_key=ctx.client_key or getattr(stored, "client_key", ""),
                    client_ip=ctx.ip or getattr(stored, "client_ip", "") or getattr(stored, "ip", ""),
                    asn=ctx.asn if ctx.asn is not None else getattr(stored, "asn", None),
                    asn_status=ctx.asn_status if ctx.asn is not None else getattr(stored, "asn_status", "unavailable"),
                    ja3_hash=ctx.ja3_hash if ctx.ja3_hash is not None else getattr(stored, "ja3_hash", None),
                    ja4_hash=ctx.ja4_hash if ctx.ja4_hash is not None else getattr(stored, "ja4_hash", None),
                    tls_source=ctx.tls_source if ctx.ja3_hash is not None else getattr(stored, "tls_source", "none"),
                    user_agent=ctx.user_agent or getattr(stored, "user_agent", ""),
                    header_fp=ctx.header_fp or getattr(stored, "header_fp", ""),
                    first_seen=getattr(stored, "first_seen", ""),
                    last_seen=getattr(stored, "last_seen", ""),
                    request_count=getattr(stored, "request_count", 0),
                    static_count=getattr(stored, "static_count", 0),
                    api_count=getattr(stored, "api_count", 0),
                    asset_ratio=getattr(stored, "asset_ratio", 0.0),
                    trust_score=getattr(stored, "trust_score", 0.0),
                    ar_anomaly_streak=getattr(stored, "ar_anomaly_streak", 0),
                    locked_sandbox=bool(getattr(stored, "locked_sandbox", False)),
                    ar_classifier_decision=getattr(stored, "ar_classifier_decision", None),
                    confidence_score=getattr(stored, "confidence_score", None),
                    router_decision=getattr(stored, "router_decision", None),
                    state=getattr(stored, "state", "SANDBOX"),
                    classification=getattr(stored, "classification", "UNKNOWN"),
                    decision=getattr(stored, "decision", "SANDBOX"),
                    risk_score=getattr(stored, "risk_score", 0),
                    reasons=getattr(stored, "reasons", []),
                    pages=getattr(stored, "pages", []),
                    traps_triggered=getattr(stored, "traps_triggered", []),
                    canaries_exposed=getattr(stored, "canaries_exposed", []),
                    event_ids=getattr(stored, "event_ids", []),
                    request_window=getattr(stored, "request_window", []),
                )
            else:
                self._sessions[sid] = Session(
                    session_id=sid,
                    client_key=ctx.client_key,
                    client_ip=ctx.ip,
                    asn=ctx.asn,
                    asn_status=ctx.asn_status,
                    ja3_hash=ctx.ja3_hash,
                    ja4_hash=ctx.ja4_hash,
                    tls_source=ctx.tls_source,
                    user_agent=ctx.user_agent,
                    header_fp=ctx.header_fp,
                )
        return self._sessions[sid]

    def get(self, sid: str) -> Session | None:
        """Retrieve active session by session_id."""
        return self._sessions.get(sid)

    def reset(self) -> None:
        """Reset in-memory cache."""
        self._sessions.clear()


sessions = SessionsManager()
