"""Edge session model and management for Phase0.

State is SANDBOX by default; old perimeter blocking-state fields and timers removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .context import RequestContext


@dataclass
class Session:
    session_id: str
    client_key: str = ""
    state: str = "SANDBOX"
    classification: str = "UNKNOWN"
    risk_score: int = 0
    reasons: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    ip: str = ""
    user_agent: str = ""
    header_fp: str = ""
    first_seen: str = ""
    last_seen: str = ""
    request_count: int = 0
    pages: list[str] = field(default_factory=list)
    traps_triggered: list[str] = field(default_factory=list)
    canaries_exposed: list[str] = field(default_factory=list)

    def __init__(
        self,
        session_id: str,
        client_key: str = "",
        state: str = "SANDBOX",
        classification: str = "UNKNOWN",
        risk_score: int = 0,
        reasons: list[str] | None = None,
        event_ids: list[str] | None = None,
        ip: str = "",
        user_agent: str = "",
        header_fp: str = "",
        first_seen: str = "",
        last_seen: str = "",
        request_count: int = 0,
        pages: list[str] | None = None,
        traps_triggered: list[str] | None = None,
        canaries_exposed: list[str] | None = None,
        **extra: Any,
    ):
        self.session_id = session_id
        self.client_key = client_key
        self.state = state or "SANDBOX"
        self.classification = classification
        self.risk_score = risk_score
        self.reasons = reasons if reasons is not None else []
        self.event_ids = event_ids if event_ids is not None else []
        self.ip = ip
        self.user_agent = user_agent
        self.header_fp = header_fp
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.request_count = request_count
        self.pages = pages if pages is not None else []
        self.traps_triggered = traps_triggered if traps_triggered is not None else []
        self.canaries_exposed = canaries_exposed if canaries_exposed is not None else []

    def __getattr__(self, name: str) -> Any:
        # Graceful compatibility fallback for legacy store queries until W3 store merge
        if name in ("l1_score", "l2_score"):
            return 0
        if name in ("l1_reasons", "l2_signals", "layer_path"):
            return []
        if name == "block_until":
            return ""
        if name == "decision":
            return getattr(self, "state", "SANDBOX")
        raise AttributeError(f"'Session' object has no attribute '{name}'")


class SessionsManager:
    """In-memory session manager with persistent store fallback."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, ctx: RequestContext) -> Session:
        sid = f"ck-{ctx.client_key}"
        if sid not in self._sessions:
            from ..store.sessions import get_session

            self._sessions[sid] = get_session(sid) or Session(
                session_id=sid, client_key=ctx.client_key
            )
        return self._sessions[sid]

    def reset(self):
        self._sessions.clear()


sessions = SessionsManager()
