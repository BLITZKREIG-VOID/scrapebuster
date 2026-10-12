"""TLS termination, ClientHello capture, and fingerprinting adapter (PRD FR1.1, FR1.2).

Extracts authentic TLS ClientHello metadata during local TLS termination or
from authenticated trusted proxy boundaries. Plaintext HTTP strictly yields
ja3_hash=None, ja4_hash=None, and tls_source="none". Never guesses or fabricates
hashes from User-Agent or HTTP headers.
"""

from __future__ import annotations

import hashlib
import logging
import os
import ssl
import struct
import threading
from typing import Any

logger = logging.getLogger("sb.edge.tls")

# Headers that unauthenticated clients may attempt to spoof
FORGED_TLS_HEADERS = frozenset({
    "x-client-ja3",
    "x-client-ja4",
    "x-client-tls-version",
    "x-client-ciphers",
    "x-client-fingerprint",
    "x-client-extensions",
})

# GREASE values (RFC 8701) to ignore in JA3/JA4 calculations
# Values like 0x0a0a, 0x1a1a, ..., 0xfafa
def is_grease(val: int) -> bool:
    """Return True if the 16-bit value is an RFC 8701 GREASE value."""
    return (val & 0x0F0F) == 0x0A0A and ((val >> 8) == (val & 0xFF))


def compute_ja3(
    version: int,
    ciphers: list[int],
    extensions: list[int],
    curves: list[int],
    point_formats: list[int],
) -> tuple[str, str]:
    """Compute JA3 fingerprint string and MD5 hash (excluding GREASE values).

    JA3 = SSLVersion,CipherSuites,Extensions,EllipticCurves,EllipticCurvePointFormats
    """
    clean_ciphers = [str(c) for c in ciphers if not is_grease(c)]
    clean_exts = [str(e) for e in extensions if not is_grease(e)]
    clean_curves = [str(crv) for crv in curves if not is_grease(crv)]
    clean_points = [str(p) for p in point_formats]

    ja3_str = (
        f"{version},"
        f"{'-'.join(clean_ciphers)},"
        f"{'-'.join(clean_exts)},"
        f"{'-'.join(clean_curves)},"
        f"{'-'.join(clean_points)}"
    )
    ja3_hash = hashlib.md5(ja3_str.encode("ascii")).hexdigest()
    return ja3_str, ja3_hash


def compute_ja4(
    tls_version_str: str,
    ciphers: list[int],
    extensions: list[int],
    alpn: list[str],
    has_sni: bool,
) -> str:
    """Compute FoxIO JA4 fingerprint string: a_b_c format.

    - Part a: (protocol)(version)(sni)(ciphers_count)(extensions_count)(alpn)
    - Part b: Truncated 12-char SHA256 of sorted 4-char hex non-GREASE ciphers
    - Part c: Truncated 12-char SHA256 of sorted 4-char hex non-GREASE extensions
    """
    clean_ciphers = [c for c in ciphers if not is_grease(c)]
    clean_exts = [e for e in extensions if not is_grease(e) and e not in (0x0000, 0x0010)]

    # Protocol: 't' for TCP
    proto = "t"

    # Version: '13', '12', '11', '10', 's3'
    if "1.3" in tls_version_str:
        ver = "13"
    elif "1.2" in tls_version_str:
        ver = "12"
    elif "1.1" in tls_version_str:
        ver = "11"
    elif "1.0" in tls_version_str:
        ver = "10"
    else:
        ver = "00"

    sni_char = "d" if has_sni else "i"
    c_count = f"{min(len(clean_ciphers), 99):02d}"
    e_count = f"{min(len(clean_exts), 99):02d}"

    # ALPN: first & last char of first ALPN string, or '00'
    if alpn and alpn[0]:
        first_alpn = alpn[0]
        if len(first_alpn) == 1:
            alpn_code = f"{first_alpn}{first_alpn}"
        else:
            alpn_code = f"{first_alpn[0]}{first_alpn[-1]}"
    else:
        alpn_code = "00"

    part_a = f"{proto}{ver}{sni_char}{c_count}{e_count}{alpn_code}"

    # Part b: sorted hex ciphers
    sorted_ciphers = sorted(f"{c:04x}" for c in clean_ciphers)
    ciphers_str = ",".join(sorted_ciphers)
    part_b = (
        hashlib.sha256(ciphers_str.encode("ascii")).hexdigest()[:12]
        if sorted_ciphers
        else "000000000000"
    )

    # Part c: sorted hex extensions
    sorted_exts = sorted(f"{e:04x}" for e in clean_exts)
    exts_str = ",".join(sorted_exts)
    part_c = (
        hashlib.sha256(exts_str.encode("ascii")).hexdigest()[:12]
        if sorted_exts
        else "000000000000"
    )

    return f"{part_a}_{part_b}_{part_c}"


