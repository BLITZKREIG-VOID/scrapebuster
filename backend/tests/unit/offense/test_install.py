"""install() wiring the demo reset relies on."""

import sb.edge.pipeline
import sb.hooks
from sb.offense import install
from sb.provenance import dataset, rag


def test_install_registers_provenance_reset_once_and_it_clears_caches(monkeypatch):
    monkeypatch.setattr(sb.hooks, "_reset_hooks", [])

    install()
    install()

    provenance_hooks = [h for h in sb.hooks._reset_hooks if h.__module__.startswith("sb.provenance")]
    assert len(provenance_hooks) == 1

    monkeypatch.setitem(rag._INDEX_CACHE, "DS-x", object())
    monkeypatch.setitem(dataset._RECORDS_CACHE, "DS-x", [])
    sb.hooks.run_reset_hooks()
    assert "DS-x" not in rag._INDEX_CACHE
    assert "DS-x" not in dataset._RECORDS_CACHE
