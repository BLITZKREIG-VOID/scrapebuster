"""Enriched request context extraction for ScrapeBuster Phase 1 (PRD FR1.1–FR1.3).

Passively inspects client IP (with trusted proxy boundary validation),
User-Agent, Autonomous System Number (ASN), genuine TLS fingerprint (JA3/JA4),
HTTP protocol version (HTTP/1.1 vs HTTP/2), raw header ordering, and target classification.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import Request

from ..config import is_ip_in_trusted_proxies
from .asn import lookup_asn
from .tls import get_tls_capture

logger = logging.getLogger("sb.edge.context")

# File extensions definitively classified as static assets (FR1.3)
STATIC_EXTENSIONS = frozenset({
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".webp",
    ".avif",
    ".map",
    ".mp4",
    ".webm",
    ".wasm",
})


class RequestContext:
    def __init__(self, request: Request | None = None):
        self.request = request
        scope: dict[str, Any] = getattr(request, "scope", {}) if request else {}

        # 1. Socket client IP and port extraction
        client_obj = getattr(request, "client", None) if request else None
        socket_ip = getattr(client_obj, "host", "127.0.0.1") or "127.0.0.1"
        socket_port = getattr(client_obj, "port", 0) or 0

        # 2. Trusted proxy boundary and real client IP resolution
        is_trusted = is_ip_in_trusted_proxies(socket_ip)
        resolved_ip = socket_ip
        tls_source = "none"
        ja3_hash: str | None = None
        ja4_hash: str | None = None
        tls_version: str | None = None

        if request:
            if is_trusted:
                # Behind an authentic upstream proxy: inspect trusted forwarding headers
                xff = request.headers.get("x-forwarded-for")
                if xff:
                    resolved_ip = xff.split(",")[0].strip()
                elif "x-real-ip" in request.headers:
                    resolved_ip = request.headers["x-real-ip"].strip()

                # Read trusted forwarded TLS metadata if present
                fwd_ja3 = request.headers.get("x-client-ja3")
                fwd_ja4 = request.headers.get("x-client-ja4")
                fwd_tls_ver = request.headers.get("x-client-tls-version")
                fwd_proto = request.headers.get("x-forwarded-proto", "").lower()

                if fwd_ja3:
                    ja3_hash = fwd_ja3.strip() or None
                    ja4_hash = fwd_ja4.strip() if fwd_ja4 else None
                    tls_version = fwd_tls_ver.strip() if fwd_tls_ver else None
                    tls_source = "trusted_proxy"
                elif fwd_proto == "https":
                    tls_source = "trusted_proxy"
            else:
                # Direct / untrusted connection: strictly ignore client-supplied TLS/forwarding headers!
                resolved_ip = socket_ip
                # Check local TLS termination capture registry
                local_capture = get_tls_capture(socket_ip, socket_port)
                if not local_capture and isinstance(scope, dict):
                    local_capture = scope.get("tls_client_hello") or scope.get("tls")

                if local_capture and isinstance(local_capture, dict):
                    ja3_hash = local_capture.get("ja3_hash")
                    ja4_hash = local_capture.get("ja4_hash")
                    tls_version = local_capture.get("tls_version")
                    tls_source = "local_tls"
                else:
                    tls_source = "none"
                    ja3_hash = None
                    ja4_hash = None
                    tls_version = None

        # Canonical IP attribute
        self.ip: str = resolved_ip
        self.ja3_hash: str | None = ja3_hash
        self.ja4_hash: str | None = ja4_hash
        self.tls_version: str | None = tls_version
        self.tls_source: str = tls_source

        # 3. ASN resolution (truth: int | None, status: ok | unavailable | loopback)
        asn_val, asn_stat = lookup_asn(self.ip)
        self.asn: int | None = asn_val
        self.asn_status: str = asn_stat

        # 4. Raw User-Agent
        self.user_agent: str = (request.headers.get("user-agent", "") if request else "")

        # 5. HTTP protocol version truth (HTTP/1.1 vs HTTP/2)
        raw_http_ver = scope.get("http_version", "1.1") if isinstance(scope, dict) else "1.1"
        if raw_http_ver in ("2", "2.0"):
            self.http_version: str = "HTTP/2"
        elif raw_http_ver == "1.0":
            self.http_version = "HTTP/1.0"
        else:
            self.http_version = "HTTP/1.1"

        # 6. Raw header ordering and canonical header fingerprint
        if isinstance(scope, dict) and "headers" in scope and scope["headers"]:
            self.header_order: list[str] = [
                k.decode("latin1") for k, _ in scope["headers"]
            ]
        elif request and request.headers:
            self.header_order = list(request.headers.keys())
        else:
            self.header_order = []

        headers_order_str = ",".join(k.lower() for k in self.header_order)
        self.header_fp: str = hashlib.sha256(headers_order_str.encode("utf-8")).hexdigest()[:16]

        # 7. Server-side client key and path
        raw_key = f"{self.ip}|{self.user_agent}".encode()
        self.client_key: str = hashlib.sha256(raw_key).hexdigest()[:16]
        self.path: str = request.url.path if request else "/"

        # 8. Target classification (is_static vs is_api vs is_document)
        path_lower = self.path.lower()
        has_static_ext = any(path_lower.endswith(ext) for ext in STATIC_EXTENSIONS)
        self.is_static: bool = (
            has_static_ext
            or path_lower.startswith(("/static/", "/assets/"))
            or path_lower == "/favicon.ico"
        )

        self.is_api: bool = not self.is_static and (
            path_lower.startswith(("/api/", "/trap/api/"))
        )

        self.is_document: bool = (
            not self.is_static
            and not self.is_api
            and self.path not in ("/favicon.ico", "/health")
        )

    @property
    def client_ip(self) -> str:
        """Alias for canonical existing .ip attribute."""
        return self.ip


def build_context(request: Request) -> RequestContext:
    """Factory to construct enriched RequestContext from inbound request."""
    return RequestContext(request)
