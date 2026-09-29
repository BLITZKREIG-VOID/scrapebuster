"""Unit tests for canary registry and seed (T-CA-1 remainder)."""

from datetime import datetime
import re
import types

import pytest

from sb.canary import hashing, registry, seed
from sb.canary.registry import InvalidTransition
from sb.contracts import Canary, ExposureEvent

from ._defs import load_canaries


def test_seed_canaries_and_publications():
    yaml_records = load_canaries()
    now = "2026-09-29T10:00:00.123456Z"
    canaries = seed.seed_canaries(now=now)

    assert len(canaries) == 5
    assert len(yaml_records) == 5

    yaml_by_id = {rec["canary_id"]: rec for rec in yaml_records}

    for canary in canaries:
        assert isinstance(canary, Canary)
        assert canary.status == "ACTIVE"
        assert canary.created_at == now
        assert canary.published_at == now
        yaml_rec = yaml_by_id[canary.canary_id]
        assert canary.sha256 == hashing.canary_hash(yaml_rec)

        # Check publication row
        pub = registry.get_publication(canary.canary_id)
        assert pub is not None
        assert pub["canary_id"] == canary.canary_id
        assert pub["sha256"] == canary.sha256
        assert pub["content_version"] == canary.content_version
        assert pub["published_at"] == canary.published_at
        assert pub["placements"] == canary.placements


def test_seed_idempotent():
    now1 = "2026-09-29T10:00:00.000000Z"
    canaries1 = seed.seed_canaries(now=now1)
    assert len(canaries1) == 5
    assert len(registry.list_canaries()) == 5

    now2 = "2026-09-29T11:00:00.000000Z"
    canaries2 = seed.seed_canaries(now=now2)
    assert len(canaries2) == 5
    assert len(registry.list_canaries()) == 5

    for c in canaries2:
        assert c.created_at == now2
        assert c.published_at == now2


def test_round_trip_upsert_and_get():
    now = registry.now_iso()
    rec = {
        "canary_id": "SB-CAN-9999",
        "type": "custom_probe",
        "canonical_content": "This is custom canonical content for testing.",
        "anchor": "custom anchor",
        "context_terms": ["custom", "terms", "list"],
        "probe_prompts": ["Prompt 1?", "Prompt 2?"],
        "sha256": "fake_sha256_hash",
        "content_version": "v1",
        "created_at": now,
        "published_at": now,
        "status": "ACTIVE",
        "placements": ["/docs/custom1", "/docs/custom2"],
    }
    upserted = registry.upsert_canary(rec)
    fetched = registry.get("SB-CAN-9999")

    assert fetched is not None
    assert upserted == fetched
    assert fetched.canary_id == "SB-CAN-9999"
    assert fetched.type == "custom_probe"
    assert fetched.canonical_content == "This is custom canonical content for testing."
    assert fetched.anchor == "custom anchor"
    assert fetched.context_terms == ["custom", "terms", "list"]
    assert fetched.probe_prompts == ["Prompt 1?", "Prompt 2?"]
    assert fetched.sha256 == "fake_sha256_hash"
    assert fetched.content_version == "v1"
    assert fetched.created_at == now
    assert fetched.published_at == now
    assert fetched.status == "ACTIVE"
    assert fetched.placements == ["/docs/custom1", "/docs/custom2"]

    assert registry.get("SB-CAN-NONEXISTENT") is None


