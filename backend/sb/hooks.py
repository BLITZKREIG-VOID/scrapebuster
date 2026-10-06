from __future__ import annotations

from typing import Any, Protocol


class OffenseHooks(Protocol):
    def classify_request(self, ctx: Any, session: Any) -> Any | None: ...
    def handle_decoy(self, ctx: Any, session: Any) -> Any | None: ...
    def transform_response(self, ctx: Any, session: Any, upstream: Any) -> bytes: ...
    def reset(self) -> None: ...


# Backward-compatibility alias for edge pipeline and tests during migration
TrapHooks = OffenseHooks


class NoOpOffenseHooks:
    def classify_request(self, ctx: Any, session: Any) -> Any | None:
        return None

    def handle_decoy(self, ctx: Any, session: Any) -> Any | None:
        return None

    def transform_response(self, ctx: Any, session: Any, upstream: Any) -> bytes:
        content = getattr(upstream, "content", b"")
        return content if isinstance(content, bytes) else bytes(content or b"")

    def reset(self) -> None:
        pass


NoOpTrapHooks = NoOpOffenseHooks

offense_hooks: OffenseHooks = NoOpOffenseHooks()
trap_hooks: OffenseHooks = offense_hooks

# Registry for components that need a reset hook during demo/reset
_reset_hooks: list[Any] = []


def register_reset_hook(hook: Any) -> None:
    _reset_hooks.append(hook)


def run_reset_hooks() -> None:
    for hook in _reset_hooks:
        hook()
