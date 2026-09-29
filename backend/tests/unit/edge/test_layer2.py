import hashlib
import time
from pathlib import Path

import pytest
from sb.edge import layer2
from sb.edge.session import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_solution(challenge_id: str) -> str:
    ans = 0
    threshold = 1 << (16 - layer2.L2_POW_ZERO_BITS)
    while True:
        text = f"{challenge_id}:{ans}"
        digest = hashlib.sha256(text.encode()).hexdigest()
        if int(digest[:4], 16) < threshold:
            return str(ans)
        ans += 1

@pytest.fixture(autouse=True)
def reset_store():
    layer2.store.reset()

def _create_session(sid="sess-1") -> Session:
    return Session(session_id=sid, client_key="ck-1")


def _browser_signals(**overrides) -> dict:
    return {
        "webdriver": False,
        "headlessChrome": False,
        "navigatorUA": "RealUA",
        "outerWidth": 1280,
        "outerHeight": 800,
        "softwareGL": False,
        "languages": ["en-US"],
        "mousemove": 4,
        "scroll": 1,
        "keydown": 1,
        **overrides,
    }

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_challenge_generation():
    session = _create_session()
    c = layer2.store.create(session)
    assert c.challenge_id.startswith("ch-")
    assert c.session_id == session.session_id
    assert c.expiry > time.time()
    assert not c.used
    assert layer2.store.get(c.challenge_id) == c

def test_correct_pow():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.challenge_id)
    
    assert layer2.verify(c.challenge_id, solution, session) is True
    assert c.used is True

def test_incorrect_pow():
    session = _create_session()
    c = layer2.store.create(session)
    assert layer2.verify(c.challenge_id, "wrong_answer", session) is False
    assert c.used is True

def test_expired_challenge():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.challenge_id)
    
    c.issued_at = time.time() - 100  # Expired (TTL 60)
    
    assert layer2.verify(c.challenge_id, solution, session) is False

def test_unknown_challenge():
    session = _create_session()
    assert layer2.verify("unknown", "0", session) is False

def test_wrong_session():
    session = _create_session("sess-1")
    c = layer2.store.create(session)
    solution = _find_solution(c.challenge_id)
    
    attacker_session = _create_session("sess-2")
    assert layer2.verify(c.challenge_id, solution, attacker_session) is False

def test_replay_protection():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.challenge_id)
    
    assert layer2.verify(c.challenge_id, solution, session) is True
    assert layer2.verify(c.challenge_id, solution, session) is False

def test_generate_interstitial():
    session = _create_session()
    resp = layer2.generate_interstitial(session)
    
    assert resp.status_code == 200
    html = resp.body.decode()
    assert "Checking your browser" in html
    assert "SB_CHALLENGE_ID" in html
    assert "SB_POW_BITS" in html

def test_signal_scoring_human():
    # Human - fast interact, no bad flags
    signals = {"mousemove": 10, "keydown": 2}
    score, _ = layer2.score_signals(signals, "RealUA", 2000)
    assert score == 0

def test_signal_scoring_headless():
    signals = {"headlessChrome": True, "mousemove": 0}
    score, reasons = layer2.score_signals(signals, "RealUA", 2000)
    assert score == layer2.SIGNAL_WEIGHTS["L2_HEADLESS_UA"] + layer2.SIGNAL_WEIGHTS["L2_NO_INTERACTION"]
    assert "L2_HEADLESS_UA" in reasons
    assert "L2_NO_INTERACTION" in reasons

def test_l2_no_js_restriction():
    session = _create_session()
    # Serve 3 interstitials
    layer2.generate_interstitial(session)
    layer2.generate_interstitial(session)
    layer2.generate_interstitial(session)
    
    # Fourth should RESTRICT
    resp = layer2.generate_interstitial(session)
    assert resp.status_code == 403
    assert session.state == "RESTRICTED"

def test_verify_submission_pass():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.challenge_id)
    
    res = layer2.verify_submission(c.challenge_id, solution, _browser_signals(), session, "RealUA", 2000)
    assert res.band == "PASS"
    assert res.score == 0
    assert "sb_clear=" in res.clearance_cookie

