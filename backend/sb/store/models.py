"""Store data models for ScrapeBuster Phase 1.

Defines the authoritative Session model with Phase 1 durable 7-tuple:
  (session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen)
and TrafficEventRecord for operational projections and telemetry payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Session:
    """Authoritative server-side session model for ScrapeBuster Phase 1.

    Durable 7-tuple: (session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen).
    Asset ratio formula: asset_ratio = static_count / max(1, api_count).
    Documents are not counted as API unless explicit is_api classification is provided.
    """

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
    state: str = "SANDBOX"
    classification: str = "UNKNOWN"
    decision: str = "SANDBOX"
    risk_score: int = 0
    reasons: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    traps_triggered: list[str] = field(default_factory=list)
    canaries_exposed: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)

    def __init__(
        self,
        session_id: str,
        client_key: str = "",
        client_ip: str = "",
        ip: str = "",
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
        asset_ratio: float | None = None,
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
        offenses_triggered: list[str] | None = None,
        canaries_exposed: list[str] | None = None,
        event_ids: list[str] | None = None,
        **extra: Any,
    ):
        self.session_id = str(session_id)
        self.client_key = str(client_key or "")
        # Resolve client_ip and legacy ip alias
        resolved_ip = str(client_ip or ip or "")
        self.client_ip = resolved_ip

        # Ensure ASN is int | None
        if asn is not None:
            try:
                self.asn = int(asn)
            except (ValueError, TypeError):
                self.asn = None
        else:
            self.asn = None

        self.asn_status = str(asn_status or "unavailable")
        self.ja3_hash = str(ja3_hash) if ja3_hash else None
        self.ja4_hash = str(ja4_hash) if ja4_hash else None
        self.tls_source = str(tls_source or "none")
        self.user_agent = str(user_agent or "")
        self.header_fp = str(header_fp or "")
        self.first_seen = str(first_seen or "")
        self.last_seen = str(last_seen or "")
        self.request_count = int(request_count or 0)
        self.static_count = int(static_count or 0)
        self.api_count = int(api_count or 0)

        if asset_ratio is not None:
            try:
                self.asset_ratio = round(float(asset_ratio), 4)
            except (ValueError, TypeError):
                self.asset_ratio = self.compute_asset_ratio()
        else:
            self.asset_ratio = self.compute_asset_ratio()

        self.trust_score = float(trust_score or 0.0)
        self.ar_anomaly_streak = int(ar_anomaly_streak or 0)
        self.locked_sandbox = bool(locked_sandbox)
        self.ar_classifier_decision = ar_classifier_decision
        self.confidence_score = confidence_score
        self.router_decision = router_decision
        self.state = str(state or "SANDBOX")
        self.classification = str(classification or "UNKNOWN")
        self.decision = str(decision or "SANDBOX")
        self.risk_score = int(risk_score or 0)
        self.reasons = list(reasons) if reasons is not None else []
        self.pages = list(pages) if pages is not None else []
        
        # Merge traps_triggered and legacy offenses_triggered
        traps = traps_triggered if traps_triggered is not None else offenses_triggered
        self.traps_triggered = list(traps) if traps is not None else []
        self.canaries_exposed = list(canaries_exposed) if canaries_exposed is not None else []
        self.event_ids = list(event_ids) if event_ids is not None else []

    @property
    def ip(self) -> str:
        """Backwards compatibility alias for client_ip."""
        return self.client_ip

    @ip.setter
    def ip(self, value: str) -> None:
        self.client_ip = str(value or "")

    @property
    def offenses_triggered(self) -> list[str]:
        """Backwards compatibility alias for traps_triggered."""
        return self.traps_triggered

    @offenses_triggered.setter
    def offenses_triggered(self, value: list[str]) -> None:
        self.traps_triggered = list(value)

    @property
    def seven_tuple(self) -> tuple[str, str, int | None, str | None, float, str, str]:
        """Authoritative durable Session 7-tuple per PRD FR1.2:
        (session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen)
        """
        return (
            self.session_id,
            self.client_ip,
            self.asn,
            self.ja3_hash,
            self.asset_ratio,
            self.first_seen,
            self.last_seen,
        )

    def compute_asset_ratio(self) -> float:
        """Calculate asset_ratio = static_count / max(1, api_count).
        
        Do not count HTML documents or generic requests as API unless explicit
        is_api classification is recorded.
        """
        denom = max(1, self.api_count)
        return round(float(self.static_count) / denom, 4)

    def record_request(
        self,
        *,
        is_static: bool = False,
        is_api: bool = False,
        is_document: bool = False,
        path: str = "",
        event_id: str = "",
        timestamp: str | None = None,
    ) -> None:
        """Update request counters, timestamps, and rolling asset ratio."""
        now_ts = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.first_seen:
            self.first_seen = now_ts
        self.last_seen = now_ts
        self.request_count += 1

        if is_static:
            self.static_count += 1
        elif is_api:
            # Only count as API if explicit is_api
            self.api_count += 1
        # Documents are intentionally not counted as API unless is_api is explicit

        self.asset_ratio = self.compute_asset_ratio()

        if path and path not in self.pages:
            self.pages.append(path)
        if event_id and event_id not in self.event_ids:
            self.event_ids.append(event_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to serializable dictionary."""
        return {
            "session_id": self.session_id,
            "client_key": self.client_key,
            "client_ip": self.client_ip,
            "ip": self.client_ip,
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
        }

    def model_dump(self) -> dict[str, Any]:
        """Pydantic-compatible serialization helper."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Create a Session instance from a dictionary or database row mapping."""
        return cls(
            session_id=data.get("session_id", ""),
            client_key=data.get("client_key", ""),
            client_ip=data.get("client_ip", data.get("ip", "")),
            ip=data.get("ip", data.get("client_ip", "")),
            asn=data.get("asn"),
            asn_status=data.get("asn_status", "unavailable"),
            ja3_hash=data.get("ja3_hash"),
            ja4_hash=data.get("ja4_hash"),
            tls_source=data.get("tls_source", "none"),
            user_agent=data.get("user_agent", ""),
            header_fp=data.get("header_fp", ""),
            first_seen=data.get("first_seen", ""),
            last_seen=data.get("last_seen", ""),
            request_count=data.get("request_count", 0),
            static_count=data.get("static_count", 0),
            api_count=data.get("api_count", 0),
            asset_ratio=data.get("asset_ratio"),
            trust_score=data.get("trust_score", 0.0),
            ar_anomaly_streak=data.get("ar_anomaly_streak", 0),
            locked_sandbox=bool(data.get("locked_sandbox", False)),
            ar_classifier_decision=data.get("ar_classifier_decision"),
            confidence_score=data.get("confidence_score"),
            router_decision=data.get("router_decision"),
            state=data.get("state", "SANDBOX"),
            classification=data.get("classification", "UNKNOWN"),
            decision=data.get("decision", "SANDBOX"),
            risk_score=data.get("risk_score", 0),
            reasons=data.get("reasons"),
            pages=data.get("pages"),
            traps_triggered=data.get("traps_triggered"),
            offenses_triggered=data.get("offenses_triggered"),
            canaries_exposed=data.get("canaries_exposed"),
            event_ids=data.get("event_ids"),
        )


