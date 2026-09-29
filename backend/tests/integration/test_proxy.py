import threading
import time

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sb.main import app
from sb.store.db import get_connection, reset_db


# Fixture to run a dummy origin server on 8001
@pytest.fixture(scope="module")
def origin_server():
    import uvicorn
    
    origin_app = FastAPI()
    @origin_app.get("/docs/")
    async def docs():
        return HTMLResponse(content="<main id='content'>Origin Docs</main>")
    
    config = uvicorn.Config(app=origin_app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)
    
    # Run the server in a thread
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    
    # Give it time to start
    time.sleep(2)
    yield
    
    # Shutdown
    server.should_exit = True
    thread.join(timeout=2)

@pytest.mark.asyncio
async def test_proxy_flow(origin_server):
    reset_db()
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/docs/")
        
        assert response.status_code == 200
        assert b"Origin Docs" in response.content
        
        # Verify traffic_events
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traffic_events")
            rows = cursor.fetchall()
            
            assert len(rows) == 1
            event = rows[0]
            assert event["path"] == "/docs/"
            assert event["method"] == "GET"
            assert event["status_code"] == 200
            assert event["layer"] == "L1"
            assert event["decision"] == "ALLOW"
        finally:
            conn.close()
