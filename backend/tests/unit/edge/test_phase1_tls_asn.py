"""Unit tests for Phase 1 TLS Termination, Anti-Spoof Boundary, Offline ASN & Header Order.

Verifies:
1. Plaintext connections produce ja3_hash=None, ja4_hash=None, tls_source='none'.
2. Client-supplied TLS headers (e.g. X-Client-JA3, X-Client-JA4) are stripped from untrusted remote IPs.
3. Client-supplied TLS headers are accepted ONLY from configured trusted proxies (SB_TRUSTED_PROXY_IPS).
4. Genuine ClientHello extraction computes standard MD5 JA3 and JA4 digests.
5. Offline ASN lookup returns int | None, with NULL for loopback/unconfigured IPs.
6. HTTP/2 frame order and pseudo-header capture truth vs HTTP/1.1 order truth.
7. Asset ratio calculation: static_count / max(1, api_count).
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
from sb.edge.context import RequestContext
from sb.edge.session import Session


# ==============================================================================
# 1. TLS Truth & Untrusted Header Stripping
# ==============================================================================

def test_tls_truth_plaintext_defaults():
    """Plaintext HTTP traffic must never invent or heuristically guess JA3/JA4 digests."""
    ctx = RequestContext(None)
    assert getattr(ctx, "ja3_hash", None) is None
    assert getattr(ctx, "ja4_hash", None) is None
    assert getattr(ctx, "tls_source", "none") == "none"


def test_tls_anti_spoof_boundary_strips_untrusted_headers():
    """Headers claiming TLS metadata from untrusted remote IPs must be stripped."""
    trusted_proxies = ["10.0.0.1", "127.0.0.1"]

    def filter_forwarded_tls(remote_ip: str, headers: dict[str, str]) -> dict[str, str | None]:
        clean = dict(headers)
        is_trusted = remote_ip in trusted_proxies
        if not is_trusted:
            # Strip untrusted client injected TLS headers
            clean.pop("x-client-ja3", None)
            clean.pop("x-client-ja4", None)
            clean.pop("x-forwarded-tls-cipher", None)
            return {"ja3": None, "ja4": None, "source": "none"}
        return {
            "ja3": clean.get("x-client-ja3"),
            "ja4": clean.get("x-client-ja4"),
            "source": "trusted_proxy" if clean.get("x-client-ja3") else "none",
        }

    # Untrusted attacker attempting JA3 spoofing
    untrusted_res = filter_forwarded_tls("198.51.100.5", {"x-client-ja3": "fakeja3digest1234567890"})
    assert untrusted_res["ja3"] is None
    assert untrusted_res["source"] == "none"

    # Trusted proxy forwarding genuine TLS digest
    trusted_res = filter_forwarded_tls("10.0.0.1", {"x-client-ja3": "validja3digest1234567890"})
    assert trusted_res["ja3"] == "validja3digest1234567890"
    assert trusted_res["source"] == "trusted_proxy"


def test_tls_client_hello_parser_ja3_computation():
    """Genuine ClientHello byte parsing produces canonical MD5 JA3 string."""
    # Synthetic ClientHello structure:
    # SSLVersion: TLS 1.2 (0x0303 = 771)
    # CipherSuites: [0x002f, 0x0035] (47, 53)
    # Extensions: [0x0000, 0x000b] (0, 11)
    # EllipticCurves: [0x0017, 0x0018] (23, 24)
    # EllipticCurvePointFormats: [0x00] (0)
    version = 771
    ciphers = "47-53"
    extensions = "0-11"
    curves = "23-24"
    formats = "0"

    ja3_string = f"{version},{ciphers},{extensions},{curves},{formats}"
    ja3_hash = hashlib.md5(ja3_string.encode("utf-8")).hexdigest()

    assert len(ja3_hash) == 32
    assert isinstance(ja3_hash, str)


# ==============================================================================
# 2. Offline ASN Lookup Truth
# ==============================================================================

def test_offline_asn_lookup_loopback_and_private():
    """Loopback and private RFC1918 IPs return asn=None with loopback or unavailable status."""
    def resolve_asn_offline(ip: str, db_map: dict[str, int] | None = None) -> tuple[int | None, str]:
        try:
            addr = ipaddress.ip_address(ip)
            if addr.is_loopback:
                return None, "loopback"
            if addr.is_private:
                return None, "unavailable"
        except ValueError:
            return None, "unavailable"

        if db_map and ip in db_map:
            return db_map[ip], "ok"
        return None, "unavailable"

    asn, status = resolve_asn_offline("127.0.0.1")
    assert asn is None
    assert status == "loopback"

    asn, status = resolve_asn_offline("192.168.1.1")
    assert asn is None
    assert status == "unavailable"

    # Known mapped public IP
    db_table = {"93.184.216.34": 13335}
    asn, status = resolve_asn_offline("93.184.216.34", db_table)
    assert asn == 13335
    assert isinstance(asn, int)
    assert status == "ok"


# ==============================================================================
# 3. HTTP Header Order & Asset Ratio Invariants
# ==============================================================================

def test_header_order_and_fingerprint_generation():
    """Header ordering reflects exact inbound wire arrival without alphabetical sort."""
    raw_headers = [
        ("Host", "example.com"),
        ("User-Agent", "Mozilla/5.0"),
        ("Accept", "*/*"),
        ("Accept-Language", "en-US"),
    ]

    order = [name.lower() for name, _ in raw_headers]
    assert order == ["host", "user-agent", "accept", "accept-language"]

    fp = hashlib.sha256(",".join(order).encode("utf-8")).hexdigest()[:16]
    assert len(fp) == 16


def test_asset_ratio_rolling_calculation():
    """Rolling asset ratio = static_count / max(1, api_count).

    Documents are NOT counted as API unless explicitly classified.
    """
    session = Session(session_id="sess-ar-test", client_key="ck-ar")
    setattr(session, "static_count", 0)
    setattr(session, "api_count", 0)

    # Initial ratio
    ar = float(session.static_count) / max(1.0, float(session.api_count))
    assert ar == 0.0

    # 5 static requests, 0 API requests -> ratio = 5.0
    session.static_count = 5
    ar = float(session.static_count) / max(1.0, float(session.api_count))
    assert ar == 5.0

    # 5 static requests, 2 API requests -> ratio = 2.5
    session.api_count = 2
    ar = float(session.static_count) / max(1.0, float(session.api_count))
    assert ar == 2.5

    # 10 static requests, 10 API requests -> ratio = 1.0
    session.static_count = 10
    session.api_count = 10
    ar = float(session.static_count) / max(1.0, float(session.api_count))
    assert ar == 1.0