@dataclass
class TrafficEventRecord:
    """Authoritative traffic event record model for ScrapeBuster Phase 1."""

    event_id: str
    ts: str
    session_id: str
    client_key: str
    client_ip: str
    method: str
    path: str
    status_code: int
    user_agent: str
    header_fp: str
    seq: int | None = None
    ip: str = ""
    asn: int | None = None
    asn_status: str = "unavailable"
    ja3_hash: str | None = None
    ja4_hash: str | None = None
    tls_source: str = "none"
    http_version: str = "HTTP/1.1"
    header_order: list[str] = field(default_factory=list)
    stage: str = "offense"
    layer: str = "ORIGIN"
    decision: str = "SANDBOX"
    risk_score: int = 0
    reasons: list[str] = field(default_factory=list)
    canary_ids: list[str] = field(default_factory=list)

    def __init__(
        self,
        event_id: str,
        ts: str,
        session_id: str,
        client_key: str,
        client_ip: str = "",
        ip: str = "",
        method: str = "GET",
        path: str = "/",
        status_code: int = 200,
        user_agent: str = "",
        header_fp: str = "",
        seq: int | None = None,
        asn: int | None = None,
        asn_status: str = "unavailable",
        ja3_hash: str | None = None,
        ja4_hash: str | None = None,
        tls_source: str = "none",
        http_version: str = "HTTP/1.1",
        header_order: list[str] | None = None,
        stage: str = "offense",
        layer: str = "ORIGIN",
        decision: str = "SANDBOX",
        risk_score: int = 0,
        reasons: list[str] | None = None,
        canary_ids: list[str] | None = None,
        route_class: str = "unknown",
        **extra: Any,
    ):
        self.seq = int(seq) if seq is not None else None
        self.event_id = str(event_id)
        self.ts = str(ts)
        self.session_id = str(session_id)
        self.client_key = str(client_key or "")
        self.client_ip = str(client_ip or ip or "")
        self.ip = self.client_ip

        if asn is not None:
            try:
                self.asn = int(asn)
            except (ValueError, TypeError):
                self.asn = None
        else:
            self.asn = None

        self.asn_status = str(asn_status or "unavailable")
        self.ja3_hash = str(ja3_hash) if ja3_hash else None
        self.ja4_hash = str(ja4_hash) if ja4_hash else None
        self.tls_source = str(tls_source or "none")
        self.http_version = str(http_version or "HTTP/1.1")
        self.header_order = list(header_order) if header_order is not None else []
        self.header_fp = str(header_fp or "")
        self.method = str(method or "GET")
        self.path = str(path or "/")
        self.status_code = int(status_code or 200)
        self.user_agent = str(user_agent or "")
        self.stage = str(stage or "offense")
        self.layer = str(layer or "ORIGIN")
        self.decision = str(decision or "SANDBOX")
        self.risk_score = int(risk_score or 0)
        self.reasons = list(reasons) if reasons is not None else []
        self.canary_ids = list(canary_ids) if canary_ids is not None else []
        self.route_class = str(route_class or "unknown")

    def to_dict(self) -> dict[str, Any]:
        """Convert event record to dictionary."""
        return {
            "seq": self.seq,
            "event_id": self.event_id,
            "ts": self.ts,
            "session_id": self.session_id,
            "client_key": self.client_key,
            "client_ip": self.client_ip,
            "ip": self.client_ip,
            "asn": self.asn,
            "asn_status": self.asn_status,
            "ja3_hash": self.ja3_hash,
            "ja4_hash": self.ja4_hash,
            "tls_source": self.tls_source,
            "http_version": self.http_version,
            "header_order": list(self.header_order),
            "header_fp": self.header_fp,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "user_agent": self.user_agent,
            "stage": self.stage,
            "layer": self.layer,
            "decision": self.decision,
            "risk_score": self.risk_score,
            "reasons": list(self.reasons),
            "canary_ids": list(self.canary_ids),
            "route_class": self.route_class,
        }

    def model_dump(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrafficEventRecord:
        return cls(
            seq=data.get("seq"),
            event_id=data.get("event_id", ""),
            ts=data.get("ts", ""),
            session_id=data.get("session_id", ""),
            client_key=data.get("client_key", ""),
            client_ip=data.get("client_ip", data.get("ip", "")),
            ip=data.get("ip", data.get("client_ip", "")),
            asn=data.get("asn"),
            asn_status=data.get("asn_status", "unavailable"),
            ja3_hash=data.get("ja3_hash"),
            ja4_hash=data.get("ja4_hash"),
            tls_source=data.get("tls_source", "none"),
            http_version=data.get("http_version", "HTTP/1.1"),
            header_order=data.get("header_order"),
            header_fp=data.get("header_fp", ""),
            method=data.get("method", "GET"),
            path=data.get("path", "/"),
            status_code=data.get("status_code", 200),
            user_agent=data.get("user_agent", ""),
            stage=data.get("stage", "offense"),
            layer=data.get("layer", "ORIGIN"),
            decision=data.get("decision", "SANDBOX"),
            risk_score=data.get("risk_score", 0),
            reasons=data.get("reasons"),
            canary_ids=data.get("canary_ids"),
        )
