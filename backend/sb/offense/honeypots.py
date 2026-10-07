"""Honeypot definitions, metadata, and configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Honeypot:
    trap_id: str
    trap_type: str
    mechanism: str
    paths: tuple[str, ...] = ()


def get_configured_trap_paths() -> list[str]:
    """Retrieve configured trap paths from env var SB_TRAP_PATHS or sb.config.

    Defaults to empty list, avoiding default claims on customer origin paths.
    """
    from sb.config import get_configured_trap_paths as _get_paths

    return _get_paths()


def get_configured_trap_api_path() -> str:
    """Retrieve configured decoy API path from env var SB_TRAP_API_PATH or sb.config.

    Defaults to empty string.
    """
    from sb.config import get_configured_trap_api_path as _get_api

    return _get_api()


def get_hidden_link_html() -> str:
    """Generate hidden link HTML using first configured trap path if present, else empty."""
    paths = get_configured_trap_paths()
    if not paths:
        return ""
    target_path = paths[0]
    return f'<a href="{target_path}" style="display:none" aria-hidden="true" tabindex="-1" rel="nofollow">Resource Reference</a>'


def get_honeypots() -> dict[str, Honeypot]:
    """Return active honeypots based on current configuration."""
    trap_paths = tuple(get_configured_trap_paths())
    decoy_api = get_configured_trap_api_path()
    pots: dict[str, Honeypot] = {}
    if trap_paths:
        pots["TRAP-PATH-01"] = Honeypot(
            trap_id="TRAP-PATH-01",
            trap_type="trap_path",
            mechanism="configured trap path",
            paths=trap_paths,
        )
    if decoy_api:
        pots["TRAP-DECOY-01"] = Honeypot(
            trap_id="TRAP-DECOY-01",
            trap_type="decoy_api",
            mechanism="configured decoy API",
            paths=(decoy_api,),
        )
    return pots
