"""Unit tests for Phase 0 edge intel and session classification."""

from dataclasses import dataclass, field

from sb.edge.context import RequestContext
from sb.edge.intel import classify_session, init_request, record_decision
from sb.edge.session import Session


@dataclass
class MockClient:
    host: str = "127.0.0.1"


@dataclass
class MockURL:
    path: str = "/"


@dataclass
class MockRequest:
    client: MockClient = field(default_factory=MockClient)
    url: MockURL = field(default_factory=MockURL)
    headers: dict = field(default_factory=dict)


def make_ctx(path="/") -> RequestContext:
    req = MockRequest(url=MockURL(path=path), headers={"user-agent": "Test-Agent"})
    return RequestContext(request=req)


def test_init_request():
    session = Session(session_id="sess-test-key", client_key="test-key")
    ctx = make_ctx("/home")

    init_request(ctx, session)

    assert session.first_seen is not None
    assert session.last_seen == session.first_seen
    assert session.ip == "127.0.0.1"
    assert session.user_agent == "Test-Agent"
    assert session.request_count == 1
    assert "/home" in session.pages
    assert session.classification == "UNKNOWN"


def test_classify_unknown():
    session = Session(session_id="sess-test-key", client_key="test-key")
    assert classify_session(session) == "UNKNOWN"


def test_classify_human_likely():
    session = Session(session_id="sess-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    record_decision(session, "ORIGIN", "SANDBOX")

    assert classify_session(session) == "HUMAN_LIKELY"
    assert session.classification == "HUMAN_LIKELY"


def test_classify_sophisticated_scraper_via_trap():
    session = Session(session_id="sess-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    session.traps_triggered.append("TRAP-PATH-01")
    record_decision(session, "ORIGIN", "SANDBOX")

    assert classify_session(session) == "SOPHISTICATED_SCRAPER"
    assert session.classification == "SOPHISTICATED_SCRAPER"


def test_classify_sophisticated_scraper_via_canary():
    session = Session(session_id="sess-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    session.canaries_exposed.append("SB-CAN-0001")
    record_decision(session, "ORIGIN", "SANDBOX")

    assert classify_session(session) == "SOPHISTICATED_SCRAPER"
    assert session.classification == "SOPHISTICATED_SCRAPER"
