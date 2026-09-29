import hashlib
import time

import pytest
from sb.edge import layer2
from sb.edge.session import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_solution(nonce: str, difficulty: str) -> str:
    ans = 0
    while True:
        text = nonce + str(ans)
        if hashlib.sha256(text.encode()).hexdigest().startswith(difficulty):
            return str(ans)
        ans += 1

@pytest.fixture(autouse=True)
def reset_store():
    layer2.store.reset()

def _create_session(sid="sess-1") -> Session:
    return Session(session_id=sid, client_key="client_key")

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_challenge_generation():
    session = _create_session()
    c = layer2.store.create(session)
    assert c.challenge_id.startswith("ch-")
    assert c.session_id == session.session_id
    assert c.nonce
    assert c.expiry > time.time()
    assert not c.used
    assert layer2.store.get(c.challenge_id) == c

def test_correct_pow():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.nonce, layer2.POW_DIFFICULTY)
    
    assert layer2.verify(c.challenge_id, solution, session) is True
    # Should mark as used
    assert c.used is True

def test_incorrect_pow():
    session = _create_session()
    c = layer2.store.create(session)
    # Give a wrong solution
    assert layer2.verify(c.challenge_id, "wrong_answer", session) is False
    # Does not mark as used until a valid try? Wait, the implementation marks as used *before* checking PoW!
    # Let's check: implementation does `c.used = True` before checking solution. 
    # That means it is single-try! This prevents brute force on a single challenge.
    assert c.used is True

def test_expired_challenge():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.nonce, layer2.POW_DIFFICULTY)
    
    # Manually expire
    c.expiry = time.time() - 10
    
    assert layer2.verify(c.challenge_id, solution, session) is False

def test_unknown_challenge():
    session = _create_session()
    assert layer2.verify("unknown", "0", session) is False

def test_wrong_session():
    session = _create_session("sess-1")
    c = layer2.store.create(session)
    solution = _find_solution(c.nonce, layer2.POW_DIFFICULTY)
    
    attacker_session = _create_session("sess-2")
    assert layer2.verify(c.challenge_id, solution, attacker_session) is False

def test_replay_protection():
    session = _create_session()
    c = layer2.store.create(session)
    solution = _find_solution(c.nonce, layer2.POW_DIFFICULTY)
    
    # First time works
    assert layer2.verify(c.challenge_id, solution, session) is True
    
    # Second time fails
    assert layer2.verify(c.challenge_id, solution, session) is False

def test_generate_challenge_response():
    session = _create_session()
    resp = layer2.generate_challenge_response(session)
    
    assert resp.status_code == 403
    html = resp.body.decode()
    assert "Security Check" in html
    assert layer2.POW_DIFFICULTY in html
    assert "NONCE" in html
