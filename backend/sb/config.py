import json
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger("sb.config")

# Canonical edge and upstream configuration (PRD v3.0 PR-2)
# No alias compatibility: strictly SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL
SB_UPSTREAM_ORIGIN = os.getenv("SB_UPSTREAM_ORIGIN", "")
SB_PUBLIC_BASE_URL = os.getenv("SB_PUBLIC_BASE_URL", "")

# Persistence and runtime directories
SB_DB_PATH = os.getenv("SB_DB_PATH", "backend/sb.db")
SB_RUNTIME_DIR = os.getenv("SB_RUNTIME_DIR", "data/runtime")


def _parse_trap_paths(val: str | None) -> list[str]:
    """Parse strict JSON list of trap paths; defaults to empty list."""
    if not val:
        return []
    val = val.strip()
    if not val:
        return []
    try:
        parsed = json.loads(val)
    except Exception as exc:
        raise ValueError(f"SB_TRAP_PATHS must be a valid JSON array of paths: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError(f"SB_TRAP_PATHS must be a JSON array of paths, got {type(parsed).__name__}")
    return [str(p).strip() for p in parsed if str(p).strip()]


# Decoy / trap route configuration (defaults empty; no hardcoded trap paths)
SB_TRAP_PATHS = _parse_trap_paths(os.getenv("SB_TRAP_PATHS"))
SB_TRAP_API_PATH = os.getenv("SB_TRAP_API_PATH", "")

# Mutation mode: Phase 0 is pure SANDBOX mutation on all eligible origin HTML/JSON.
# Passthrough escape removed; adaptive mode deferred to Phase 2.
SB_MUTATION_MODE = "always"


def validate_required_urls() -> None:
    """Enforce canonical SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL at application lifespan startup.

    Both must be valid HTTP(S) URLs with scheme and netloc.
    """
    upstream = os.getenv("SB_UPSTREAM_ORIGIN", SB_UPSTREAM_ORIGIN).strip()
    public_base = os.getenv("SB_PUBLIC_BASE_URL", SB_PUBLIC_BASE_URL).strip()

    if not upstream:
        raise ValueError("Required configuration SB_UPSTREAM_ORIGIN is missing or empty")
    if not public_base:
        raise ValueError("Required configuration SB_PUBLIC_BASE_URL is missing or empty")

    u_parsed = urlparse(upstream)
    if u_parsed.scheme not in ("http", "https") or not u_parsed.netloc:
        raise ValueError(f"SB_UPSTREAM_ORIGIN must be a valid HTTP(S) URL, got: {upstream!r}")

    p_parsed = urlparse(public_base)
    if p_parsed.scheme not in ("http", "https") or not p_parsed.netloc:
        raise ValueError(f"SB_PUBLIC_BASE_URL must be a valid HTTP(S) URL, got: {public_base!r}")
