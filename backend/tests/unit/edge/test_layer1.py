"""
T-OB-2  Layer 1 table-driven tests  (INT-06 §4)
================================================
Covers: header scoring, UA scoring, rate scoring, score-band decisions,
        session state transitions, repeat-throttle, FP anomaly, rate identity.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sb.config import L1_BLOCK_TTL_SECS, L1_RATE_HARD, L1_RATE_SOFT
from sb.edge import layer1
from sb.edge.layer1 import (
    _KNOWN_LIBRARY_FPS,
    L1Result,
    band,
    reset_rate_state,
    run,
)
from sb.edge.session import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ctx(
    ua: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    headers: dict | None = None,
    ip: str = "1.2.3.4",
    path: str = "/page",
    fp: str = "ok_fp_not_in_blocklist",
    is_document: bool = True,
    cookies: dict | None = None,
    client_key: str = "deadbeef00000001",
) -> MagicMock:
    """Build a minimal RequestContext mock."""
    if headers is None:
        headers = {
            "accept": "text/html",
            "accept-language": "en-US",
            "accept-encoding": "gzip, deflate",
            "user-agent": ua,
        }
    if cookies is None:
        cookies = {}

    mock_request = MagicMock()
    mock_request.headers = headers
    mock_request.cookies = cookies

    ctx = MagicMock()
    ctx.user_agent = ua
    ctx.ip = ip
    ctx.path = path
    ctx.request = mock_request
    ctx.header_fp = fp
    ctx.is_document = is_document
    ctx.client_key = client_key
    return ctx


def _session(state: str = "NEW") -> Session:
    return Session(session_id="test-sid", client_key="deadbeef00000001", state=state)


# ---------------------------------------------------------------------------
# Score band tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("score,expected", [
    (0,   "ALLOW"),
    (29,  "ALLOW"),
    (30,  "ESCALATE"),
    (59,  "ESCALATE"),
    (60,  "THROTTLE"),
    (89,  "THROTTLE"),
    (90,  "BLOCK"),
    (100, "BLOCK"),
])
def test_band(score, expected):
    assert band(score) == expected


# ---------------------------------------------------------------------------
# Header scoring — L1_MISSING_BROWSER_HEADERS
# ---------------------------------------------------------------------------
def test_header_score_clean_browser():
    """Full browser headers → 0 header penalty."""
    ctx = _ctx()
    score, reasons = layer1._header_score(ctx)
    assert score == 0
    assert "L1_MISSING_BROWSER_HEADERS" not in reasons


def test_header_score_missing_accept_language():
    """Missing accept-language → exactly +20 (flat, not per-header)."""
    ctx = _ctx(headers={
        "accept": "text/html",
        "accept-encoding": "gzip",
        "user-agent": "Mozilla/5.0",
    })
    score, reasons = layer1._header_score(ctx)
    assert score == 20
    assert "L1_MISSING_BROWSER_HEADERS" in reasons


def test_header_score_all_missing():
    """Bare headers (only host) → exactly +20, not +30."""
    ctx = _ctx(headers={"host": "example.com"})
    score, reasons = layer1._header_score(ctx)
    assert score == 20
    assert "L1_MISSING_BROWSER_HEADERS" in reasons


# ---------------------------------------------------------------------------
# Header fingerprint anomaly — L1_HEADER_FP_ANOMALY
# ---------------------------------------------------------------------------
def test_header_fp_anomaly_real_library():
    """A real known-library fingerprint triggers L1_HEADER_FP_ANOMALY +10."""
    # python-requests canonical fingerprint
    python_requests_fp = "2d30dc89d9816360"
    assert python_requests_fp in _KNOWN_LIBRARY_FPS, "test assumes requests FP in blocklist"

    ctx = _ctx(
        headers={
            "accept": "text/html",
            "accept-language": "en-US",
            "accept-encoding": "gzip, deflate",
            "user-agent": "Mozilla/5.0",
        },
        fp=python_requests_fp,
    )
    score, reasons = layer1._header_score(ctx)
    assert score == 10
    assert "L1_HEADER_FP_ANOMALY" in reasons


def test_header_fp_anomaly_curl():
    """curl canonical FP triggers anomaly."""
    curl_fp = "0421123993515468"
    assert curl_fp in _KNOWN_LIBRARY_FPS
    ctx = _ctx(fp=curl_fp, headers={"accept": "*/*", "accept-language": "en", "accept-encoding": "gzip", "user-agent": "Mozilla/5.0"})
    _, reasons = layer1._header_score(ctx)
    assert "L1_HEADER_FP_ANOMALY" in reasons


def test_header_fp_normal_browser_no_anomaly():
    """A non-library fingerprint must NOT trigger L1_HEADER_FP_ANOMALY."""
    ctx = _ctx(fp="not_a_known_library_fp")
    _, reasons = layer1._header_score(ctx)
    assert "L1_HEADER_FP_ANOMALY" not in reasons


# ---------------------------------------------------------------------------
# User-Agent scoring — L1_AUTOMATION_UA
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ua,expect_bot", [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", False),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15", False),
    ("python-requests/2.31.0", True),
    ("Go-http-client/2.0", True),
    ("curl/7.88.1", True),
    ("Wget/1.21.3", True),
    ("Scrapy/2.11 (+https://scrapy.org)", True),
    ("AhrefsBot/7.0", True),
    ("", True),
])
def test_ua_score(ua, expect_bot):
    ctx = _ctx(ua=ua)
    score, reasons = layer1._ua_score(ctx)
    if expect_bot:
        assert score == 45, f"Expected 45 for UA '{ua}', got {score}"
        assert "L1_AUTOMATION_UA" in reasons
    else:
        assert score == 0, f"Expected 0 for UA '{ua}', got {score}"


def test_ua_empty_gives_automation_ua():
    """Empty UA must return L1_AUTOMATION_UA +45."""
    ctx = _ctx(ua="")
    score, reasons = layer1._ua_score(ctx)
    assert score == 45
    assert "L1_AUTOMATION_UA" in reasons


# ---------------------------------------------------------------------------
# Rate scoring — L1_RATE_SOFT / L1_RATE_HARD
# ---------------------------------------------------------------------------
def test_rate_clean_ip():
    reset_rate_state()
    ctx = _ctx(ip="10.0.0.1", client_key="clean0001")
    score, _ = layer1._rate_score(ctx)
    assert score == 0


def test_rate_soft_threshold():
    """After L1_RATE_SOFT document requests, next request scores +30 (L1_RATE_SOFT)."""
    reset_rate_state()
    key = "soft00001"
    ctx = _ctx(ip="10.0.0.2", client_key=key, is_document=True)
    for _ in range(L1_RATE_SOFT):
        layer1._rate_score(ctx)
    score, reasons = layer1._rate_score(ctx)
    assert score == 30
    assert "L1_RATE_SOFT" in reasons


def test_rate_hard_threshold():
    """After L1_RATE_HARD document requests, next request scores +100 (L1_RATE_HARD → BLOCK)."""
    reset_rate_state()
    key = "hard00001"
    ctx = _ctx(ip="10.0.0.3", client_key=key, is_document=True)
    for _ in range(L1_RATE_HARD):
        layer1._rate_score(ctx)
    score, reasons = layer1._rate_score(ctx)
    assert score == 100
    assert "L1_RATE_HARD" in reasons


def test_rate_static_path_does_not_count():
    """Requests to /static/* must not increment the document rate counter."""
    reset_rate_state()
    key = "statickey1"
    # Flood with static requests
    static_ctx = _ctx(ip="10.0.0.4", client_key=key, path="/static/app.js", is_document=False)
    for _ in range(L1_RATE_HARD + 10):
        layer1._rate_score(static_ctx)
    # Now send a document request — should have 0 count
    doc_ctx = _ctx(ip="10.0.0.4", client_key=key, path="/page", is_document=True)
    score, _ = layer1._rate_score(doc_ctx)
    assert score == 0, f"Static requests should not have built up rate count, got {score}"


def test_rate_sb_namespace_does_not_count():
    """Requests to /_sb/* must not increment the rate counter."""
    reset_rate_state()
    key = "sbkey0001"
    sb_ctx = _ctx(ip="10.0.0.5", client_key=key, path="/_sb/challenge/verify", is_document=False)
    for _ in range(L1_RATE_HARD + 10):
        layer1._rate_score(sb_ctx)
    doc_ctx = _ctx(ip="10.0.0.5", client_key=key, path="/page", is_document=True)
    score, _ = layer1._rate_score(doc_ctx)
    assert score == 0


def test_rate_client_key_separates_different_uas():
    """Two different UAs from the same IP must have independent rate buckets."""
    reset_rate_state()
    # UA A floods its bucket
    ctx_a = _ctx(ip="10.0.0.6", client_key="ua_a_key0", is_document=True)
    for _ in range(L1_RATE_HARD):
        layer1._rate_score(ctx_a)
    # UA B (same IP, different client_key) should be clean
    ctx_b = _ctx(ip="10.0.0.6", client_key="ua_b_key1", is_document=True)
    score_b, reasons_b = layer1._rate_score(ctx_b)
    assert score_b == 0, f"UA B should have an independent rate bucket, got {score_b}"
    assert "L1_RATE_HARD" not in reasons_b


# ---------------------------------------------------------------------------
# Repeat throttle — L1_REPEAT_THROTTLE
# ---------------------------------------------------------------------------
def test_repeat_throttle_triggers_block():
    """≥3 THROTTLE decisions in 30 s → L1_REPEAT_THROTTLE, score=100."""
    session = _session()
    now = datetime.now(timezone.utc)
    session.layer_path = [
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=5)).isoformat()},
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=10)).isoformat()},
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=15)).isoformat()},
    ]
    score, reasons = layer1._check_repeat_throttle(session)
    assert score == 100
    assert "L1_REPEAT_THROTTLE" in reasons
    assert session.block_until != "", "block_until must be set by _check_repeat_throttle"


def test_repeat_throttle_expired_decisions_not_counted():
    """THROTTLE decisions older than 30 s must not count."""
    session = _session()
    now = datetime.now(timezone.utc)
    session.layer_path = [
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=35)).isoformat()},
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=40)).isoformat()},
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=45)).isoformat()},
    ]
    score, reasons = layer1._check_repeat_throttle(session)
    assert score == 0
    assert "L1_REPEAT_THROTTLE" not in reasons


# ---------------------------------------------------------------------------
# End-to-end run() — full pipeline
# ---------------------------------------------------------------------------
def test_run_clean_browser_allows():
    """Verified session with clean browser headers → ALLOW."""
    reset_rate_state()
    ctx = _ctx()
    session = _session(state="VERIFIED")
    result = run(ctx, session)
    assert isinstance(result, L1Result)
    assert result.decision == "ALLOW"
    assert result.score < 30


def test_unverified_session_produces_escalate():
    """Non-verified document request without sb_clear → ESCALATE + L1_UNVERIFIED_SESSION."""
    reset_rate_state()
    ctx = _ctx(is_document=True)
    session = _session(state="NEW")
    result = run(ctx, session)
    assert result.decision == "ESCALATE"
    assert "L1_UNVERIFIED_SESSION" in result.reasons


def test_run_bot_ua_throttles():
    """Bot UA (+45) + missing headers (+20) = 65 → THROTTLE."""
    reset_rate_state()
    ctx = _ctx(ua="curl/7.88.1", headers={"host": "example.com"}, is_document=True,
               client_key="curlkey001")
    session = _session(state="VERIFIED")
    result = run(ctx, session)
    assert result.decision == "THROTTLE"
    assert result.score == 65
    assert "L1_AUTOMATION_UA" in result.reasons


def test_run_score_caps_at_100():
    """Score never exceeds 100."""
    reset_rate_state()
    key = "capkey001"
    ctx = _ctx(ua="", headers={"host": "example.com"}, ip="10.0.0.99",
               client_key=key, is_document=True)
    session = _session()
    for _ in range(L1_RATE_HARD + 10):
        layer1._rate_score(ctx)
    result = run(ctx, session)
    assert result.score <= 100


# ---------------------------------------------------------------------------
# Session state transitions (verify pipeline behaviour through L1Result)
# ---------------------------------------------------------------------------
def test_hard_rate_sets_block_until():
    """L1_RATE_HARD → BLOCK, block_until set ~300 s in future."""
    reset_rate_state()
    key = "hardblk01"
    ctx = _ctx(ip="10.1.1.1", client_key=key, is_document=True)
    session = _session(state="VERIFIED")
    # Exceed hard threshold
    for _ in range(L1_RATE_HARD + 1):
        layer1._rate_score(ctx)
    result = run(ctx, session)
    assert result.decision == "BLOCK"
    assert "L1_RATE_HARD" in result.reasons
    assert result.block_until != "", "L1_RATE_HARD must populate block_until"
    until = datetime.fromisoformat(result.block_until)
    delta = until - datetime.now(timezone.utc)
    # block_until should be approximately L1_BLOCK_TTL_SECS seconds from now
    assert L1_BLOCK_TTL_SECS - 5 < delta.total_seconds() <= L1_BLOCK_TTL_SECS + 5


def test_repeat_throttle_end_to_end_block():
    """L1_REPEAT_THROTTLE → BLOCK, session.block_until set ~300 s out."""
    session = _session(state="VERIFIED")
    now = datetime.now(timezone.utc)
    session.layer_path = [
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=5)).isoformat()},
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=10)).isoformat()},
        {"layer": "L1", "decision": "THROTTLE", "ts": (now - timedelta(seconds=15)).isoformat()},
    ]
    reset_rate_state()
    ctx = _ctx(client_key="rtkey001", is_document=True)
    result = run(ctx, session)
    assert result.decision == "BLOCK"
    assert "L1_REPEAT_THROTTLE" in result.reasons
    assert result.block_until != ""
    until = datetime.fromisoformat(result.block_until)
    delta = until - datetime.now(timezone.utc)
    assert L1_BLOCK_TTL_SECS - 5 < delta.total_seconds() <= L1_BLOCK_TTL_SECS + 5


@pytest.mark.parametrize(
    ("case", "ua", "headers", "fp", "prior_requests", "verified", "expected_score", "expected_decision", "reason"),
    [
        ("verified browser, low rate", "Mozilla/5.0", None, "browser_fp", 0, True, 0, "ALLOW", None),
        ("fresh browser, first response requires clearance", "Mozilla/5.0", None, "browser_fp", 0, False, 0, "ESCALATE", "L1_UNVERIFIED_SESSION"),
        ("python client fingerprint", "python-requests/2.31", {"host": "shop.test"}, "browser_fp", 0, True, 65, "THROTTLE", "L1_AUTOMATION_UA"),
        ("browser missing a required header", "Mozilla/5.0", {"accept": "text/html", "accept-encoding": "gzip"}, "browser_fp", 0, True, 20, "ALLOW", "L1_MISSING_BROWSER_HEADERS"),
        ("known library fingerprint", "Mozilla/5.0", None, "2d30dc89d9816360", 0, True, 10, "ALLOW", "L1_HEADER_FP_ANOMALY"),
        ("soft boundary, at configured count", "Mozilla/5.0", None, "browser_fp", L1_RATE_SOFT - 1, True, 0, "ALLOW", None),
        ("soft boundary, one over configured count", "Mozilla/5.0", None, "browser_fp", L1_RATE_SOFT, True, 30, "ESCALATE", "L1_RATE_SOFT"),
        ("exact throttle score boundary", "Mozilla/5.0", {"accept": "text/html", "accept-encoding": "gzip"}, "2d30dc89d9816360", L1_RATE_SOFT, True, 60, "THROTTLE", "L1_RATE_SOFT"),
        ("hard boundary, at configured count", "Mozilla/5.0", None, "browser_fp", L1_RATE_HARD - 1, True, 30, "ESCALATE", "L1_RATE_SOFT"),
        ("hard boundary, one over configured count", "Mozilla/5.0", None, "browser_fp", L1_RATE_HARD, True, 100, "BLOCK", "L1_RATE_HARD"),
    ],
)
def test_deterministic_decision_table(
    monkeypatch, case, ua, headers, fp, prior_requests, verified, expected_score, expected_decision, reason
):
    """Representative Layer 1 inputs produce stable scores, reasons and bands."""
    reset_rate_state()
    monkeypatch.setattr(layer1.time, "monotonic", lambda: 100.0)
    ctx = _ctx(
        ua=ua,
        headers=headers,
        fp=fp,
        client_key=f"table-{case}",
        is_document=True,
    )
    session = _session(state="VERIFIED" if verified else "NEW")
    for _ in range(prior_requests):
        layer1._rate_score(ctx)

    result = run(ctx, session)
    assert result.score == expected_score, case
    assert result.decision == expected_decision, case
    if reason:
        assert reason in result.reasons, case


def test_rate_window_expires_at_exact_window_boundary(monkeypatch):
    reset_rate_state()
    ticks = iter((0.0, 10.0))
    monkeypatch.setattr(layer1.time, "monotonic", lambda: next(ticks))
    ctx = _ctx(client_key="window-boundary", is_document=True)

    layer1._rate_score(ctx)
    score, reasons = layer1._rate_score(ctx)

    assert score == 0
    assert reasons == []
