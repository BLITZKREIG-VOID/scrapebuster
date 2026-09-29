from dataclasses import dataclass, field
from typing import Any

from .context import RequestContext


@dataclass
class Session:
    session_id: str
    client_key: str
    state: str = "NEW"
    classification: str = "UNKNOWN"
    l1_score: int = 0
    l1_reasons: list[str] = field(default_factory=list)
    l2_score: int = 0
    l2_signals: list[str] = field(default_factory=list)
    layer_path: list[dict[str, Any]] = field(default_factory=list)
    ip: str = ""
    user_agent: str = ""
    header_fp: str = ""
    first_seen: str = ""
    last_seen: str = ""
    request_count: int = 0
    pages: list[str] = field(default_factory=list)
    traps_triggered: list[str] = field(default_factory=list)
    canaries_exposed: list[str] = field(default_factory=list)
    def block_expired(self) -> bool:
        return False
        
    def mark_trapped(self, trap: Any):
        self.state = "TRAPPED"

class SessionsManager:
    def __init__(self):
        self._sessions = {}
        
    def get_or_create(self, ctx: RequestContext) -> Session:
        sid = f"ck-{ctx.client_key}"
        if sid not in self._sessions:
            self._sessions[sid] = Session(session_id=sid, client_key=ctx.client_key)
        return self._sessions[sid]
        
    def reset(self):
        self._sessions.clear()

sessions = SessionsManager()
