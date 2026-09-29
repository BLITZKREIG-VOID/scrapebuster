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
    l2_score: int = 0
    layer_path: list[dict[str, Any]] = field(default_factory=list)
    
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
