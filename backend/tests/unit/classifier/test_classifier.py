"""Unit tests for ScrapeBuster Phase 2 Adaptive AR Classifier.

Verifies:
1. EMA baseline calculation: AR_baseline(route) = alpha * AR_current + (1 - alpha) * AR_historical.
2. Cold start behavior: sample_count < baseline_min_samples routes to SANDBOX.
3. Genuine browser cascade: high asset ratio yields high trust score and FAST_PATH.
4. Scraper divergence: low asset ratio yields low trust score and SANDBOX.
5. Anomaly streak and sticky sandbox lock: >= 20 consecutive API calls lock to SANDBOX.
6. Sticky lock cannot be undone by subsequent static requests.
7. SB_MUTATION_MODE=always reproduces unconditional SANDBOX.
8. Classifier status metrics, latency tracking, and confidence distribution.
"""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest

from sb.classifier.classifier import ARClassifier, ClassificationResult
from sb.edge.session import Session, SessionsManager
from sb.store import db


@pytest.fixture(autouse=True)
def clean_db():
    db.reset_db()
    yield
    db.reset_db()


def test_ema_baseline_formula():
    """Verify EMA formula: AR_baseline = alpha * AR_current + (1 - alpha) * AR_historical."""
    classifier = ARClassifier()
    classifier.reset()

    # Default alpha = 0.2
    # Sample 1: first sample initializes baseline to current value (5.0)
    s1 = classifier.record_sample("/shop", 5.0)
    assert s1["sample_count"] == 1
    assert pytest.approx(s1["ar_ema"], 0.001) == 5.0

    # Sample 2: historical = 5.0, current = 5.0 -> 0.2 * 5.0 + 0.8 * 5.0 = 5.0
    s2 = classifier.record_sample("/shop", 5.0)
    assert s2["sample_count"] == 2
    assert pytest.approx(s2["ar_ema"], 0.001) == 5.0

    # Sample 3: historical = 5.0, current = 10.0 -> 0.2 * 10.0 + 0.8 * 5.0 = 2.0 + 4.0 = 6.0
    s3 = classifier.record_sample("/shop", 10.0)
    assert s3["sample_count"] == 3
    assert pytest.approx(s3["ar_ema"], 0.001) == 6.0


def test_cold_start_fails_offensive():
    """FR-2.6: Immature baseline (sample_count < 10) must route to SANDBOX."""
    classifier = ARClassifier()
    classifier.reset()

    session = Session(session_id="sess_cold_1", client_ip="127.0.0.1", user_agent="Mozilla/5.0")
    session.asset_ratio = 4.5  # High AR, but baseline has 0 samples

    res = classifier.classify_session(session, "/catalog")
    assert res.decision == "SANDBOX"
    assert res.state == "SANDBOX"
    assert res.trust_score == 0.0
    assert res.route_class == "cold_start"
    assert "COLD_START_IMMATURE_BASELINE" in res.reasons
    assert res.is_mature is False


def test_matured_baseline_browser_fast_path():
    """FR-2.2, FR-2.3: Genuine browser cascade with high AR receives FAST_PATH."""
    classifier = ARClassifier()
    classifier.reset()

    # Mature the baseline with 12 samples of AR ~ 3.0
    for _ in range(12):
        classifier.record_sample("/items", 3.0)

    baseline = classifier.get_baseline("/items")
    assert baseline["is_mature"] is True
    assert baseline["sample_count"] == 12

    session = Session(session_id="sess_browser_1", client_ip="127.0.0.1", user_agent="Mozilla/5.0")
    session.asset_ratio = 3.2  # Matches or exceeds baseline

    res = classifier.classify_session(session, "/items")
    assert res.decision == "FAST_PATH"
    assert res.state == "FAST"
    assert res.trust_score >= 70.0
    assert res.route_class == "browser_cascade"
    assert "HIGH_TRUST_ASSET_CASCADE" in res.reasons
    assert res.is_mature is True


def test_matured_baseline_scraper_divergence_sandbox():
    """Scraper harvesting API with low AR receives SANDBOX."""
    classifier = ARClassifier()
    classifier.reset()

    # Mature the baseline with 10 samples of AR ~ 4.0
    for _ in range(10):
        classifier.record_sample("/api/data", 4.0)

    session = Session(session_id="sess_scraper_1", client_ip="10.0.0.1", user_agent="curl/8.0")
    session.asset_ratio = 0.2  # Very low asset ratio compared to baseline 4.0

    res = classifier.classify_session(session, "/api/data")
    assert res.decision == "SANDBOX"
    assert res.state == "SANDBOX"
    assert res.trust_score < 70.0
    assert res.route_class == "scraper_recon"
    assert "LOW_TRUST_ASSET_DIVERGENCE" in res.reasons


def test_anomaly_streak_triggers_sticky_sandbox_lock():
    """FR-2.4: >= 20 consecutive zero-AR API calls locks into sticky SANDBOX."""
    classifier = ARClassifier()
    classifier.reset()

    # Mature the baseline
    for _ in range(12):
        classifier.record_sample("/api/users", 2.0)

    session = Session(session_id="sess_streak_1", client_ip="10.0.0.2", user_agent="Python/3.11")
    session.ar_anomaly_streak = 20
    session.asset_ratio = 2.0  # Even with high nominal AR, streak locks it

    res = classifier.classify_session(session, "/api/users")
    assert res.decision == "SANDBOX"
    assert res.locked is True
    assert res.route_class == "locked_sandbox"
    assert "SANDBOX_LOCKED_ANOMALY_STREAK" in res.reasons
    assert session.locked_sandbox is True

    # Test sticky nature: session later makes static requests, but locked flag remains
    session.asset_ratio = 5.0
    session.ar_anomaly_streak = 0  # Attempt to reset streak
    res2 = classifier.classify_session(session, "/api/users")
    assert res2.decision == "SANDBOX"
    assert res2.locked is True
    assert res2.route_class == "locked_sandbox"


def test_mutation_mode_always_forces_sandbox():
    """SB_MUTATION_MODE=always forces unconditional SANDBOX reproducing Phase 1 behavior."""
    classifier = ARClassifier()
    classifier.reset()

    # Mature the baseline
    for _ in range(15):
        classifier.record_sample("/home", 3.0)

    session = Session(session_id="sess_mode_1", client_ip="127.0.0.1", user_agent="Mozilla/5.0")
    session.asset_ratio = 3.5

    with patch.dict(os.environ, {"SB_MUTATION_MODE": "always"}):
        res = classifier.classify_session(session, "/home")
        assert res.decision == "SANDBOX"
        assert res.route_class == "forced_sandbox"
        assert "MUTATION_MODE_ALWAYS" in res.reasons


def test_classifier_status_and_metrics():
    """Verify get_status metrics reporting and latency calculation."""
    classifier = ARClassifier()
    classifier.reset()

    # Record some samples and classifications
    for _ in range(10):
        classifier.record_sample("/route1", 2.0)

    session = Session(session_id="sess_stat_1", client_ip="127.0.0.1", user_agent="Mozilla/5.0")
    session.asset_ratio = 2.5
    classifier.classify_session(session, "/route1")

    status = classifier.get_status()
    assert status["status"] == "ok"
    assert status["total_routes"] >= 1
    assert status["matured_routes"] >= 1
    assert status["metrics"]["total_evaluations"] >= 1
    assert "latency_p50_ms" in status["metrics"]
    assert "latency_p95_ms" in status["metrics"]
    assert "confidence_distribution" in status["metrics"]
