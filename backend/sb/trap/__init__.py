"""ScapeBusters Layer 3 trap / honeypot package."""

from sb.trap.injector import ScapeBustersTrapHooks


def install() -> ScapeBustersTrapHooks:
    """Install ScapeBusters TrapHooks and register the trap + provenance reset hooks.

    ``sb.main`` makes this single call at startup, so the provenance in-memory reset
    (BM25 index cache + dataset registry) is registered here too; the demo reset
    (§21 step 4) requires a hook owned by ``sb.provenance``.
    """
    import sb.edge.pipeline
    import sb.hooks
    import sb.provenance

    instance = ScapeBustersTrapHooks()
    sb.hooks.trap_hooks = instance
    sb.edge.pipeline.trap_hooks = instance
    sb.hooks.register_reset_hook(instance.reset)
    if sb.provenance.reset not in sb.hooks._reset_hooks:
        sb.hooks.register_reset_hook(sb.provenance.reset)
    return instance