def test_record_exposure_duck_typing_and_lifecycle():
    seed.seed_canaries()
    canary = registry.get("SB-CAN-0001")
    assert canary is not None
    assert canary.status == "ACTIVE"

    session = types.SimpleNamespace(
        session_id="sess-abc123",
        client_key="ckey-xyz",
        classification="ai_crawler",
    )
    ctx = types.SimpleNamespace(
        ip="10.0.0.42",
        user_agent="BadScraper/1.0",
        method="GET",
        path="/docs/team",
        headers={
            "Referer": "https://external.example/search",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    block_text = canary.canonical_content
    exp = registry.record_exposure(
        canary_id="SB-CAN-0001",
        session=session,
        ctx=ctx,
        resource="/docs/team",
        block_text=block_text,
    )

    assert isinstance(exp, ExposureEvent)
    assert re.match(r"^EXP-[0-9a-f]{8}$", exp.exposure_id)
    assert exp.canary_id == "SB-CAN-0001"
    assert exp.session_id == "sess-abc123"
    assert exp.resource == "/docs/team"
    assert exp.content_version == canary.content_version
    assert exp.content_sha256 == hashing.block_hash(canary.canonical_content)

    assert exp.client == {
        "ip": "10.0.0.42",
        "user_agent": "BadScraper/1.0",
        "client_key": "ckey-xyz",
        "classification": "ai_crawler",
    }
    assert exp.request == {
        "method": "GET",
        "path": "/docs/team",
        "referer": "https://external.example/search",
        "accept_language": "en-US,en;q=0.9",
    }

    # Canary moved ACTIVE -> EXPOSED
    updated_canary = registry.get("SB-CAN-0001")
    assert updated_canary.status == "EXPOSED"

    # Persisted in list_exposures
    exposures = registry.list_exposures()
    assert len(exposures) == 1
    assert exposures[0].exposure_id == exp.exposure_id

    canary_exposures = registry.list_exposures("SB-CAN-0001")
    assert len(canary_exposures) == 1
    assert canary_exposures[0].exposure_id == exp.exposure_id

    # Second exposure keeps EXPOSED and yields 2 rows
    exp2 = registry.record_exposure(
        canary_id="SB-CAN-0001",
        session=session,
        ctx=ctx,
        resource="/docs/team",
        block_text=block_text,
    )
    assert exp2.exposure_id != exp.exposure_id
    assert registry.get("SB-CAN-0001").status == "EXPOSED"

    all_exposures = registry.list_exposures("SB-CAN-0001")
    assert len(all_exposures) == 2
    assert all_exposures[0].exposure_id == exp.exposure_id
    assert all_exposures[1].exposure_id == exp2.exposure_id


def test_record_exposure_unknown_canary():
    session = types.SimpleNamespace(session_id="s1")
    ctx = types.SimpleNamespace()
    with pytest.raises(KeyError):
        registry.record_exposure(
            canary_id="UNKNOWN-CANARY",
            session=session,
            ctx=ctx,
            resource="/test",
            block_text="some text",
        )


def test_set_status_transitions():
    seed.seed_canaries()
    c = registry.get("SB-CAN-0001")
    assert c.status == "ACTIVE"

    # Same status no-op
    c_noop = registry.set_status("SB-CAN-0001", "ACTIVE")
    assert c_noop.status == "ACTIVE"

    # ACTIVE -> EXPOSED ok
    c_exposed = registry.set_status("SB-CAN-0001", "EXPOSED")
    assert c_exposed.status == "EXPOSED"
    assert registry.get("SB-CAN-0001").status == "EXPOSED"

    # Same status no-op
    c_exposed_noop = registry.set_status("SB-CAN-0001", "EXPOSED")
    assert c_exposed_noop.status == "EXPOSED"

    # EXPOSED -> OBSERVED ok
    c_observed = registry.set_status("SB-CAN-0001", "OBSERVED")
    assert c_observed.status == "OBSERVED"
    assert registry.get("SB-CAN-0001").status == "OBSERVED"

    # Same status no-op
    c_observed_noop = registry.set_status("SB-CAN-0001", "OBSERVED")
    assert c_observed_noop.status == "OBSERVED"

    # Illegal transitions from OBSERVED
    with pytest.raises(InvalidTransition):
        registry.set_status("SB-CAN-0001", "ACTIVE")
    with pytest.raises(InvalidTransition):
        registry.set_status("SB-CAN-0001", "EXPOSED")
    with pytest.raises(InvalidTransition):
        registry.set_status("SB-CAN-0001", "DRAFT")

    # Illegal transitions from ACTIVE (using SB-CAN-0002)
    with pytest.raises(InvalidTransition):
        registry.set_status("SB-CAN-0002", "OBSERVED")
    with pytest.raises(InvalidTransition):
        registry.set_status("SB-CAN-0002", "DRAFT")

    # Illegal transitions from EXPOSED (using SB-CAN-0003)
    registry.set_status("SB-CAN-0003", "EXPOSED")
    with pytest.raises(InvalidTransition):
        registry.set_status("SB-CAN-0003", "ACTIVE")
    with pytest.raises(InvalidTransition):
        registry.set_status("SB-CAN-0003", "DRAFT")


def test_set_status_unknown_canary():
    with pytest.raises(KeyError):
        registry.set_status("SB-CAN-UNKNOWN", "EXPOSED")


def test_injected_block_text():
    seed.seed_canaries()
    c = registry.get("SB-CAN-0001")
    assert registry.injected_block_text(c) == c.canonical_content


def test_now_iso_format():
    iso = registry.now_iso()
    assert iso.endswith("Z")
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    assert dt.tzinfo is not None