def parse_client_hello(raw_bytes: bytes) -> dict[str, Any]:
    """Parse raw TLS ClientHello record bytes and return extracted parameters.

    Returns dict with:
        tls_record_version, client_version, tls_version, ciphers,
        extensions, curves, point_formats, alpn, sni, ja3_string,
        ja3_hash, ja4_hash.
    """
    if not raw_bytes or len(raw_bytes) < 42:
        raise ValueError(f"Payload too short for TLS ClientHello: {len(raw_bytes)} bytes")

    offset = 0
    # Check if raw_bytes starts with TLS record header (0x16 = Handshake)
    if raw_bytes[0] == 0x16:
        # TLS Record Header: 1 byte type, 2 bytes version, 2 bytes length
        record_version = struct.unpack("!H", raw_bytes[1:3])[0]
        _ = struct.unpack("!H", raw_bytes[3:5])[0]  # record_length (unused)
        offset = 5
    else:
        record_version = 0x0303

    # Handshake Message Type: 0x01 = ClientHello
    if offset >= len(raw_bytes) or raw_bytes[offset] != 0x01:
        raise ValueError("Not a TLS ClientHello handshake message")

    # Handshake length: 3 bytes
    _ = (raw_bytes[offset + 1] << 16) | (raw_bytes[offset + 2] << 8) | raw_bytes[offset + 3]
    offset += 4

    # Client Version: 2 bytes
    client_version = struct.unpack("!H", raw_bytes[offset : offset + 2])[0]
    offset += 2

    # Random: 32 bytes
    offset += 32

    # Session ID: 1 byte length + data
    if offset >= len(raw_bytes):
        raise ValueError("Malformed ClientHello: missing session ID length")
    sess_id_len = raw_bytes[offset]
    offset += 1 + sess_id_len

    # Cipher Suites: 2 bytes length + 2 bytes per cipher
    if offset + 2 > len(raw_bytes):
        raise ValueError("Malformed ClientHello: missing cipher suites")
    ciphers_len = struct.unpack("!H", raw_bytes[offset : offset + 2])[0]
    offset += 2

    ciphers: list[int] = []
    for i in range(0, ciphers_len, 2):
        if offset + i + 2 <= len(raw_bytes):
            ciphers.append(struct.unpack("!H", raw_bytes[offset + i : offset + i + 2])[0])
    offset += ciphers_len

    # Compression Methods: 1 byte length + data
    if offset >= len(raw_bytes):
        comp_len = 0
    else:
        comp_len = raw_bytes[offset]
        offset += 1 + comp_len

    extensions: list[int] = []
    curves: list[int] = []
    point_formats: list[int] = []
    alpn: list[str] = []
    sni: str | None = None
    has_tls13 = False

    # Extensions: 2 bytes total length + extension records
    if offset + 2 <= len(raw_bytes):
        exts_total_len = struct.unpack("!H", raw_bytes[offset : offset + 2])[0]
        offset += 2
        exts_end = min(offset + exts_total_len, len(raw_bytes))

        while offset + 4 <= exts_end:
            ext_type = struct.unpack("!H", raw_bytes[offset : offset + 2])[0]
            ext_len = struct.unpack("!H", raw_bytes[offset + 2 : offset + 4])[0]
            offset += 4
            ext_data = raw_bytes[offset : offset + ext_len]
            offset += ext_len

            extensions.append(ext_type)

            # SNI (0x0000)
            if ext_type == 0x0000 and len(ext_data) >= 5:
                try:
                    # 2 bytes list length, 1 byte name type (0 = host), 2 bytes name length
                    name_len = struct.unpack("!H", ext_data[3:5])[0]
                    sni = ext_data[5 : 5 + name_len].decode("ascii", errors="replace")
                except (struct.error, ValueError):
                    # Malformed SNI extension: leave sni unset.
                    logger.debug("Malformed SNI extension in ClientHello", exc_info=True)

            # Supported Groups / Elliptic Curves (0x000A)
            elif ext_type == 0x000A and len(ext_data) >= 2:
                curves_len = struct.unpack("!H", ext_data[0:2])[0]
                for ci in range(2, min(2 + curves_len, len(ext_data)), 2):
                    curves.append(struct.unpack("!H", ext_data[ci : ci + 2])[0])

            # EC Point Formats (0x000B)
            elif ext_type == 0x000B and len(ext_data) >= 1:
                pf_len = ext_data[0]
                for pi in range(1, min(1 + pf_len, len(ext_data))):
                    point_formats.append(ext_data[pi])

            # ALPN (0x0010)
            elif ext_type == 0x0010 and len(ext_data) >= 2:
                alpn_len = struct.unpack("!H", ext_data[0:2])[0]
                p_idx = 2
                while p_idx < min(2 + alpn_len, len(ext_data)):
                    proto_len = ext_data[p_idx]
                    p_idx += 1
                    proto_str = ext_data[p_idx : p_idx + proto_len].decode("ascii", errors="replace")
                    alpn.append(proto_str)
                    p_idx += proto_len

            # Supported Versions (0x002B)
            elif ext_type == 0x002B and len(ext_data) >= 1:
                sv_len = ext_data[0]
                for vi in range(1, min(1 + sv_len, len(ext_data)), 2):
                    ver_val = struct.unpack("!H", ext_data[vi : vi + 2])[0]
                    if ver_val == 0x0304:
                        has_tls13 = True

    # Determine TLS version name
    if has_tls13 or client_version == 0x0304:
        tls_version = "TLS 1.3"
    elif client_version == 0x0303:
        tls_version = "TLS 1.2"
    elif client_version == 0x0302:
        tls_version = "TLS 1.1"
    elif client_version == 0x0301:
        tls_version = "TLS 1.0"
    else:
        tls_version = f"0x{client_version:04x}"

    ja3_str, ja3_hash = compute_ja3(
        client_version, ciphers, extensions, curves, point_formats
    )
    ja4_hash = compute_ja4(tls_version, ciphers, extensions, alpn, bool(sni))

    return {
        "record_version": record_version,
        "client_version": client_version,
        "tls_version": tls_version,
        "ciphers": ciphers,
        "extensions": extensions,
        "curves": curves,
        "point_formats": point_formats,
        "alpn": alpn,
        "sni": sni,
        "ja3_string": ja3_str,
        "ja3_hash": ja3_hash,
        "ja4_hash": ja4_hash,
    }


