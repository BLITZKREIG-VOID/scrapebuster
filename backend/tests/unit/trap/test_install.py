"""install() wiring the demo reset (§21 step 4) relies on."""

import sb.edge.pipeline
import sb.hooks
from sb.provenance import dataset, rag
from sb.trap import install


def test_install_registers_provenance_reset_once_and_it_clears_caches(monkeypatch):
    monkeypatch.setattr(sb.hooks, "_reset_hooks", [])
    monkeypatch.setattr(sb.hooks, "trap_hooks", sb.hooks.trap_hooks)
    monkeypatch.setattr(sb.edge.pipeline, "trap_hooks", sb.edge.pipeline.trap_hooks)

    install()
    install()

    provenance_hooks = [h for h in sb.hooks._reset_hooks if h.__module__.startswith("sb.provenance")]
    assert len(provenance_hooks) == 1
    assert type(sb.hooks.trap_hooks).__name__ != "NoOpTrapHooks"

    monkeypatch.setitem(rag._INDEX_CACHE, "DS-x", object())
    monkeypatch.setitem(dataset._RECORDS_CACHE, "DS-x", [])
    sb.hooks.run_reset_hooks()
    assert "DS-x" not in rag._INDEX_CACHE
    assert "DS-x" not in dataset._RECORDS_CACHE
