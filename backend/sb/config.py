import ipaddress
import json
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger("sb.config")

# Canonical edge and upstream configuration (PRD v3.0 PR-2)
# No alias compatibility: strictly SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL
SB_UPSTREAM_ORIGIN = os.getenv("SB_UPSTREAM_ORIGIN", "")
SB_PUBLIC_BASE_URL = os.getenv("SB_PUBLIC_BASE_URL", "")

# Phase 1: ASN, Trusted Proxies, Telemetry Tap, and TLS configuration
SB_ASN_DB_PATH = os.getenv("SB_ASN_DB_PATH", "")
SB_TRUSTED_PROXY_IPS = os.getenv("SB_TRUSTED_PROXY_IPS", "")
SB_TELEMETRY_BATCH_SIZE = int(os.getenv("SB_TELEMETRY_BATCH_SIZE", "50"))
SB_TELEMETRY_FLUSH_INTERVAL_MS = int(os.getenv("SB_TELEMETRY_FLUSH_INTERVAL_MS", "100"))
SB_TELEMETRY_QUEUE_MAXSIZE = int(os.getenv("SB_TELEMETRY_QUEUE_MAXSIZE", "10000"))
SB_TLS_CERT_PATH = os.getenv("SB_TLS_CERT_PATH", "")
SB_TLS_KEY_PATH = os.getenv("SB_TLS_KEY_PATH", "")
SB_TLS_PORT = int(os.getenv("SB_TLS_PORT", "8443"))

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


# Mutation mode & Phase 2 Adaptive AR Classifier and Dynamic Router configuration (PRD M2)
SB_MUTATION_MODE = os.getenv("SB_MUTATION_MODE", "adaptive").strip().lower()
SB_AR_ALPHA = float(os.getenv("SB_AR_ALPHA", "0.2"))
SB_AR_ANOMALY_STREAK = int(os.getenv("SB_AR_ANOMALY_STREAK", "20"))
SB_TRUST_THRESHOLD = float(os.getenv("SB_TRUST_THRESHOLD", "70.0"))
SB_BASELINE_MIN_SAMPLES = int(os.getenv("SB_BASELINE_MIN_SAMPLES", "10"))
SB_REDIS_URL = os.getenv("SB_REDIS_URL", "")


def get_mutation_mode() -> str:
    """Return runtime configured mutation mode: 'adaptive' or 'always'."""
    val = os.getenv("SB_MUTATION_MODE")
    if val is not None:
        return val.strip().lower()
    return SB_MUTATION_MODE


def get_ar_alpha() -> float:
    """Return EMA smoothing factor alpha (default 0.2)."""
    try:
        val = os.getenv("SB_AR_ALPHA")
        if val is not None:
            return float(val)
    except Exception:
        pass
    return SB_AR_ALPHA


def get_ar_anomaly_streak() -> int:
    """Return threshold for consecutive zero-AR calls triggering sticky sandbox lock (default 20)."""
    try:
        val = os.getenv("SB_AR_ANOMALY_STREAK")
        if val is not None:
            return int(val)
    except Exception:
        pass
    return SB_AR_ANOMALY_STREAK


def get_trust_threshold() -> float:
    """Return trust score threshold (0-100) above which sessions take FAST_PATH (default 70.0)."""
    try:
        val = os.getenv("SB_TRUST_THRESHOLD")
        if val is not None:
            return float(val)
    except Exception:
        pass
    return SB_TRUST_THRESHOLD


def get_baseline_min_samples() -> int:
    """Return minimum samples required before route baseline is considered mature (default 10)."""
    try:
        val = os.getenv("SB_BASELINE_MIN_SAMPLES")
        if val is not None:
            return int(val)
    except Exception:
        pass
    return SB_BASELINE_MIN_SAMPLES


def get_redis_url() -> str:
    """Return Redis connection URL, or empty string for embedded SQLite store."""
    return os.getenv("SB_REDIS_URL", SB_REDIS_URL).strip()


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


def get_trusted_proxy_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse runtime SB_TRUSTED_PROXY_IPS into a list of IP networks."""
    raw = os.getenv("SB_TRUSTED_PROXY_IPS", SB_TRUSTED_PROXY_IPS).strip()
    if not raw:
        return []
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    # Support comma-separated or JSON list
    items = raw.split(",") if not raw.startswith("[") else json.loads(raw)
    for item in items:
        token = str(item).strip()
        if not token:
            continue
        try:
            networks.append(ipaddress.ip_network(token, strict=False))
        except ValueError as exc:
            logger.warning("Invalid trusted proxy network '%s': %s", token, exc)
    return networks


def is_ip_in_trusted_proxies(ip_str: str) -> bool:
    """Check if the given IP string matches any configured trusted proxy network."""
    if not ip_str:
        return False
    try:
        addr = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return False
    for net in get_trusted_proxy_networks():
        if addr in net:
            return True
    return False


def get_asn_db_path() -> str:
    """Return runtime configured ASN database path."""
    return os.getenv("SB_ASN_DB_PATH", SB_ASN_DB_PATH).strip()


def get_telemetry_batch_size() -> int:
    """Return runtime configured telemetry batch size."""
    try:
        val = os.getenv("SB_TELEMETRY_BATCH_SIZE")
        if val is not None:
            return int(val)
    except Exception:
        pass
    return SB_TELEMETRY_BATCH_SIZE


def get_telemetry_flush_interval_ms() -> int:
    """Return runtime configured telemetry flush interval in ms."""
    try:
        val = os.getenv("SB_TELEMETRY_FLUSH_INTERVAL_MS")
        if val is not None:
            return int(val)
    except Exception:
        pass
    return SB_TELEMETRY_FLUSH_INTERVAL_MS


def get_public_base_url() -> str:
    """Return runtime configured public base URL."""
    return os.getenv("SB_PUBLIC_BASE_URL", SB_PUBLIC_BASE_URL).strip()