# ---------------------------------------------------------------------------
# TLS Connection Registry for Local Termination
# ---------------------------------------------------------------------------
class TLSCaptureRegistry:
    """Thread-safe registry mapping client (host, port) to captured TLS metadata."""

    def __init__(self):
        self._lock = threading.Lock()
        self._captures: dict[tuple[str, int], dict[str, Any]] = {}

    def register(self, host: str, port: int, metadata: dict[str, Any]) -> None:
        with self._lock:
            self._captures[(host, port)] = metadata

    def lookup(self, host: str, port: int) -> dict[str, Any] | None:
        with self._lock:
            return self._captures.get((host, port))

    def pop(self, host: str, port: int) -> dict[str, Any] | None:
        with self._lock:
            return self._captures.pop((host, port), None)

    def clear(self) -> None:
        with self._lock:
            self._captures.clear()


_registry = TLSCaptureRegistry()


def register_tls_capture(host: str, port: int, metadata: dict[str, Any]) -> None:
    """Register captured TLS handshake metadata for a client address."""
    _registry.register(host, port, metadata)


def get_tls_capture(host: str, port: int) -> dict[str, Any] | None:
    """Retrieve captured TLS metadata for a client address."""
    return _registry.lookup(host, port)


def pop_tls_capture(host: str, port: int) -> dict[str, Any] | None:
    """Retrieve and remove captured TLS metadata for a client address."""
    return _registry.pop(host, port)


def clear_tls_captures() -> None:
    """Clear all registered TLS captures."""
    _registry.clear()


def strip_untrusted_tls_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a dictionary of headers stripped of forged client-supplied TLS headers."""
    return {k: v for k, v in headers.items() if k.lower() not in FORGED_TLS_HEADERS}


# ---------------------------------------------------------------------------
# Local TLS Termination Server Adapter (for Integration / Benchmark / Regression)
# ---------------------------------------------------------------------------
def create_self_signed_cert(
    cert_path: str,
    key_path: str,
    host: str = "localhost",
) -> tuple[str, str]:
    """Generate self-signed certificate and private key for local TLS termination."""
    os.makedirs(os.path.dirname(os.path.abspath(cert_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(key_path)), exist_ok=True)

    try:
        import datetime

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, host),
        ])
        now = datetime.datetime.now(datetime.UTC)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256())
        )

        with open(key_path, "wb") as f:
            f.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        return cert_path, key_path
    except ImportError:
        logger.warning("cryptography package not available for self-signed cert generation")
        return cert_path, key_path


def create_ssl_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    """Create SSLContext configured for local TLS termination."""
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return ctx
