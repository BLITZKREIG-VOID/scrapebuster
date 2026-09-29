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
                "webdriver": False,
                "headlessChrome": False,
                "navigatorUA": "Mozilla/5.0 EscalateBot/1.0",
                "outerWidth": 1024,
                "outerHeight": 768,
                "softwareGL": False,
                "languages": ["en-US"],
                "mousemove": 10,
                "scroll": 0,
                "keydown": 2,
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


@pytest.mark.asyncio
async def test_headless_behavior_restricts_before_origin(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)
    headers = {
        "host": "testserver",
        "user-agent": "Mozilla/5.0 HeadlessChrome/133.0",
        "accept": "text/html",
        "accept-language": "en-US,en;q=0.9",
        "accept-encoding": "gzip, deflate",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as app_client:
        challenged = await app_client.get("/headless-profile", headers=headers)
        assert challenged.status_code == 200
        challenge_match = re.search(r'SB_CHALLENGE_ID = "(ch-[^"]+)"', challenged.text)
        assert challenge_match
        challenge_id = challenge_match.group(1)

        verified = await app_client.post(
            "/_sb/verify",
            headers=headers,
            json={
                "challenge_id": challenge_id,
                "nonce": _solve_pow(challenge_id),
                "signals": {
                    "webdriver": True,
                    "headlessChrome": True,
                    "navigatorUA": headers["user-agent"],
                    "outerWidth": 1280,
                    "outerHeight": 720,
                    "softwareGL": False,
                    "languages": ["en-US"],
                    "mousemove": 0,
                    "scroll": 0,
                    "keydown": 0,
                    "elapsed_ms": 2000,
                },
            },
        )
        assert verified.status_code == 403
        assert verified.json() == {"status": "failed"}

        denied = await app_client.get("/headless-profile", headers=headers)
        assert denied.status_code == 403
        assert "Access Restricted" in denied.text
        assert "Origin headless-profile" not in denied.text


@pytest.mark.asyncio
async def test_verify_rejects_non_object_payload_without_server_error(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as app_client:
        response = await app_client.post("/_sb/verify", json=["not", "an", "object"])

    assert response.status_code == 403
    assert response.json() == {"status": "failed"}


@pytest.mark.asyncio
async def test_legacy_verify_alias_cannot_skip_behavioral_scoring(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)
    headers = {
        "host": "testserver",
        "user-agent": "Mozilla/5.0 AliasCheck/1.0",
        "accept": "text/html",
        "accept-language": "en-US,en;q=0.9",
        "accept-encoding": "gzip, deflate",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as app_client:
        challenged = await app_client.get("/legacy-challenge-check", headers=headers)
        challenge_id = re.search(r'SB_CHALLENGE_ID = "(ch-[^"]+)"', challenged.text).group(1)
        response = await app_client.post(
            "/_sb/challenge/verify",
            headers=headers,
            json={"challenge_id": challenge_id, "solution": _solve_pow(challenge_id)},
        )

    assert response.status_code == 403
    assert response.json() == {"status": "failed"}
