"""Canary constants, data structures, and format helpers for ScrapeBuster Phase 1."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

CANARIES_YAML: Path = Path(__file__).resolve().parent / "canaries.yaml"

# Regex pattern for canonical canary tokens:
# Phase 1: SB-CANARY-<32 hex session hash>-<min 4 digit sequence>
# Also supports general SB-CANARY-<hex>-<seq> and seed SB-CAN-<seq>
CANARY_ID_PATTERN = re.compile(
    r"\b(SB-CANARY-[0-9a-fA-F]{8,64}-\d{4,}|SB-CAN-\d{4,})\b"
)
CANARY_ATTR_PATTERN = re.compile(
    r'data-canary-id=["\']([^"\']+)["\']'
)
CANARY_JSON_PATTERN = re.compile(
    r'"canary_id"\s*:\s*"([^"\']+)"'
)


@dataclass(frozen=True)
class SessionCanaryBinding:
    """Runtime binding for session-bound canaries."""

    canary_id: str
    session_id: str
    vector: str
    ts: str
    value: str


def session_hash_for_canary(session_id: str) -> str:
    """Compute 32-hex canonical session hash for canary ID per PRD v3 Phase 1."""
    clean = str(session_id or "anonymous")
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:32]


def format_canary_id(session_id: str, seq: int) -> str:
    """Format canonical canary ID: SB-CANARY-<32hex_session_hash>-<min 4 decimal seq>."""
    shash = session_hash_for_canary(session_id)
    return f"SB-CANARY-{shash}-{seq:04d}"


def normalize_vector(vector: str) -> str:
    """Normalize vector identifiers to PRD standard (API/TEXT/JSONLD)."""
    v = (vector or "").strip()
    v_upper = v.upper()
    if v_upper in ("HTML", "TEXT"):
        return "TEXT"
    if v_upper in ("JSON", "API"):
        return "API"
    if v_upper in ("JSONLD", "BEACON", "DNS", "HONEYKEY"):
        return v_upper
    return v_upper or "TEXT"


def extract_canary_ids(body: bytes | str | None) -> tuple[str, ...]:
    """Extract all served canary IDs from response bytes or text in document order.

    Extracts:
    1. HTML data-canary-id attributes
    2. JSON canary_id properties
    3. Direct canary token strings matching SB-CANARY-* or SB-CAN-*
    Deduplicates while preserving order of appearance.
    """
    if not body:
        return ()

    if isinstance(body, bytes):
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            text = body.decode("utf-8", errors="replace")
    else:
        text = str(body)

    matches: list[tuple[int, str]] = []

    for m in CANARY_ATTR_PATTERN.finditer(text):
        cid = m.group(1).strip()
        if cid:
            matches.append((m.start(1), cid))

    for m in CANARY_JSON_PATTERN.finditer(text):
        cid = m.group(1).strip()
        if cid:
            matches.append((m.start(1), cid))

    for m in CANARY_ID_PATTERN.finditer(text):
        cid = m.group(1).strip()
        if cid:
            matches.append((m.start(1), cid))

    matches.sort(key=lambda x: x[0])

    seen: set[str] = set()
    deduped: list[str] = []
    for _, cid in matches:
        if cid and cid not in seen:
            seen.add(cid)
            deduped.append(cid)

    return tuple(deduped)
