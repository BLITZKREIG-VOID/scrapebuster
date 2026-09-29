import hashlib
import re

import httpx
import pytest
from sb.edge.layer1 import reset_rate_state
from sb.edge.layer2 import L2_POW_ZERO_BITS
from sb.edge.session import sessions
from sb.main import app
from sb.store.db import reset_db


def _solve_pow(challenge_id: str) -> str:
    ans = 0
    threshold = 1 << (16 - L2_POW_ZERO_BITS)
    while True:
        text = f"{challenge_id}:{ans}"
        digest = hashlib.sha256(text.encode()).hexdigest()
        if int(digest[:4], 16) < threshold:
            return str(ans)
        ans += 1


@pytest.mark.asyncio
async def test_layer2_flow_challenge_solve_and_pass(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as app_client:
        # Use a UA that L1 maps to ESCALATE (e.g. valid-ish format but missing browser headers + httpx FP)
        # Empty UA is THROTTLE, so we must provide something non-empty but unverified.
        headers = {
            "host": "testserver", 
            "user-agent": "Mozilla/5.0 EscalateBot/1.0",
        }
        
        # 1. Trigger Interstitial (ESCALATE)
        resp1 = await app_client.get("/target-path", headers=headers)
        assert resp1.status_code == 200
        html = resp1.text
        assert "Checking your browser" in html
        
        # Extract CHALLENGE_ID
        cid_match = re.search(r'SB_CHALLENGE_ID = "(ch-[^"]+)"', html)
        assert cid_match
        cid = cid_match.group(1)
        
        # 2. Solve the PoW
        solution = _solve_pow(cid)
        
        # 3. Submit solution to /_sb/verify (PASS band: < 40)
        verify_payload = {
            "challenge_id": cid,
            "nonce": solution,
            "signals": {
                "navigatorUA": "Mozilla/5.0 EscalateBot/1.0",
                "mousemove": 10,
                "keydown": 2,
                "outerWidth": 1024,
                "outerHeight": 768
            }
        }
        resp2 = await app_client.post("/_sb/verify", json=verify_payload, headers=headers)
        
        # 4. Success -> sb_clear cookie issued
        assert resp2.status_code == 200
        assert resp2.json() == {"status": "ok"}
        assert "sb_clear" in resp2.cookies
        
        # 5. Retry the original request - should pass through!
        resp3 = await app_client.get("/target-path", headers=headers, cookies=resp2.cookies)
        assert resp3.status_code == 200
        assert "Checking your browser" not in resp3.text


@pytest.mark.asyncio
async def test_layer2_flow_invalid_solution(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as app_client:
        headers = {
            "host": "testserver", 
            "user-agent": "Mozilla/5.0 EscalateBot/1.0",
        }
        
        resp1 = await app_client.get("/target-path2", headers=headers)
        assert resp1.status_code == 200
        
        cid = re.search(r'SB_CHALLENGE_ID = "(ch-[^"]+)"', resp1.text).group(1)
        
        # Submit wrong PoW
        verify_payload = {
            "challenge_id": cid,
            "nonce": "wrong",
            "signals": {}
        }
        resp2 = await app_client.post("/_sb/verify", json=verify_payload, headers=headers)
        assert resp2.status_code == 403
        assert resp2.json() == {"status": "failed"}
        
        # Retry original request - gets RESTRICTED page (not interstitial again)
        # Because L2 score >= 70 (PoW missing = 100) -> RESTRICTED
        resp3 = await app_client.get("/target-path2", headers=headers)
        assert resp3.status_code == 403
        assert "Access Restricted" in resp3.text
