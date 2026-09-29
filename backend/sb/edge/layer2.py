"""
Layer 2 — Behavioral / Automation Verification  (INT-07, §5)
=============================================================
Flow:
  1. ESCALATE from L1  →  pipeline calls generate_interstitial()
     → HTTP 200 HTML page that loads /_sb/challenge.js
  2. challenge.js collects 8 signals, solves PoW, POSTs to /_sb/verify
  3. Server verifies challenge, scores signals, applies band:
       < 40  → PASS   (VERIFIED, sb_clear HMAC cookie)
       40–69 → TRAP   (silent PASS response; session TRAPPED)
       ≥ 70  → RESTRICT (403 restricted page on all future requests)
  4. L2_NO_JS: ≥ 3 interstitials in 60 s without any verify → RESTRICT

Challenge formula: sha256(challenge_id + ":" + nonce)
                   first 14 bits must be zero, i.e. int(hex[:4],16) < 4
"""

import base64
import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass, field

from fastapi import Response

from ..config import (
    L2_CHALLENGE_TTL_SECS,
    L2_CLEARANCE_TTL_SECS,
    L2_NO_JS_LIMIT,
    L2_NO_JS_WINDOW_SECS,
    L2_POW_ZERO_BITS,
    SB_SECRET,
)
from .session import Session

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Canonical verify endpoint (§5)
VERIFY_PATH = "/_sb/verify"

# PoW: 14 leading zero bits  ≡  int(hexdigest[:4], 16) < 4
# Explanation: 14 bits = 0b00_0000_0000_0000XX → first hex nibble and a half
# all zero, i.e. the first 16-bit value < 0x0004 = 4.
_POW_THRESHOLD = 1 << (16 - L2_POW_ZERO_BITS)   # = 4 when L2_POW_ZERO_BITS=14

# Legacy name exposed for tests that import it directly
POW_DIFFICULTY = "pow14bit"   # descriptive tag; not a prefix string any more

# L2 signal score bands
_BAND_PASS = 40         # < 40 → PASS
_BAND_RESTRICT = 70     # >= 70 → RESTRICT  (40–69 → TRAP)

# Cookie name
_COOKIE_NAME = "sb_clear"


# ---------------------------------------------------------------------------
# Signal scoring (§5 table)
# ---------------------------------------------------------------------------
SIGNAL_WEIGHTS: dict[str, int] = {
    "L2_WEBDRIVER":      50,
    "L2_HEADLESS_UA":    40,
    "L2_UA_MISMATCH":    25,
    "L2_ZERO_VIEWPORT":  15,
    "L2_SOFTWARE_GL":    15,
    "L2_NO_LANGUAGES":   10,
    "L2_NO_INTERACTION": 20,
    "L2_FAST_SUBMIT":    10,
}


