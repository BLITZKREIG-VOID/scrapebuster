"""ScapeBusters Layer 3 trap / honeypot package."""

from sb.trap.injector import ScapeBustersTrapHooks


def install() -> ScapeBustersTrapHooks:
    """Install ScapeBusters TrapHooks into hooks and pipeline registries."""
    import sb.edge.pipeline
    import sb.hooks

    instance = ScapeBustersTrapHooks()
    sb.hooks.trap_hooks = instance
    sb.edge.pipeline.trap_hooks = instance
    sb.hooks.register_reset_hook(instance.reset)
    return instance