def test_verify_submission_trap(monkeypatch):
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.challenge_id)
    monkeypatch.setattr(layer2.time, "time", lambda: c.issued_at + 2)
    
    # headlessChrome (+40) + no interactions (+20) = 60 (TRAP band 40-69)
    res = layer2.verify_submission(
        c.challenge_id,
        solution,
        _browser_signals(headlessChrome=True, mousemove=0, scroll=0, keydown=0),
        session,
        "RealUA",
        2000,
    )
    assert res.band == "TRAP"
    assert res.score == 60


@pytest.mark.parametrize(
    ("profile", "signals", "expected_band", "expected_score", "reasons"),
    [
        (
            "supported human browser",
            {"webdriver": False, "headlessChrome": False, "navigatorUA": "Browser/1", "outerWidth": 1280,
             "outerHeight": 800, "softwareGL": False, "languages": ["en-US"], "mousemove": 4,
             "scroll": 1, "keydown": 1},
            "PASS", 0, set(),
        ),
        (
            "headless Playwright",
            {"webdriver": True, "headlessChrome": True, "navigatorUA": "HeadlessChrome/1",
             "outerWidth": 1280, "outerHeight": 800, "softwareGL": False, "languages": ["en-US"],
             "mousemove": 0, "scroll": 0, "keydown": 0},
            "RESTRICT", 100, {"L2_WEBDRIVER", "L2_HEADLESS_UA"},
        ),
        (
            "stealth-like sophisticated profile",
            {"webdriver": False, "headlessChrome": False, "navigatorUA": "Browser/1", "outerWidth": 1280,
             "outerHeight": 800, "softwareGL": False, "languages": ["en-US"], "mousemove": 3,
             "scroll": 1, "keydown": 1},
            "PASS", 0, set(),
        ),
        (
            "sophisticated but trap-eligible profile",
            {"webdriver": False, "headlessChrome": False, "navigatorUA": "Browser/1", "outerWidth": 1280,
             "outerHeight": 800, "softwareGL": True, "languages": [], "mousemove": 0,
             "scroll": 0, "keydown": 0},
            "TRAP", 45, {"L2_SOFTWARE_GL", "L2_NO_LANGUAGES", "L2_NO_INTERACTION"},
        ),
    ],
)
def test_behavioral_profile_decision_matrix(monkeypatch, profile, signals, expected_band, expected_score, reasons):
    session = _create_session(profile)
    challenge = layer2.store.create(session)
    solution = _find_solution(challenge.challenge_id)
    monkeypatch.setattr(layer2.time, "time", lambda: challenge.issued_at + 2)

    result = layer2.verify_submission(
        challenge.challenge_id, solution, signals, session, "Browser/1" if profile != "headless Playwright" else "HeadlessChrome/1", 2500
    )

    assert result.band == expected_band, profile
    assert result.score == expected_score, profile
    assert reasons <= set(result.reasons), profile


@pytest.mark.parametrize(
    ("challenge_kind", "expected_reason"),
    [
        ("unknown", "L2_CHALLENGE_UNKNOWN"),
        ("expired", "L2_CHALLENGE_EXPIRED"),
        ("replayed", "L2_CHALLENGE_REPLAY"),
        ("wrong-session", "L2_CHALLENGE_SESSION_MISMATCH"),
        ("wrong-client", "L2_CHALLENGE_SESSION_MISMATCH"),
    ],
)
def test_challenge_rejections_have_stable_reasons(challenge_kind, expected_reason):
    session = _create_session("owner")
    challenge = layer2.store.create(session)
    challenge_id = "unknown-challenge"
    if challenge_kind != "unknown":
        challenge_id = challenge.challenge_id
    if challenge_kind == "expired":
        challenge.issued_at = time.time() - layer2.L2_CHALLENGE_TTL_SECS
    elif challenge_kind == "replayed":
        challenge.used = True
    elif challenge_kind == "wrong-session":
        session = _create_session("other-session")
    elif challenge_kind == "wrong-client":
        session = Session(session_id="owner", client_key="other-client")

    result = layer2.verify_submission(challenge_id, "0", {}, session, "Browser/1")

    assert result.band == "RESTRICT"
    assert result.reasons == [expected_reason]


