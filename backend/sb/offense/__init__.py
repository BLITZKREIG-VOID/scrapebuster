"""ScapeBusters offense and active defense package."""

from __future__ import annotations

from sb.offense.injector import (
    ScapeBustersOffenseHooks,
    deterministic_fallback,
    inject_json_canary,
    insert_canary,
    insert_hidden_link,
    transform_response,
)

__all__ = [
    "ScapeBustersOffenseHooks",
    "deterministic_fallback",
    "inject_json_canary",
    "insert_canary",
    "insert_hidden_link",
    "transform_response",
    "install",
]


def install() -> ScapeBustersOffenseHooks:
    """Install ScapeBusters OffenseHooks and register reset hooks.

    sb.main invokes this at startup to bind offense hooks into the request pipeline.
    """
    import sb.hooks
    import sb.provenance

    instance = ScapeBustersOffenseHooks()
    sb.hooks.offense_hooks = instance
    sb.hooks.register_reset_hook(instance.reset)

    if hasattr(sb.provenance, "reset") and sb.provenance.reset not in sb.hooks._reset_hooks:
        sb.hooks.register_reset_hook(sb.provenance.reset)

    return instance
