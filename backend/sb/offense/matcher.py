"""Offense matcher alias for layer3 classification."""

from sb.offense.layer3 import (
    TrapHit,
    classify_request,
    list_trap_hits,
    match_trap,
)

__all__ = [
    "TrapHit",
    "classify_request",
    "list_trap_hits",
    "match_trap",
]
