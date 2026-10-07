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


def get_configured_trap_paths() -> list[str]:
    """Return runtime configured trap paths from environment or module default."""
    val = os.getenv("SB_TRAP_PATHS")
    if val is not None:
        try:
            return _parse_trap_paths(val)
        except Exception as exc:
            logger.warning("Failed to parse live SB_TRAP_PATHS ('%s'): %s; defaulting to []", val, exc)
            return []
    return list(SB_TRAP_PATHS)


def get_configured_trap_api_path() -> str:
    """Return runtime configured trap API path from environment or module default."""
    val = os.getenv("SB_TRAP_API_PATH")
    if val is not None:
        return val.strip()
    return SB_TRAP_API_PATH.strip() if SB_TRAP_API_PATH else ""


def is_segment_match(path: str, prefix: str) -> bool:
    """Segment-safe match: exact or subpath under boundary (e.g. /trap and /trap/sub, not /trap-other)."""
    if not path or not prefix:
        return False
    norm_path = path.rstrip("/") if path != "/" else "/"
    norm_prefix = prefix.rstrip("/") if prefix != "/" else "/"
    if norm_path == norm_prefix:
        return True
    pfx = norm_prefix if norm_prefix.endswith("/") else norm_prefix + "/"
    return norm_path.startswith(pfx)


def is_trap_path(path: str, candidates: list[str] | None = None) -> bool:
    """Check if the path matches runtime-configured trap paths.

    Shared canonical runtime-config predicate (Phase 0 Hard Rule).
    Segment-safe: matches exact path or subpath under segment boundary (e.g. /trap and /trap/sub),
    but never partial prefix matches without segment boundary (e.g. /trap-other).
    Defaults to empty (no hardcoded trap paths).
    """
    try:
        if candidates is None:
            trap_paths = get_configured_trap_paths()
            api_path = get_configured_trap_api_path()
            if not trap_paths and not api_path:
                return False
            check_list: list[str] = list(trap_paths)
            if api_path:
                check_list.append(api_path)
        else:
            check_list = candidates

        for tp in check_list:
            if is_segment_match(path, tp):
                return True
        return False
    except Exception as exc:
        logger.warning("Error evaluating is_trap_path for %s: %s", path, exc)
        return False


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
