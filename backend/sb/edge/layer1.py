"""
Layer 1 — Edge Defence Engine
==============================
Table-driven scoring. Inspects headers, User-Agent, and per-IP/UA request rate.
Returns a verdict: ALLOW | ESCALATE | THROTTLE | BLOCK

Score bands (INT-06 §4):
  0  –  29  → ALLOW
  30 –  59  → ESCALATE
  60 –  89  → THROTTLE  (HTTP 429, Retry-After: 10)
  90 – 100  → BLOCK     (HTTP 403, session.state = BLOCKED, block_until set)
"""

import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..config import (
    L1_BLOCK_TTL_SECS,
    L1_RATE_HARD,
    L1_RATE_SOFT,
    L1_RATE_WINDOW_SECS,
    L1_REPEAT_THROTTLE_LIMIT,
    L1_REPEAT_THROTTLE_WINDOW_SECS,
)
from ..edge.context import RequestContext
from ..edge.session import Session

# ---------------------------------------------------------------------------
# Score bands
# ---------------------------------------------------------------------------
ALLOW     = "ALLOW"
ESCALATE  = "ESCALATE"
CHALLENGE = "CHALLENGE"   # retained for backward compatibility; not emitted by L1
THROTTLE  = "THROTTLE"
BLOCK     = "BLOCK"


def band(score: int) -> str:
    if score >= 90:
        return BLOCK
    if score >= 60:
        return THROTTLE
    if score >= 30:
        return ESCALATE
    return ALLOW


# ---------------------------------------------------------------------------
# Known-bad User-Agent patterns
# ---------------------------------------------------------------------------
_UA_BOT_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"python-requests",
        r"go-http-client",
        r"curl/",
        r"wget/",
        r"scrapy",
        r"httpclient",
        r"okhttp",
        r"axios",
        r"node-fetch",
        r"libwww-perl",
        r"java/",
        r"perl",
        r"ruby",
        r"php/",
        r"aiohttp",
        r"httpx",
        r"playwright",
        r"puppeteer",
        r"selenium",
        r"headlesschrome",
        r"phantomjs",
        r"slurp",       # Yahoo
        r"bingbot",
        r"yandexbot",
        r"semrushbot",
        r"ahrefsbot",
        r"mj12bot",
        r"dotbot",
        r"rogerbot",
        r"ia_archiver",
    ]
]

# Score for a matched automation UA or empty UA (§4: L1_AUTOMATION_UA = +45)
_UA_BOT_SCORE = 45


# ---------------------------------------------------------------------------
# Header scoring
# ---------------------------------------------------------------------------

# Every genuine browser sends these three headers.
_EXPECTED_HEADERS = {"accept", "accept-language", "accept-encoding"}

# ---------------------------------------------------------------------------
# Known-library header fingerprints  (§4: L1_HEADER_FP_ANOMALY = +10)
#
# A fingerprint is sha256(lowercased header-name ORDER)[:16] for the
# exact header set each library sends by default.  Derived empirically
# from library source code / wire captures.
#
# Library                     | Header order used
# ----------------------------|---------------------------------------------------
# python-requests 2.x         | host, user-agent, accept-encoding, accept, connection
# httpx 0.x                   | host, accept, accept-encoding, connection, user-agent
# curl (minimal GET)          | host, user-agent, accept
# wget (minimal GET)          | host, user-agent, accept, accept-encoding, connection
# Go net/http (default)       | user-agent, accept-encoding
# aiohttp                     | host, accept, accept-encoding, user-agent, content-type
# scrapy                      | accept, accept-language, user-agent, accept-encoding, cookie, host
# axios (Node.js)             | accept, accept-encoding, host, user-agent, connection
# Java HttpURLConnection      | user-agent, host, accept, connection
# OkHttp 3                    | accept-encoding, user-agent, host, connection
# Puppeteer headless (no sec) | host, connection, user-agent, accept-encoding, accept-language, accept
# ---------------------------------------------------------------------------
_KNOWN_LIBRARY_FPS: frozenset[str] = frozenset({
    "2d30dc89d9816360",  # python-requests 2.x
    "e161b8ad08302eee",  # httpx 0.x
    "0421123993515468",  # curl minimal
    "cac2c496544b7302",  # wget minimal
    "fb4f949fd323be14",  # Go net/http default
    "6a32677f428b29bf",  # aiohttp
    "a4e1078151330128",  # scrapy
    "ee962c0fb0f7fef4",  # axios (Node.js)
    "1830ad44f9e11883",  # Java HttpURLConnection
    "2cf229673e600bdb",  # OkHttp3
    "6ea4a932ce2ee24a",  # Puppeteer headless (missing sec-fetch-*)
})


def _header_score(ctx: RequestContext) -> tuple[int, list[str]]:
    """Return (score_delta, reasons) based on header analysis."""
    score = 0
    reasons: list[str] = []
    names = {k.lower() for k in ctx.request.headers}

    # Missing browser essentials (§4: L1_MISSING_BROWSER_HEADERS = +20 flat)
    if _EXPECTED_HEADERS - names:
        score += 20
        reasons.append("L1_MISSING_BROWSER_HEADERS")

    # Known-library fingerprint match (§4: L1_HEADER_FP_ANOMALY = +10)
    if ctx.header_fp in _KNOWN_LIBRARY_FPS:
        score += 10
        reasons.append("L1_HEADER_FP_ANOMALY")

    return score, reasons


# ---------------------------------------------------------------------------
# User-Agent scoring
# ---------------------------------------------------------------------------
def _ua_score(ctx: RequestContext) -> tuple[int, list[str]]:
    ua = ctx.user_agent.strip()
    if not ua:
        return _UA_BOT_SCORE, ["L1_AUTOMATION_UA"]

    for pat in _UA_BOT_PATTERNS:
        if pat.search(ua):
            return _UA_BOT_SCORE, ["L1_AUTOMATION_UA"]

    return 0, []