def test_invalid_pow_consumes_challenge_and_blocks_replay():
    session = _create_session()
    challenge = layer2.store.create(session)

    invalid = layer2.verify_submission(challenge.challenge_id, "bad", {}, session, "Browser/1")
    replay = layer2.verify_submission(challenge.challenge_id, "bad", {}, session, "Browser/1")

    assert invalid.reasons == ["L2_POW_INVALID"]
    assert replay.reasons == ["L2_CHALLENGE_REPLAY"]


def test_malformed_signals_are_restricted_with_reason():
    score, reasons = layer2.score_signals({"webdriver": "false", "mousemove": "many"}, "Browser/1", 2000)

    assert score >= layer2.SIGNAL_WEIGHTS["L2_SIGNAL_INVALID"]
    assert "L2_SIGNAL_INVALID" in reasons


def test_missing_required_signals_are_restricted():
    session = _create_session()
    challenge = layer2.store.create(session)
    solution = _find_solution(challenge.challenge_id)

    result = layer2.verify_submission(
        challenge.challenge_id, solution, {}, session, "RealUA", 2000
    )

    assert result.band == "RESTRICT"
    assert result.reasons == ["L2_SIGNAL_INVALID"]


def test_challenge_expires_at_exact_ttl_boundary(monkeypatch):
    session = _create_session()
    challenge = layer2.store.create(session)
    monkeypatch.setattr(layer2.time, "time", lambda: challenge.expiry)

    assert challenge.is_expired()


def test_server_elapsed_time_drives_fast_submit(monkeypatch):
    session = _create_session()
    challenge = layer2.store.create(session)
    solution = _find_solution(challenge.challenge_id)
    monkeypatch.setattr(layer2.time, "time", lambda: challenge.issued_at + 0.1)

    result = layer2.verify_submission(
        challenge.challenge_id,
        solution,
        _browser_signals(navigatorUA="Browser/1", mousemove=0, scroll=0, keydown=0),
        session,
        "Browser/1",
        5000,
    )

    assert "L2_FAST_SUBMIT" in result.reasons


def test_clearance_is_bound_and_expires(monkeypatch):
    monkeypatch.setattr(layer2.time, "time", lambda: 1000)
    value, _ = layer2.issue_clearance_cookie("client-a", 0)
    assert layer2.validate_clearance(value, "client-a")
    assert not layer2.validate_clearance(value, "client-b")

    expiry = int(layer2.L2_CLEARANCE_TTL_SECS + 1000)
    monkeypatch.setattr(layer2.time, "time", lambda: expiry)
    assert not layer2.validate_clearance(value, "client-a")


def test_interstitial_marker_matches_attack_driver_protocol():
    response = layer2.generate_interstitial(_create_session())
    html = response.body.decode()

    assert "Checking your browser" in html
    assert '<script src="/_sb/challenge.js"></script>' in html
    root = Path(layer2.__file__).resolve().parents[3]
    attack_helper = (root / "attacks" / "common.py").read_text(encoding="utf-8")
    assert 'INTERSTITIAL_MARKER = "Checking your browser"' in attack_helper
    script = Path(layer2.__file__).parent / "static" / "challenge.js"
    with open(script, encoding="utf-8") as challenge_js:
        source = challenge_js.read()
    assert "fetch('/_sb/verify'" in source
    assert 'webdriver:' in source and 'headlessChrome:' in source

def test_clearance_validation():
    # Valid
    ck = "ck-test"
    val, _ = layer2.issue_clearance_cookie(ck, 0)
    assert layer2.validate_clearance(val, ck) is True
    
    # Wrong client
    assert layer2.validate_clearance(val, "ck-attacker") is False
    
    # Tampered
    tampered = val[:-2] + "X" + val[-1:]
    assert layer2.validate_clearance(tampered, ck) is False
