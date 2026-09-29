import httpx
import pytest
from pydantic import ValidationError
from sb.contracts import Health, SessionDetail, SessionSummary, TrafficEvent
from sb.main import app
from sb.store.db import reset_db


@pytest.mark.asyncio
async def test_health_contract():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        try:
            health = Health(**data)
            assert health.status == "ok"
        except ValidationError as e:
            pytest.fail(f"Health contract validation failed: {e}")

@pytest.mark.asyncio
async def test_traffic_contract(origin_server):
    reset_db()
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Generate a proxy request to create a traffic event
        await client.get("/")
        
        # Check traffic API
        response = await client.get("/api/v1/traffic/events?after=0&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
        assert "last_seq" in data
        assert len(data["events"]) > 0
        
        try:
            for ev in data["events"]:
                TrafficEvent(**ev)
        except ValidationError as e:
            pytest.fail(f"TrafficEvent contract validation failed: {e}")

@pytest.mark.asyncio
async def test_sessions_contract(origin_server):
    reset_db()
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Make a proxy request to generate a session
        await client.get("/")
        
        # 1. Test List Endpoint
        response = await client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) > 0
        
        try:
            for s in data["sessions"]:
                SessionSummary(**s)
        except ValidationError as e:
            pytest.fail(f"SessionSummary contract validation failed: {e}")
            
        session_id = data["sessions"][0]["session_id"]
        
        # 2. Test Detail Endpoint
        response = await client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        detail_data = response.json()
        
        try:
            SessionDetail(**detail_data)
        except ValidationError as e:
            pytest.fail(f"SessionDetail contract validation failed: {e}")

@pytest.mark.asyncio
async def test_overview_contract(origin_server):
    reset_db()
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.get("/")
        
        response = await client.get("/api/v1/overview")
        assert response.status_code == 200
        data = response.json()
        
        # While there's an Overview schema conceptually, 
        # let's validate required top-level keys matching the plan
        assert "run_id" in data
        assert "counts" in data
        assert "ladder" in data
        assert "sessions_by_class" in data
        assert "canaries" in data
        assert "cases" in data
        assert "pipeline" in data