def score_signals(signals: dict, request_ua: str, elapsed_ms: float) -> tuple[int, list[str]]:
    """
    Score client-reported signal dict against §5 weights.
    Returns (total_score, reason_codes).

    signals keys (from challenge.js):
        webdriver, headlessChrome, uaMismatch, outerWidth, outerHeight,
        softwareGL, languages, mousemove, scroll, keydown, elapsed_ms
    """
    score = 0
    reasons: list[str] = []

    if signals.get("webdriver"):
        score += SIGNAL_WEIGHTS["L2_WEBDRIVER"]
        reasons.append("L2_WEBDRIVER")

    if signals.get("headlessChrome"):
        score += SIGNAL_WEIGHTS["L2_HEADLESS_UA"]
        reasons.append("L2_HEADLESS_UA")

    # UA mismatch: JS navigator.userAgent ≠ request UA header
    js_ua = signals.get("navigatorUA", "")
    if js_ua and request_ua and js_ua.strip() != request_ua.strip():
        score += SIGNAL_WEIGHTS["L2_UA_MISMATCH"]
        reasons.append("L2_UA_MISMATCH")

    # Zero outer viewport
    outer_w = signals.get("outerWidth", 1)
    outer_h = signals.get("outerHeight", 1)
    if outer_w == 0 or outer_h == 0:
        score += SIGNAL_WEIGHTS["L2_ZERO_VIEWPORT"]
        reasons.append("L2_ZERO_VIEWPORT")

    if signals.get("softwareGL"):
        score += SIGNAL_WEIGHTS["L2_SOFTWARE_GL"]
        reasons.append("L2_SOFTWARE_GL")

    # navigator.languages empty
    langs = signals.get("languages", None)
    if langs is not None and (not langs or langs == [] or langs == ""):
        score += SIGNAL_WEIGHTS["L2_NO_LANGUAGES"]
        reasons.append("L2_NO_LANGUAGES")

    # Zero interaction events in observation window
    no_interaction = (
        signals.get("mousemove", 0) == 0
        and signals.get("scroll", 0) == 0
        and signals.get("keydown", 0) == 0
    )
    if no_interaction:
        score += SIGNAL_WEIGHTS["L2_NO_INTERACTION"]
        reasons.append("L2_NO_INTERACTION")

    # Suspiciously fast submit (< 300 ms after load with no events)
    if elapsed_ms > 0 and elapsed_ms < 300 and no_interaction:
        score += SIGNAL_WEIGHTS["L2_FAST_SUBMIT"]
        reasons.append("L2_FAST_SUBMIT")

    return score, reasons


# ---------------------------------------------------------------------------
# Clearance cookie  (§5: HMAC-SHA256(SB_SECRET))
# ---------------------------------------------------------------------------

