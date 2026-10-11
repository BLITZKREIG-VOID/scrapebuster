from __future__ import annotations

import sqlite3
from typing import Any, Protocol


class OffenseHooks(Protocol):
    def classify_request(
        self,
        ctx: Any,
        session: Any,
        conn: sqlite3.Connection | None = None,
    ) -> Any | None: ...

    def handle_decoy(
        self,
        ctx: Any,
        session: Any,
        conn: sqlite3.Connection | None = None,
    ) -> Any | None: ...

    def transform_response(
        self,
        ctx: Any,
        session: Any,
        upstream: Any,
        conn: sqlite3.Connection | None = None,
    ) -> bytes: ...

    def extract_canary_ids(self, body: bytes) -> tuple[str, ...]: ...

    def reset(self) -> None: ...


class NoOpOffenseHooks:
    def classify_request(
        self,
        ctx: Any,
        session: Any,
        conn: sqlite3.Connection | None = None,
    ) -> Any | None:
        return None

    def handle_decoy(
        self,
        ctx: Any,
        session: Any,
        conn: sqlite3.Connection | None = None,
    ) -> Any | None:
        return None

    def transform_response(
        self,
        ctx: Any,
        session: Any,
        upstream: Any,
        conn: sqlite3.Connection | None = None,
    ) -> bytes:
        content = getattr(upstream, "content", b"")
        return content if isinstance(content, bytes) else bytes(content or b"")

    def extract_canary_ids(self, body: bytes) -> tuple[str, ...]:
        return ()

    def reset(self) -> None:
        pass


offense_hooks: OffenseHooks = NoOpOffenseHooks()


def extract_canary_ids(body: bytes) -> tuple[str, ...]:
    """Extract canary IDs from response bytes using active offense hook or canary registry."""
    if hasattr(offense_hooks, "extract_canary_ids"):
        res = offense_hooks.extract_canary_ids(body)
        if res:
            return res
    from sb.canary._defs import extract_canary_ids as _extract

    return _extract(body)


# Registry for components that need a reset hook during demo/reset
_reset_hooks: list[Any] = []


def register_reset_hook(hook: Any) -> None:
    _reset_hooks.append(hook)


def run_reset_hooks() -> None:
    for hook in _reset_hooks:
        hook()
