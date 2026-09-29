"""
Layer 1 — Edge Defence Engine
==============================
Table-driven scoring. Inspects headers, User-Agent, and per-IP request rate.
Returns a verdict: ALLOW | ESCALATE | CHALLENGE | BLOCK

Score bands (INT-06):
  0  –  29  → ALLOW
  30 –  59  → ESCALATE
  60 –  89  → CHALLENGE
  90 – 100  → BLOCK
"""

import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

from ..edge.context import RequestContext

# ---------------------------------------------------------------------------
# Score bands
# ---------------------------------------------------------------------------
ALLOW     = "ALLOW"
ESCALATE  = "ESCALATE"
CHALLENGE = "CHALLENGE"
BLOCK     = "BLOCK"

def band(score: int) -> str:
    if score >= 90:
        return BLOCK
    if score >= 60:
        return CHALLENGE
    if score >= 30:
        return ESCALATE
    return ALLOW


# ---------------------------------------------------------------------------
# Known-bad / known-good User-Agent patterns
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
        r"slurp",         # Yahoo
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

_UA_EMPTY_SCORE   = 40   # missing UA is a strong signal
_UA_BOT_SCORE     = 35   # known library / known scraper UA


# ---------------------------------------------------------------------------
# Suspicious header heuristics
# ---------------------------------------------------------------------------
# Headers that a real browser always sends
_EXPECTED_HEADERS = {"accept", "accept-language", "accept-encoding"}
# Headers a headless tool often sends that real browsers don't
_HEADLESS_MARKERS = {"x-forwarded-for", "via", "forwarded"}


def _header_score(ctx: RequestContext) -> tuple[int, list[str]]:
    """Return (score_delta, reasons) based on header analysis."""
    score = 0
    reasons: list[str] = []
    names = {k.lower() for k in ctx.request.headers}

    # Missing browser essentials
    missing = _EXPECTED_HEADERS - names
    if missing:
        pts = len(missing) * 10
        score += pts
        reasons.append(f"missing_headers:{','.join(sorted(missing))}+{pts}")

    # Headless tool markers present
    present_markers = _HEADLESS_MARKERS & names
    if present_markers:
        pts = len(present_markers) * 8
        score += pts
        reasons.append(f"headless_markers:{','.join(sorted(present_markers))}+{pts}")

    return score, reasons


# ---------------------------------------------------------------------------
# User-Agent scoring
# ---------------------------------------------------------------------------
def _ua_score(ctx: RequestContext) -> tuple[int, list[str]]:
    ua = ctx.user_agent.strip()
    if not ua:
        return _UA_EMPTY_SCORE, ["ua:empty"]

    for pat in _UA_BOT_PATTERNS:
        if pat.search(ua):
            return _UA_BOT_SCORE, [f"ua:bot_pattern:{pat.pattern}"]

    return 0, []


# ---------------------------------------------------------------------------
# Per-IP rate limiting (sliding 60-second window)
# ---------------------------------------------------------------------------
_RATE_WINDOW_SECS = 60
_RATE_LOCK = threading.Lock()
# ip → deque of timestamps
_ip_timestamps: dict[str, list[float]] = defaultdict(list)

# Thresholds (requests / window)
_RATE_ESCALATE  = 40
_RATE_CHALLENGE = 80
_RATE_BLOCK     = 150


def _rate_score(ctx: RequestContext) -> tuple[int, list[str]]:
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_SECS
    ip = ctx.ip

    with _RATE_LOCK:
        ts_list = _ip_timestamps[ip]
        # Evict old entries
        _ip_timestamps[ip] = [t for t in ts_list if t > cutoff]
        _ip_timestamps[ip].append(now)
        count = len(_ip_timestamps[ip])

    if count >= _RATE_BLOCK:
        return 50, [f"rate:block_threshold:{count}req/60s"]
    if count >= _RATE_CHALLENGE:
        return 30, [f"rate:challenge_threshold:{count}req/60s"]
    if count >= _RATE_ESCALATE:
        return 15, [f"rate:escalate_threshold:{count}req/60s"]
    return 0, []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@dataclass
class L1Result:
    score: int
    decision: str
    reasons: list[str] = field(default_factory=list)


def run(ctx: RequestContext) -> L1Result:
    """
    Execute the Layer 1 scoring pipeline.
    Returns an L1Result with the total score, decision, and reason list.
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
    return L1Result(score=total, decision=band(total), reasons=reasons)


def reset_rate_state() -> None:
    """Clear per-IP rate counters. Used by tests and demo reset."""
    with _RATE_LOCK:
        _ip_timestamps.clear()
