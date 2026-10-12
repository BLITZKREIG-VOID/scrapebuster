"""Integration test: Scrape -> callback correlated within 5 seconds (PRD M4 / FR-4.1, FR-4.4)."""

from __future__ import annotations

import re
import time
import pytest
from fastapi.testclient import TestClient
from sb.canary.registry import bind_session_canary, get_session_binding
from sb.main import app
from sb.offense.injector import inject_beacon
from sb.store.db import reset_db
from sb.store.ledger import verify_chain


@pytest.fixture(autouse=True)
def clean_state():
    reset_db()
    yield
    reset_db()


def test_scrape_to_callback_within_5_seconds():
    """Verify scrape response containing beacon is triggered and correlated within 5s."""
    client = TestClient(app)
    t_start = time.perf_counter()

    # 1. Simulate server generating response with session-bound beacon
    session_id = "scrape-session-xyz"
    binding = bind_session_canary(session_id, vector="BEACON", value="token-alpha-99")
    html_origin = "<html><head><title>Scraped Catalog</title></head><body><h1>Products</h1></body></html>"
    mutated_html = inject_beacon(html_origin, binding.canary_id, "token-alpha-99", public_base_url="http://127.0.0.1:8000")

    # 2. Scraper parses HTML and extracts the beacon image URL
    match = re.search(r'src="[^"]*?/beacon\.gif\?c=([^&"]+)&t=([^&"]+)"', mutated_html)
    assert match is not None, "Beacon image not found in mutated response"
    extracted_canary, extracted_token = match.group(1), match.group(2)
    assert extracted_canary == binding.canary_id
    assert extracted_token == "token-alpha-99"

    # 3. Scraper renders or loads the beacon image within 5 seconds
    t_scrape_done = time.perf_counter()
    assert (t_scrape_done - t_start) < 5.0, "Scraping/extraction exceeded time limit"

    callback_resp = client.get(f"/beacon.gif?c={extracted_canary}&t={extracted_token}")
    assert callback_resp.status_code == 200
    assert callback_resp.headers["content-type"] == "image/gif"
    assert callback_resp.content.startswith(b"GIF89a")
    assert "x-callback-id" in callback_resp.headers

    # 4. Verify correlation and ledger chain integrity
    total_elapsed = time.perf_counter() - t_start
    assert total_elapsed < 5.0, f"Scrape to callback exceeded 5s SLA (took {total_elapsed:.3f}s)"

    # Verify session is correlated in ledger and chain is VALID
    bound = get_session_binding(extracted_canary)
    assert bound is not None
    assert bound.session_id == session_id

    chain_res = verify_chain()
    assert chain_res["result"] == "VALID"
