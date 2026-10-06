"""ScapeBusters offense and active defense package."""

from __future__ import annotations

from sb.offense.injector import (
    ScapeBustersOffenseHooks,
    ScapeBustersTrapHooks,
)

__all__ = [
    "ScapeBustersOffenseHooks",
    "ScapeBustersTrapHooks",
    "install",
]


def install() -> ScapeBustersOffenseHooks:
    """Install ScapeBusters OffenseHooks and register reset hooks.

    sb.main invokes this at startup to bind offense hooks into the request pipeline.
    """
    import sb.hooks

    instance = ScapeBustersOffenseHooks()
    sb.hooks.offense_hooks = instance
    sb.hooks.trap_hooks = instance
    sb.hooks.register_reset_hook(instance.reset)

    try:
        import sb.edge.pipeline
        sb.edge.pipeline.offense_hooks = instance
        sb.edge.pipeline.trap_hooks = instance
    except (ImportError, AttributeError):
        pass

    try:
        import sb.provenance
        if hasattr(sb.provenance, "reset") and sb.provenance.reset not in sb.hooks._reset_hooks:
            sb.hooks.register_reset_hook(sb.provenance.reset)
    except (ImportError, AttributeError):
        pass

    return instance
