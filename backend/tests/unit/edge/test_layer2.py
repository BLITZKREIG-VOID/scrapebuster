import hashlib
import time

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
    
    res = layer2.verify_submission(c.challenge_id, solution, {"mousemove": 10}, session, "RealUA", 2000)
    assert res.band == "PASS"
    assert res.score == 0
    assert "sb_clear=" in res.clearance_cookie

def test_verify_submission_trap():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.challenge_id)
    
    # headlessChrome (+40) + no interactions (+20) = 60 (TRAP band 40-69)
    res = layer2.verify_submission(c.challenge_id, solution, {"headlessChrome": True}, session, "RealUA", 2000)
    assert res.band == "TRAP"
    assert res.score == 60

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
