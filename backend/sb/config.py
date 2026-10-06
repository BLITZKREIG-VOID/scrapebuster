import json
import logging
import os

logger = logging.getLogger("sb.config")

# Edge and upstream configuration (PRD v3.0 PR-2)
SB_UPSTREAM_ORIGIN = (
    os.getenv("SB_UPSTREAM_ORIGIN")
    or os.getenv("UPSTREAM_ORIGIN")
    or os.getenv("SB_ORIGIN_URL")
    or ""
)
SB_ORIGIN_URL = SB_UPSTREAM_ORIGIN
SB_PUBLIC_BASE_URL = os.getenv("SB_PUBLIC_BASE_URL", "")

# Persistence and runtime directories
SB_DB_PATH = os.getenv("SB_DB_PATH", "backend/sb.db")
SB_RUNTIME_DIR = os.getenv("SB_RUNTIME_DIR", "data/runtime")


def _parse_trap_paths(val: str | None) -> list[str]:
    if not val:
        return []
    val = val.strip()
    if val.startswith("["):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(p).strip() for p in parsed if str(p).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    return [p.strip() for p in val.split(",") if p.strip()]


# Decoy / trap route configuration
SB_TRAP_PATHS = _parse_trap_paths(os.getenv("SB_TRAP_PATHS"))
SB_TRAP_API_PATH = os.getenv("SB_TRAP_API_PATH", "")

# Mutation mode (Phase0 defaults to always until Phase2 adaptive)
SB_MUTATION_MODE = os.getenv("SB_MUTATION_MODE", "always")
