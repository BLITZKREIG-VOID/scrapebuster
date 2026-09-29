import hashlib

import httpx
import pytest

from sb.edge.layer2 import POW_DIFFICULTY
from sb.main import app
from sb.edge.session import sessions
from sb.edge.layer1 import reset_rate_state
from sb.store.db import reset_db

@pytest.mark.asyncio
async def test_layer2_flow_challenge_solve_and_pass(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as app_client:
        # 1. Trigger CHALLENGE by setting a suspicious UA and headless markers
        headers = {
            "host": "testserver", 
            "user-agent": "", 
            "x-forwarded-for": "1.2.3.4", 
            "via": "1.1 proxy", 
            "forwarded": "for=192.0.2.60"
        }
        resp1 = await app_client.get("/target-path", headers=headers)
        
        assert resp1.status_code == 403
        html = resp1.text
        assert "Security Check" in html
        
        # Extract CHALLENGE_ID and NONCE from the HTML
        import re
        cid_match = re.search(r'const CHALLENGE_ID = "(ch-[^"]+)"', html)
        nonce_match = re.search(r'const NONCE = "([^"]+)"', html)
        assert cid_match and nonce_match
        
        cid = cid_match.group(1)
        nonce = nonce_match.group(1)
        
        # 2. Solve the PoW
        ans = 0
        while True:
            text = nonce + str(ans)
            if hashlib.sha256(text.encode()).hexdigest().startswith(POW_DIFFICULTY):
                break
            ans += 1
            
        solution = str(ans)
        
        # 3. Submit solution to verify endpoint
        verify_payload = {
            "challenge_id": cid,
            "solution": solution,
            "signals": {"userAgent": "", "language": ""}
        }
        resp2 = await app_client.post("/_sb/challenge/verify", json=verify_payload, headers=headers)
        assert resp2.status_code == 200
        assert resp2.json() == {"status": "ok"}
        
        # 4. Now retry the original request - should pass through!
        resp3 = await app_client.get("/target-path", headers=headers)
        assert resp3.status_code == 200
        assert "Security Check" not in resp3.text

@pytest.mark.asyncio
async def test_layer2_flow_invalid_solution(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as app_client:
        headers = {
            "host": "testserver", 
            "user-agent": "", 
            "x-forwarded-for": "1.2.3.4", 
            "via": "1.1 proxy", 
            "forwarded": "for=192.0.2.60"
        }
        resp1 = await app_client.get("/target-path2", headers=headers)
        assert resp1.status_code == 403
        
        import re
        cid = re.search(r'const CHALLENGE_ID = "(ch-[^"]+)"', resp1.text).group(1)
        
        # Submit wrong solution
        verify_payload = {
            "challenge_id": cid,
            "solution": "wrong",
        }
        resp2 = await app_client.post("/_sb/challenge/verify", json=verify_payload, headers=headers)
        assert resp2.status_code == 403
        assert resp2.json() == {"status": "failed"}
        
        # Retry original request - should still get challenged
        resp3 = await app_client.get("/target-path2", headers=headers)
        assert resp3.status_code == 403
        assert "Security Check" in resp3.text