# ---------------------------------------------------------------------------
# Per-client_key document-request rate limiting (§4)
#
# Rate is counted per client_key (sha256(ip|ua)[:16]), not per raw IP.
# Only document requests count — /static/*, /_sb/*, /favicon.ico excluded
# via ctx.is_document (set in RequestContext).
# ---------------------------------------------------------------------------
_RATE_LOCK = threading.Lock()
# client_key → list of monotonic timestamps within the window
_client_timestamps: dict[str, list[float]] = defaultdict(list)


def _rate_score(ctx: RequestContext) -> tuple[int, list[str]]:
    """Rate-score a request; non-document requests are exempt and do not count."""
    if not ctx.is_document:
        return 0, []

    now = time.monotonic()
    cutoff = now - L1_RATE_WINDOW_SECS
    key = ctx.client_key  # sha256(ip|ua)[:16] — separates UAs on same IP

    with _RATE_LOCK:
        _client_timestamps[key] = [t for t in _client_timestamps[key] if t > cutoff]
        _client_timestamps[key].append(now)
        count = len(_client_timestamps[key])

    if count > L1_RATE_HARD:
        return 100, ["L1_RATE_HARD"]
    if count > L1_RATE_SOFT:
        return 30, ["L1_RATE_SOFT"]
    return 0, []


# ---------------------------------------------------------------------------
# Repeat-throttle detection (§4: L1_REPEAT_THROTTLE)
#
# If a session accumulates ≥ L1_REPEAT_THROTTLE_LIMIT THROTTLE decisions
# within L1_REPEAT_THROTTLE_WINDOW_SECS seconds, it should be BLOCKED for
# L1_BLOCK_TTL_SECS.  We set session.block_until here so the pipeline can
# persist it; the caller must set session.state = "BLOCKED".
# ---------------------------------------------------------------------------
def _check_repeat_throttle(session: Session) -> tuple[int, list[str]]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=L1_REPEAT_THROTTLE_WINDOW_SECS)

    throttles = sum(
        1
        for p in session.layer_path
        if p.get("layer") == "L1" and p.get("decision") == "THROTTLE"
        and _parse_ts(p.get("ts")) > cutoff
    )

    if throttles >= L1_REPEAT_THROTTLE_LIMIT:
        session.block_until = (now + timedelta(seconds=L1_BLOCK_TTL_SECS)).isoformat()
        return 100, ["L1_REPEAT_THROTTLE"]

    return 0, []


def _parse_ts(ts: str | None) -> datetime:
    """Parse an ISO timestamp from layer_path safely; returns epoch on error."""
    if not ts:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@dataclass
class L1Result:
    score: int
    decision: str
    reasons: list[str] = field(default_factory=list)
    # When decision is BLOCK via a hard path, block_until is set
    block_until: str = ""


def run(ctx: RequestContext, session: Session) -> L1Result:
    """
    Execute the Layer 1 scoring pipeline.

    Decision priority (§4):
      1. L1_REPEAT_THROTTLE → BLOCK (overrides score)
      2. L1_RATE_HARD       → BLOCK (overrides score)
      3. score ≥ 90         → BLOCK
      4. score ≥ 60         → THROTTLE
      5. L1_UNVERIFIED_SESSION (document, not VERIFIED, no sb_clear) → ESCALATE
      6. score ≥ 30         → ESCALATE
      7. otherwise          → ALLOW
    """
    total = 0
    reasons: list[str] = []

    h_score, h_reasons = _header_score(ctx)
    total += h_score
    reasons.extend(h_reasons)

    ua_score, ua_reasons = _ua_score(ctx)
    total += ua_score
    reasons.extend(ua_reasons)

    r_score, r_reasons = _rate_score(ctx)
    total += r_score
    reasons.extend(r_reasons)

    total = min(total, 100)

    # ── Hard BLOCK paths ─────────────────────────────────────────────────────
    # Check repeat-throttle; this also writes block_until onto the session.
    _, rt_reasons = _check_repeat_throttle(session)
    if rt_reasons:
        reasons.extend(rt_reasons)
        return L1Result(score=100, decision=BLOCK, reasons=reasons,
                        block_until=session.block_until)

    if "L1_RATE_HARD" in reasons or total >= 90:
        # Hard rate violation or maximum score — BLOCK with TTL.
        now = datetime.now(timezone.utc)
        until = (now + timedelta(seconds=L1_BLOCK_TTL_SECS)).isoformat()
        session.block_until = until
        return L1Result(score=total, decision=BLOCK, reasons=reasons, block_until=until)

    # ── THROTTLE ─────────────────────────────────────────────────────────────
    if total >= 60:
        return L1Result(score=total, decision=THROTTLE, reasons=reasons)

    # ── Unverified-session routing (§4: L1_UNVERIFIED_SESSION) ───────────────
    # Applied to document requests whose session has not been verified and
    # has no sb_clear clearance cookie.  Not a score rule — it overrides routing.
    if (
        ctx.is_document
        and session.state not in ("VERIFIED",)
        and not ctx.request.cookies.get("sb_clear")
    ):
        reasons.append("L1_UNVERIFIED_SESSION")
        return L1Result(score=total, decision=ESCALATE, reasons=reasons)

    if total >= 30:
        return L1Result(score=total, decision=ESCALATE, reasons=reasons)

    return L1Result(score=total, decision=ALLOW, reasons=reasons)


def reset_rate_state() -> None:
    """Clear per-client rate counters.  Used by tests and demo reset."""
    with _RATE_LOCK:
        _client_timestamps.clear()
