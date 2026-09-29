from typing import Any, Protocol


class TrapHooks(Protocol):
    def classify_request(self, ctx: Any, session: Any) -> Any | None: ...
    def handle_decoy(self, ctx: Any, session: Any) -> Any | None: ...
    def transform_response(self, ctx: Any, session: Any, upstream: Any) -> bytes: ...
    def reset(self) -> None: ...

class NoOpTrapHooks:
    def classify_request(self, ctx: Any, session: Any) -> Any | None:
        return None
    def handle_decoy(self, ctx: Any, session: Any) -> Any | None:
        return None
    def transform_response(self, ctx: Any, session: Any, upstream: Any) -> bytes:
        return upstream.content
    def reset(self) -> None:
        pass

trap_hooks: TrapHooks = NoOpTrapHooks()

# Registry for components that need a reset hook during `demo/reset`
_reset_hooks = []
def register_reset_hook(hook):
    _reset_hooks.append(hook)

def run_reset_hooks():
    for hook in _reset_hooks:
        hook()
