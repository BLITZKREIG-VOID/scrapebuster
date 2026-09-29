"""Layer 1 terminal decisions must never reach the upstream proxy."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Response
from sb.edge import layer2, pipeline
from sb.edge.layer1 import L1Result
from sb.edge.session import Session


def _ctx():
    ctx = MagicMock()
    ctx.path = "/products"
    ctx.client_key = "pipeline-test-key"
    ctx.ip = "192.0.2.10"
    ctx.user_agent = "Mozilla/5.0"
    ctx.header_fp = "browser-fingerprint"
    ctx.is_document = True
    ctx.request.cookies = {}
    return ctx


def _session(state="VERIFIED", block_until=""):
    return Session(
        session_id="pipeline-test-session",
        client_key="pipeline-test-key",
        state=state,
        block_until=block_until,
        l1_reasons=["L1_AUTOMATION_UA"],
    )


@pytest.mark.parametrize("block_until", ["not-a-timestamp", 123])
def test_malformed_block_expiry_does_not_strand_session(block_until):
    assert _session("BLOCKED", block_until).block_expired() is True


@pytest.fixture
def quiet_pipeline(monkeypatch):
    monkeypatch.setattr(pipeline, "log_event", MagicMock())
    monkeypatch.setattr(pipeline.trap_hooks, "classify_request", MagicMock(return_value=None))
    record = MagicMock()
    monkeypatch.setattr(pipeline, "proxy", AsyncMock())
    monkeypatch.setattr(layer2, "generate_interstitial", MagicMock(return_value=Response("challenge")))
    return record


def test_active_blocked_session_never_calls_proxy(quiet_pipeline):
    until = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    session = _session("BLOCKED", until)

    response = asyncio.run(pipeline._handle_request(_ctx(), session, quiet_pipeline))

    assert response.status_code == 403
    assert session.state == "BLOCKED"
    pipeline.proxy.assert_not_awaited()


def test_l1_block_decision_sets_blocked_and_never_calls_proxy(monkeypatch, quiet_pipeline):
    until = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    monkeypatch.setattr(
        pipeline,
        "l1_run",
        MagicMock(return_value=L1Result(100, "BLOCK", ["L1_RATE_HARD"], until)),
    )
    session = _session()

    response = asyncio.run(pipeline._handle_request(_ctx(), session, quiet_pipeline))

    assert response.status_code == 403
    assert session.state == "BLOCKED"
    assert session.block_until == until
    pipeline.proxy.assert_not_awaited()


def test_active_challenge_session_never_calls_proxy(monkeypatch, quiet_pipeline):
    monkeypatch.setattr(pipeline, "clearance_valid", MagicMock(return_value=False))
    session = _session("CHALLENGED")

    response = asyncio.run(pipeline._handle_request(_ctx(), session, quiet_pipeline))

    assert response.status_code == 200
    assert session.state == "CHALLENGED"
    pipeline.proxy.assert_not_awaited()


def test_expired_block_resumes_layer1_evaluation(monkeypatch, quiet_pipeline):
    monkeypatch.setattr(
        pipeline,
        "l1_run",
        MagicMock(return_value=L1Result(0, "ESCALATE", ["L1_UNVERIFIED_SESSION"])),
    )
    monkeypatch.setattr(pipeline, "clearance_valid", MagicMock(return_value=False))
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    session = _session("BLOCKED", expired)

    response = asyncio.run(pipeline._handle_request(_ctx(), session, quiet_pipeline))

    assert response.status_code == 200
    assert session.state == "CHALLENGED"
    assert session.block_until == ""
    pipeline.l1_run.assert_called_once()
    pipeline.proxy.assert_not_awaited()


def test_l1_challenge_decision_never_calls_proxy(monkeypatch, quiet_pipeline):
    monkeypatch.setattr(
        pipeline,
        "l1_run",
        MagicMock(return_value=L1Result(70, "CHALLENGE", ["L1_HEADER_FP_ANOMALY"])),
    )
    session = _session()

    response = asyncio.run(pipeline._handle_request(_ctx(), session, quiet_pipeline))

    assert response.status_code == 200
    assert session.state == "CHALLENGED"
    pipeline.proxy.assert_not_awaited()


def test_restricted_session_is_enforced_before_layer1_and_proxy(monkeypatch, quiet_pipeline):
    session = _session("RESTRICTED")
    session.l2_signals = ["L2_WEBDRIVER", "L2_HEADLESS_UA"]
    monkeypatch.setattr(pipeline, "l1_run", MagicMock())

    response = asyncio.run(pipeline._handle_request(_ctx(), session, quiet_pipeline))

    assert response.status_code == 403
    assert b"Access Restricted" in response.body
    pipeline.l1_run.assert_not_called()
    pipeline.proxy.assert_not_awaited()
