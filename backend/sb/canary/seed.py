"""Seed canary definitions into the database and record publication."""

from __future__ import annotations

from sb.canary import hashing, registry
from sb.contracts import Canary


def seed_canaries(now: str | None = None) -> list[Canary]:
    """Seed canaries from canaries.yaml into SQLite database.

    For each YAML item:
    - sha256 = hashing.canary_hash({canary_id, type, content, content_version})
    - canonical_content = hashing.normalize(content)
    - status = ACTIVE
    - created_at = published_at = now (default registry.now_iso())
    - upsert canary record
    - record_publication(canary_id, now)

    Idempotent (re-running overwrites).
    """
    timestamp = now or registry.now_iso()
    definitions = registry.load_definitions()
    results: list[Canary] = []

    for item in definitions:
        sha256 = hashing.canary_hash(item)
        canonical_content = hashing.normalize(item["content"])
        record = {
            "canary_id": item["canary_id"],
            "type": item["type"],
            "canonical_content": canonical_content,
            "anchor": item["anchor"],
            "context_terms": item["context_terms"],
            "probe_prompts": item["probe_prompts"],
            "sha256": sha256,
            "content_version": item["content_version"],
            "created_at": timestamp,
            "published_at": timestamp,
            "status": "ACTIVE",
            "placements": item["placements"],
        }
        registry.upsert_canary(record)
        registry.record_publication(item["canary_id"], timestamp)
        canary = registry.get(item["canary_id"])
        if canary is not None:
            results.append(canary)

    return results
