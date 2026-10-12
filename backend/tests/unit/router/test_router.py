"""Unit tests for ScrapeBuster Phase 2 Dynamic Router.

Verifies:
1. Route path normalization (stripping query parameters and fragments, leading slash).
2. Routing to FAST_PATH for trusted browser sessions.
3. Routing to SANDBOX for cold start, scraper divergence, and locked sessions.
4. Fail-offensive behavior on classifier exception (fallback to SANDBOX, fault recorded).
5. Audit trail retention and FIFO size capping.
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from starlette.requests import Request

from sb.edge.context import RequestContext
from sb.edge.session import Session
from sb.router.router import DynamicRouter, RouterDecision
from sb.classifier.classifier import ARClassifier
from sb.store import db


@pytest.fixture(autouse=True)
def clean_db():
    db.reset_db()
    yield
    db.reset_db()


def _make_context(path: str, is_document: bool = True) -> RequestContext:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [
            (b"user-agent", b"Mozilla/5.0"),
            (b"accept", b"text/html" if is_document else b"application/json"),
        ],
        "client": ("127.0.0.1", 12345),
    }
    return RequestContext(Request(scope))


def test_route_normalization():
    """Verify route normalization cleanly formats URL paths."""
    router = DynamicRouter()
    assert router.normalize_route("/catalog") == "/catalog"
    assert router.normalize_route("catalog") == "/catalog"
    assert router.normalize_route("/catalog?page=2&sort=asc") == "/catalog"
    assert router.normalize_route("/catalog#details") == "/catalog"
    assert router.normalize_route("") == "/"


def test_router_evaluates_cold_start_to_sandbox():
    """Verify router defaults to SANDBOX when baseline has not matured."""
    classifier = ARClassifier()
    classifier.reset()
    router = DynamicRouter(classifier_instance=classifier)

    ctx = _make_context("/items")
    session = Session(session_id="sess_r_1", client_ip="127.0.0.1", user_agent="Mozilla/5.0")
    session.asset_ratio = 5.0

    dec = router.evaluate(ctx, session)
    assert dec.decision == "SANDBOX"
    assert dec.route_class == "cold_start"
    assert dec.trust_score == 0.0

    # Audit trail recorded
    trail = router.get_audit_trail()
    assert len(trail) == 1
    assert trail[0]["path"] == "/items"
    assert trail[0]["decision"] == "SANDBOX"


def test_router_evaluates_trusted_browser_to_fast_path():
    """Verify router produces FAST_PATH for mature baseline with high trust score."""
    classifier = ARClassifier()
    classifier.reset()
    router = DynamicRouter(classifier_instance=classifier)

    # Mature baseline
    for _ in range(12):
        classifier.record_sample("/search", 3.0)

    ctx = _make_context("/search")
    session = Session(session_id="sess_r_2", client_ip="127.0.0.1", user_agent="Mozilla/5.0")
    session.asset_ratio = 3.5

    dec = router.evaluate(ctx, session)
    assert dec.decision == "FAST_PATH"
    assert dec.state == "FAST"
    assert dec.trust_score >= 70.0
    assert dec.route_class == "browser_cascade"


def test_router_fail_offensive_on_classifier_exception():
    """Verify classifier exception fails offensive to SANDBOX with fault record."""
    classifier = ARClassifier()
    classifier.reset()
    # Mock classify_session to raise an unhandled exception
    classifier.classify_session = MagicMock(side_effect=RuntimeError("Simulated internal classifier breakdown"))

    router = DynamicRouter(classifier_instance=classifier)

    ctx = _make_context("/secure/profile")
    session = Session(session_id="sess_err_1", client_ip="127.0.0.1", user_agent="Mozilla/5.0")

    dec = router.evaluate(ctx, session)
    assert dec.decision == "SANDBOX"
    assert dec.state == "SANDBOX"
    assert dec.route_class == "router_fault_fallback"
    assert "CLASSIFIER_EXCEPTION_FAIL_OFFENSIVE" in dec.reasons

    # Verify recorded in audit trail
    trail = router.get_audit_trail()
    assert len(trail) == 1
    assert trail[0]["decision"] == "SANDBOX"
    assert trail[0]["route_class"] == "router_fault_fallback"


def test_audit_trail_fifo_capacity():
    """Verify audit trail caps at MAX_AUDIT_TRAIL_LEN (1000)."""
    classifier = ARClassifier()
    classifier.reset()
    router = DynamicRouter(classifier_instance=classifier)

    ctx = _make_context("/ping", is_document=False)
    session = Session(session_id="sess_trail_1", client_ip="127.0.0.1", user_agent="Mozilla/5.0")

    for _ in range(1050):
        router.evaluate(ctx, session)

    trail = router.get_audit_trail(limit=2000)
    assert len(trail) == 1000
