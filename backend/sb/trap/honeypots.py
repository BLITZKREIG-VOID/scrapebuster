"""Honeypot definitions, metadata, and constants."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Honeypot:
    trap_id: str
    trap_type: str
    mechanism: str
    paths: tuple[str, ...] = ()


HIDDEN_LINK_PATH = "/docs/archive/legacy-index"
ROBOTS_PREFIX = "/internal/"
DECOY_API_PATH = "/internal/api/v3/quasar-reconcile"
L2_BAND = (40, 69)
HIDDEN_LINK_HTML = '<a href="/docs/archive/legacy-index" style="display:none" aria-hidden="true" tabindex="-1" rel="nofollow">Archive index</a>'

HONEYPOTS: dict[str, Honeypot] = {
    "TRAP-LINK-01": Honeypot(
        trap_id="TRAP-LINK-01",
        trap_type="hidden_link",
        mechanism="hidden honeypot link",
        paths=(HIDDEN_LINK_PATH,),
    ),
    "TRAP-ROBOTS-01": Honeypot(
        trap_id="TRAP-ROBOTS-01",
        trap_type="robots_disallowed",
        mechanism="robots-disallowed area",
        paths=(ROBOTS_PREFIX,),
    ),
    "TRAP-DECOY-01": Honeypot(
        trap_id="TRAP-DECOY-01",
        trap_type="decoy_api",
        mechanism="decoy API",
        paths=(DECOY_API_PATH,),
    ),
    "TRAP-BAND-L2": Honeypot(
        trap_id="TRAP-BAND-L2",
        trap_type="l2_band",
        mechanism="L2 suspicious band",
        paths=(),
    ),
}
