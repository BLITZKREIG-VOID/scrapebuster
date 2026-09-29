"""T-CA-3: no probe prompt contains its anchor or any context term; §8 definition invariants."""

import pytest
from sb.canary.hashing import normalize_for_match

from ._defs import load_canaries

CANARIES = load_canaries()
IDS = [c["canary_id"] for c in CANARIES]


def test_exactly_the_five_plan_canaries():
    assert IDS == [f"SB-CAN-000{i}" for i in range(1, 6)]


@pytest.mark.parametrize("canary", CANARIES, ids=IDS)
def test_prompt_contains_no_anchor_or_context_term(canary):
    assert len(canary["probe_prompts"]) == 1
    prompt = normalize_for_match(canary["probe_prompts"][0])
    for registered in CANARIES:
        for term in [registered["anchor"], *registered["context_terms"]]:
            assert normalize_for_match(term) not in prompt, f"{canary['canary_id']} prompt leaks {term!r}"


@pytest.mark.parametrize("canary", CANARIES, ids=IDS)
def test_content_carries_anchor_and_context_terms(canary):
    # Correlation (§11.1) needs anchor + >=2 context terms to be matchable in the canonical content.
    content = normalize_for_match(canary["content"])
    assert normalize_for_match(canary["anchor"]) in content
    assert len(canary["context_terms"]) >= 2
    for term in canary["context_terms"]:
        assert normalize_for_match(term) in content
    assert canary["placements"]
