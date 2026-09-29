"""Canary normalization and hashing (master plan §8)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

_WHITESPACE = re.compile(r"\s+")
_MARKUP_CHARS = str.maketrans("", "", "*_`")


def normalize(text: str) -> str:
    """Unicode NFC, collapse whitespace runs to one space, strip."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def normalize_for_match(text: str) -> str:
    """normalize() plus lowercase and removal of markdown emphasis chars (* _ `)."""
    return normalize(text.translate(_MARKUP_CHARS)).lower()


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def canary_hash(record: Mapping[str, Any]) -> str:
    """sha256 of canonical JSON over canary_id, type, normalized content, content_version."""
    payload = {
        "canary_id": record["canary_id"],
        "type": record["type"],
        "content": normalize(record["content"]),
        "content_version": record["content_version"],
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def block_hash(text: str) -> str:
    """sha256 of an injected/observed text block after normalize()."""
    return _sha256(normalize(text))
