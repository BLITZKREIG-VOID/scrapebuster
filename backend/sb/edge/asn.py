"""Offline Autonomous System Number (ASN) lookup service (PRD FR1.1, FR1.2).

Performs strict offline IP-to-ASN resolution using a configured static table,
CIDR mapping, or local database. Never performs online queries or fabricates ASNs.

Statuses:
- "ok": ASN successfully resolved from configured offline database.
- "loopback": IP address is a local loopback address (e.g., 127.0.0.1, ::1).
- "unavailable": Database unconfigured, IP is private/unroutable, or not found in database.
"""

from __future__ import annotations

import csv
import ipaddress
import json
import logging
import os
import sqlite3
import threading

from ..config import get_asn_db_path

logger = logging.getLogger("sb.edge.asn")

# Thread-safe in-memory cache for loaded CIDR ranges: list of (network, asn)
_asn_cache: list[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, int]] | None = None
_asn_cached_path: str | None = None
_cache_lock = threading.Lock()


def clear_asn_cache() -> None:
    """Clear in-memory cached ASN database."""
    global _asn_cache, _asn_cached_path
    with _cache_lock:
        _asn_cache = None
        _asn_cached_path = None


def _load_cidr_table(path: str) -> list[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, int]]:
    """Parse CIDR table from JSON, CSV, or plain text file."""
    entries: list[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, int]] = []
    if not os.path.isfile(path):
        logger.warning("ASN database file does not exist: %s", path)
        return entries

    ext = os.path.splitext(path)[1].lower()

    if ext == ".json":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for cidr_str, asn_val in data.items():
                    try:
                        net = ipaddress.ip_network(cidr_str.strip(), strict=False)
                        entries.append((net, int(asn_val)))
                    except Exception:
                        continue
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "cidr" in item and "asn" in item:
                        try:
                            net = ipaddress.ip_network(str(item["cidr"]).strip(), strict=False)
                            entries.append((net, int(item["asn"])))
                        except Exception:
                            continue
        except Exception as exc:
            logger.warning("Failed to parse JSON ASN database %s: %s", path, exc)
    elif ext in (".csv", ".tsv", ".txt"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                delimiter = "\t" if ext == ".tsv" else ","
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if not row or len(row) < 2 or row[0].startswith("#"):
                        continue
                    cidr_str, asn_str = row[0].strip(), row[1].strip()
                    try:
                        net = ipaddress.ip_network(cidr_str, strict=False)
                        entries.append((net, int(asn_str)))
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("Failed to parse CSV/TSV ASN database %s: %s", path, exc)
    return entries


def load_asn_database(path: str) -> None:
    """Pre-load and cache the ASN database from file."""
    global _asn_cache, _asn_cached_path
    with _cache_lock:
        _asn_cache = _load_cidr_table(path)
        _asn_cached_path = path


def lookup_asn(ip: str | None, db_path: str | None = None) -> tuple[int | None, str]:
    """Resolve an IP address to (asn: int | None, status: str).

    Status values:
    - "ok": Valid ASN found in configured database.
    - "loopback": Local loopback address (asn is None).
    - "unavailable": Private/unroutable address, missing DB, or not found.
    """
    if not ip or not isinstance(ip, str) or not ip.strip():
        return None, "unavailable"

    ip_clean = ip.strip()

    try:
        addr = ipaddress.ip_address(ip_clean)
    except ValueError:
        return None, "unavailable"

    # Strict loopback truth
    if addr.is_loopback:
        return None, "loopback"

    # Private and unroutable addresses cannot have authentic public ASNs
    if addr.is_private or addr.is_link_local or addr.is_reserved or addr.is_multicast:
        return None, "unavailable"

    target_db = (db_path if db_path is not None else get_asn_db_path()).strip()
    if not target_db:
        return None, "unavailable"

    ext = os.path.splitext(target_db)[1].lower()

    # MaxMind MMDB lookup if library installed and format matches
    if ext == ".mmdb":
        try:
            import maxminddb  # type: ignore

            with maxminddb.open_database(target_db) as reader:
                record = reader.get(ip_clean)
                if record and isinstance(record, dict):
                    asn = record.get("autonomous_system_number")
                    if asn is not None:
                        return int(asn), "ok"
            return None, "unavailable"
        except ImportError:
            logger.warning("maxminddb module not installed; cannot read mmdb database")
            return None, "unavailable"
        except Exception as exc:
            logger.warning("MMDB ASN lookup failed for %s: %s", ip_clean, exc)
            return None, "unavailable"

    # SQLite database lookup if format is .db / .sqlite
    if ext in (".db", ".sqlite", ".sqlite3"):
        try:
            conn = sqlite3.connect(f"file:{target_db}?mode=ro", uri=True)
            try:
                cur = conn.cursor()
                # Check for asn table with ip or cidr
                row = cur.execute(
                    "SELECT asn FROM asn_lookup WHERE ip = ? LIMIT 1", (ip_clean,)
                ).fetchone()
                if row:
                    return int(row[0]), "ok"
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("SQLite ASN lookup failed for %s: %s", ip_clean, exc)
        return None, "unavailable"

    # CIDR table lookup (cached)
    global _asn_cache, _asn_cached_path
    with _cache_lock:
        if _asn_cache is None or _asn_cached_path != target_db:
            _asn_cache = _load_cidr_table(target_db)
            _asn_cached_path = target_db
        table = _asn_cache

    if not table:
        return None, "unavailable"

    # Longest prefix match
    best_asn: int | None = None
    best_prefix_len: int = -1

    for net, asn_val in table:
        if addr in net:
            if net.prefixlen > best_prefix_len:
                best_prefix_len = net.prefixlen
                best_asn = asn_val

    if best_asn is not None:
        return best_asn, "ok"

    return None, "unavailable"