def _hmac_sign(payload: str) -> str:
    return hmac.new(
        SB_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def issue_clearance_cookie(client_key: str, score: int) -> tuple[str, str]:
    """
    Build sb_clear cookie value and Set-Cookie header string.

    Format: base64url(client_key|exp_epoch|score) + "." + HMAC
    The HMAC covers the encoded payload so it cannot be forged.
    Returns (cookie_value, set_cookie_header_string).
    """
    exp = int(time.time()) + L2_CLEARANCE_TTL_SECS
    raw = f"{client_key}|{exp}|{score}"
    encoded = base64.urlsafe_b64encode(raw.encode()).decode()
    sig = _hmac_sign(encoded)
    value = f"{encoded}.{sig}"
    # Build Set-Cookie string: HttpOnly, SameSite=Lax, max-age
    header = (
        f"{_COOKIE_NAME}={value}; HttpOnly; SameSite=Lax; "
        f"Max-Age={L2_CLEARANCE_TTL_SECS}; Path=/"
    )
    return value, header


def validate_clearance(cookie_value: str, client_key: str) -> bool:
    """
    Validate sb_clear cookie. Returns True iff:
    - HMAC matches (not tampered)
    - Not expired
    - Bound to this client_key
    """
    if not cookie_value:
        return False
    try:
        encoded, sig = cookie_value.rsplit(".", 1)
    except ValueError:
        return False

    # Constant-time HMAC check
    expected_sig = _hmac_sign(encoded)
    if not hmac.compare_digest(sig, expected_sig):
        return False

    import binascii
    try:
        raw = base64.urlsafe_b64decode(encoded.encode()).decode()
        ck, exp_str, _ = raw.split("|", 2)
    except (ValueError, TypeError, binascii.Error):
        return False

    if ck != client_key:
        return False

    return int(time.time()) <= int(exp_str)


# ---------------------------------------------------------------------------
# PoW verification
# ---------------------------------------------------------------------------

def _pow_valid(challenge_id: str, nonce: str) -> bool:
    """
    §5: sha256(challenge_id + ":" + nonce) must have 14 leading zero bits.
    14 zero bits  ↔  int(hexdigest[:4], 16) < _POW_THRESHOLD (= 4).
    """
    digest = hashlib.sha256(f"{challenge_id}:{nonce}".encode()).hexdigest()
    return int(digest[:4], 16) < _POW_THRESHOLD


# ---------------------------------------------------------------------------
# Challenge store
# ---------------------------------------------------------------------------

@dataclass
class Challenge:
    challenge_id: str
    session_id: str
    client_key: str
    issued_at: float = field(default_factory=time.time)
    used: bool = False

    @property
    def expiry(self) -> float:
        return self.issued_at + L2_CHALLENGE_TTL_SECS

    def is_expired(self) -> bool:
        return time.time() > self.expiry

    def is_valid_for(self, session: Session) -> bool:
        return (
            self.session_id == session.session_id
            and self.client_key == session.client_key
            and not self.is_expired()
            and not self.used
        )


class ChallengeStore:
    def __init__(self) -> None:
        self._challenges: dict[str, Challenge] = {}
        # client_key → list of (issued_at,) for L2_NO_JS tracking
        self._interstitial_times: dict[str, list[float]] = {}

    def create(self, session: Session) -> Challenge:
        cid = f"ch-{uuid.uuid4().hex}"
        c = Challenge(
            challenge_id=cid,
            session_id=session.session_id,
            client_key=session.client_key,
        )
        self._challenges[cid] = c

        # Track interstitial count for L2_NO_JS
        now = time.time()
        cutoff = now - L2_NO_JS_WINDOW_SECS
        times = self._interstitial_times.setdefault(session.client_key, [])
        times[:] = [t for t in times if t > cutoff]
        times.append(now)
        return c

    def get(self, challenge_id: str) -> Challenge | None:
        return self._challenges.get(challenge_id)

    def interstitial_count(self, client_key: str) -> int:
        """Return number of interstitials served in the L2_NO_JS window."""
        now = time.time()
        cutoff = now - L2_NO_JS_WINDOW_SECS
        times = self._interstitial_times.get(client_key, [])
        return sum(1 for t in times if t > cutoff)

    def reset(self) -> None:
        self._challenges.clear()
        self._interstitial_times.clear()


store = ChallengeStore()


# ---------------------------------------------------------------------------
# L2_NO_JS check
# ---------------------------------------------------------------------------

def check_no_js(session: Session) -> bool:
    """Return True if this session should be RESTRICTED due to L2_NO_JS."""
    return store.interstitial_count(session.client_key) >= L2_NO_JS_LIMIT


# ---------------------------------------------------------------------------
# Interstitial response  (§5: HTTP 200)
# ---------------------------------------------------------------------------

def generate_interstitial(session: Session) -> Response:
    """
    Serve a 200 OK interstitial page that:
    - Loads the bundled pure-JS sha256 from /_sb/challenge.js
    - Embeds CHALLENGE_ID, RETURN_TO in script vars
    - Collects 8 signals, solves PoW, POSTs to /_sb/verify
    """
    # L2_NO_JS guard: if already 3+ interstitials with no verify, RESTRICT
    if check_no_js(session):
        session.state = "RESTRICTED"
        return _restricted_response(["L2_NO_JS"])

    challenge = store.create(session)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Checking your browser\u2026</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; background: #f4f6f9; margin: 0;
        }}
        .box {{
            background: #fff; padding: 2.5rem; border-radius: 10px;
            box-shadow: 0 4px 16px rgba(0,0,0,.1); text-align: center;
            max-width: 380px; width: 100%;
        }}
        .spinner {{
            border: 3px solid #e0e0e0; border-top-color: #4a90e2;
            border-radius: 50%; width: 36px; height: 36px;
            animation: spin 0.8s linear infinite; margin: 1.2rem auto;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        #status {{ color: #666; font-size: 0.85rem; margin-top: 0.5rem; }}
    </style>
</head>
<body>
<div class="box">
    <h2>Checking your browser\u2026</h2>
    <div class="spinner"></div>
    <div id="status">Please wait</div>
</div>
<script>
    /* Injected by ScapeBusters Layer 2 */
    const SB_CHALLENGE_ID = "{challenge.challenge_id}";
    const SB_RETURN_TO    = window.location.href;
    const SB_LOAD_TIME    = Date.now();
    const SB_POW_BITS     = {L2_POW_ZERO_BITS};
</script>
<script src="/_sb/challenge.js"></script>
</body>
</html>"""

    return Response(content=html, media_type="text/html", status_code=200)


# ---------------------------------------------------------------------------
# RESTRICT response helper
# ---------------------------------------------------------------------------

def _restricted_response(reasons: list[str]) -> Response:
    body = (
        "<!DOCTYPE html><html><head><title>Access Restricted</title></head>"
        "<body><h1>403 Restricted</h1>"
        "<p>Your access has been restricted by the security system.</p>"
        "</body></html>"
    )
    return Response(content=body, media_type="text/html", status_code=403)


# ---------------------------------------------------------------------------
# Verify endpoint logic
# ---------------------------------------------------------------------------

@dataclass
class L2Result:
    band: str          # "PASS" | "TRAP" | "RESTRICT"
    score: int
    reasons: list[str]
    clearance_cookie: str = ""   # Set-Cookie header value when band=="PASS"


def verify_submission(
    challenge_id: str,
    nonce: str,
    signals: dict,
    session: Session,
    request_ua: str,
    elapsed_ms: float,
) -> L2Result:
    """
    Full L2 verification flow.  Returns L2Result with band decision.
    Marks the challenge used to prevent replay.
    """
    challenge = store.get(challenge_id)

    # Validate challenge existence, ownership, TTL, replay
    if not challenge:
        return L2Result(band="RESTRICT", score=100, reasons=["L2_POW_INVALID"],
                        clearance_cookie="")
    if not challenge.is_valid_for(session):
        # Already used or wrong session/client_key or expired
        return L2Result(band="RESTRICT", score=100, reasons=["L2_POW_INVALID"],
                        clearance_cookie="")

    # Mark used before PoW check (single-attempt per challenge)
    challenge.used = True

    # Verify PoW: sha256(challenge_id + ":" + nonce), 14 zero bits
    if not _pow_valid(challenge.challenge_id, nonce):
        return L2Result(band="RESTRICT", score=100, reasons=["L2_POW_INVALID"],
                        clearance_cookie="")

    # Score signals
    score, reasons = score_signals(signals, request_ua, elapsed_ms)

    # Apply bands
    if score >= _BAND_RESTRICT:
        return L2Result(band="RESTRICT", score=score, reasons=reasons)

    if score >= _BAND_PASS:
        # TRAP: silent pass — tell client it passed; session marked TRAPPED upstream
        return L2Result(band="TRAP", score=score, reasons=reasons)

    # PASS: issue sb_clear clearance cookie
    _, set_cookie_header = issue_clearance_cookie(session.client_key, score)
    return L2Result(
        band="PASS",
        score=score,
        reasons=reasons,
        clearance_cookie=set_cookie_header,
    )


# ---------------------------------------------------------------------------
# Legacy compat shim (for existing tests that call layer2.verify directly)
# ---------------------------------------------------------------------------

def verify(challenge_id: str, nonce: str, session: Session) -> bool:
    """
    Simplified verify for backward compat / unit tests.
    Returns True iff challenge is valid and PoW passes.
    Does NOT apply signal scoring (no signals provided).
    """
    challenge = store.get(challenge_id)
    if not challenge:
        return False
    if challenge.session_id != session.session_id:
        return False
    if challenge.is_expired():
        return False
    if challenge.used:
        return False
    challenge.used = True
    if not nonce:
        return False
    return _pow_valid(challenge.challenge_id, nonce)


# ---------------------------------------------------------------------------
# Backward compat alias (old tests used generate_challenge_response)
# ---------------------------------------------------------------------------

def generate_challenge_response(session: Session) -> Response:
    """Alias kept for pipeline compat; delegates to generate_interstitial."""
    return generate_interstitial(session)
