"""T-AS-1 (scraper 2 vs Layer 2) and T-NEG-1 (scrapers 1/2 harvest no canaries). Master plan §5, §19."""
from __future__ import annotations

import re

import pytest

ANCHORS = ("Oriel Vantrask", "Hexaquorum", "quasar-reconcile", "velvet-anchor", "ORCHID-7")
RESET_DEPS = ("sb.main", "sb.store.db", "sb.hooks", "sb.canary.seed", "sb.trap.layer3", "sb.provenance.dataset")
REASON = re.compile(r"^L\d_[A-Z0-9_]+$")


def reason_codes(obj) -> set[str]:
    """Every reason-code string anywhere in an API payload (field names are owner-defined)."""
    if isinstance(obj, str):
        return {obj} if REASON.match(obj) else set()
    if isinstance(obj, dict):
        return set().union(set(), *(reason_codes(v) | reason_codes(k) for k, v in obj.items()))
    if isinstance(obj, list):
        return set().union(set(), *(reason_codes(v) for v in obj))
    return set()


@pytest.mark.browser
@pytest.mark.requires(*RESET_DEPS, "sb.edge.pipeline", "sb.edge.layer1", "sb.edge.layer2", "sb.edge.intel")
def test_advanced_scraper_is_challenged_then_restricted(api, reset, attack, wait_for, site):
    out = attack("advanced_scraper.py", "--site", site, "--pages", "6")
    ua = out["user_agent"]
    assert "HeadlessChrome" in ua, "scraper 2 must run default headless Chromium"

    session = wait_for(
        lambda: next((s for s in api.sessions()
                      if s.get("user_agent") == ua and s.get("classification") == "AUTOMATION"), None),
        15, what="scraper 2 session classified AUTOMATION",
    )
    assert session.get("state") == "RESTRICTED", session

    events = sorted((e for e in api.events() if e["user_agent"] == ua), key=lambda e: e["seq"])
    decisions = [e["decision"] for e in events]
    assert "CHALLENGE" in decisions, decisions
    assert "RESTRICT" in decisions, decisions
    assert decisions.index("CHALLENGE") < decisions.index("RESTRICT"), decisions

    reasons = reason_codes(events) | reason_codes(api.session(session["session_id"]))
    assert {"L2_WEBDRIVER", "L2_HEADLESS_UA"} <= reasons, sorted(reasons)

    assert out["content_pages"] == 0, out["pages"]
    assert out["anchors_found"] == [], "T-NEG-1: scraper 2 harvested canaries"


@pytest.mark.requires(*RESET_DEPS, "sb.edge.pipeline", "sb.edge.layer1")
def test_ordinary_bot_harvests_no_canaries(api, reset, attack, site):
    """T-NEG-1 for scraper 1: whatever it receives contains no anchor."""
    out = attack("ordinary_bot.py", "--site", site, "--requests", "100", "--threads", "10")
    assert out["anchors_found"] == [], out
    assert out["content_bodies"] == 0, out["status_histogram"]
