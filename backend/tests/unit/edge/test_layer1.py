"""
T-OB-2  Layer 1 table-driven tests
===================================
Covers: header scoring, UA scoring, rate scoring, score-band decisions.
"""

from unittest.mock import MagicMock

import pytest
from sb.edge import layer1
from sb.edge.layer1 import L1Result, band, reset_rate_state, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ctx(
    ua: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    headers: dict | None = None,
    ip: str = "1.2.3.4",
    path: str = "/",
) -> MagicMock:
    """Build a minimal RequestContext mock."""
    if headers is None:
        headers = {
            "accept": "text/html",
            "accept-language": "en-US",
            "accept-encoding": "gzip, deflate",
            "user-agent": ua,
        }

    mock_request = MagicMock()
    mock_request.headers = headers

    ctx = MagicMock()
    ctx.user_agent = ua
    ctx.ip = ip
    ctx.path = path
    ctx.request = mock_request
    return ctx


# ---------------------------------------------------------------------------
# Score band tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("score,expected", [
    (0,   "ALLOW"),
    (29,  "ALLOW"),
    (30,  "ESCALATE"),
    (59,  "ESCALATE"),
    (60,  "CHALLENGE"),
    (89,  "CHALLENGE"),
    (90,  "BLOCK"),
    (100, "BLOCK"),
])
def test_band(score, expected):
    assert band(score) == expected


# ---------------------------------------------------------------------------
# Header scoring
# ---------------------------------------------------------------------------
def test_header_score_clean_browser():
    """Full browser headers → 0 header penalty."""
    ctx = _ctx()
    result = layer1._header_score(ctx)
    assert result[0] == 0
    assert result[1] == []


def test_header_score_missing_accept_language():
    """Missing accept-language adds points."""
    ctx = _ctx(headers={
        "accept": "text/html",
        "accept-encoding": "gzip",
        "user-agent": "Mozilla/5.0",
    })
    score, reasons = layer1._header_score(ctx)
    assert score > 0
    assert any("missing_headers" in r for r in reasons)


def test_header_score_all_missing():
    """Totally bare headers (only host) → high penalty."""
    ctx = _ctx(headers={"host": "example.com"})
    score, _reasons = layer1._header_score(ctx)
    assert score >= 30


def test_header_score_headless_markers():
    """Presence of headless tool markers adds points."""
    ctx = _ctx(headers={
        "accept": "text/html",
        "accept-language": "en",
        "accept-encoding": "gzip",
        "x-forwarded-for": "10.0.0.1",
        "via": "1.1 proxy",
    })
    score, reasons = layer1._header_score(ctx)
    assert score > 0
    assert any("headless_markers" in r for r in reasons)


# ---------------------------------------------------------------------------
# User-Agent scoring
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ua,expect_zero", [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", True),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15", True),
    ("python-requests/2.31.0", False),
    ("Go-http-client/2.0", False),
    ("curl/7.88.1", False),
    ("Wget/1.21.3", False),
    ("Scrapy/2.11 (+https://scrapy.org)", False),
    ("AhrefsBot/7.0", False),
    ("", False),
])
def test_ua_score(ua, expect_zero):
    ctx = _ctx(ua=ua)
    score, _reasons = layer1._ua_score(ctx)
    if expect_zero:
        assert score == 0, f"Expected 0 for UA '{ua}', got {score}"
    else:
        assert score > 0, f"Expected >0 for UA '{ua}', got {score}"


def test_ua_empty():
    ctx = _ctx(ua="")
    score, reasons = layer1._ua_score(ctx)
    assert score == layer1._UA_EMPTY_SCORE
    assert "ua:empty" in reasons


# ---------------------------------------------------------------------------
# Rate scoring
# ---------------------------------------------------------------------------
def test_rate_clean_ip():
    reset_rate_state()
    ctx = _ctx(ip="10.0.0.1")
    score, _reasons = layer1._rate_score(ctx)
    assert score == 0  # 1 request is well within limits


def test_rate_escalate_threshold():
    reset_rate_state()
    ip = "10.0.0.2"
    ctx = _ctx(ip=ip)
    # Flood up to escalate threshold
    for _ in range(layer1._RATE_ESCALATE):
        layer1._rate_score(ctx)
    score, reasons = layer1._rate_score(ctx)
    assert score > 0
    assert any("rate:" in r for r in reasons)


def test_rate_block_threshold():
    reset_rate_state()
    ip = "10.0.0.3"
    ctx = _ctx(ip=ip)
    for _ in range(layer1._RATE_BLOCK):
        layer1._rate_score(ctx)
    score, reasons = layer1._rate_score(ctx)
    assert score >= 50
    assert any("block_threshold" in r for r in reasons)


# ---------------------------------------------------------------------------
# End-to-end run() — score caps at 100
# ---------------------------------------------------------------------------
def test_run_clean_browser_allows():
    reset_rate_state()
    ctx = _ctx()
    result = run(ctx)
    assert isinstance(result, L1Result)
    assert result.decision == "ALLOW"
    assert result.score < 30


def test_run_curl_escalates_or_higher():
    reset_rate_state()
    ctx = _ctx(ua="curl/7.88.1")
    result = run(ctx)
    assert result.decision in ("ESCALATE", "CHALLENGE", "BLOCK")
    assert result.score >= 30


def test_run_empty_ua_escalates_or_higher():
    reset_rate_state()
    ctx = _ctx(ua="", headers={"host": "example.com"})
    result = run(ctx)
    # empty UA + missing browser headers → high score
    assert result.score >= 30


def test_run_score_caps_at_100():
    reset_rate_state()
    # Worst-case: empty UA + all headers missing + flooding
    ip = "10.0.0.99"
    ctx = _ctx(ua="", headers={"host": "example.com"}, ip=ip)
    for _ in range(layer1._RATE_BLOCK + 10):
        layer1._rate_score(ctx)
    result = run(ctx)
    assert result.score <= 100
