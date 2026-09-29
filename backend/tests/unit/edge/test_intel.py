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
    session = Session(session_id="ck-test-key", client_key="test-key")
    ctx = make_ctx("/home")
    
    init_request(ctx, session)
    
    assert session.first_seen is not None
    assert session.last_seen == session.first_seen
    assert session.ip == "127.0.0.1"
    assert session.user_agent == "Test-Agent"
    assert session.request_count == 1
    assert "/home" in session.pages
    assert session.classification == "UNKNOWN"

def test_human_likely():
    session = Session(session_id="ck-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    
    # Allowed by L1
    record_decision(session, "L1", "ALLOW")
    # Allowed by Origin
    record_decision(session, "ORIGIN", "ALLOW")
    
    assert session.classification == "HUMAN_LIKELY"
    assert len(session.layer_path) == 2
    assert session.layer_path[0]["layer"] == "L1"
    assert session.layer_path[0]["decision"] == "ALLOW"
    assert "ts" in session.layer_path[0]

def test_bot_basic():
    session = Session(session_id="ck-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    
    # 1. Blocked by L1
    record_decision(session, "L1", "BLOCK")
    assert session.classification == "BOT_BASIC"
    
    # 2. Flagged with L1_AUTOMATION_UA
    session2 = Session(session_id="ck-test-key2", client_key="test-key2")
    session2.l1_reasons.append("L1_AUTOMATION_UA")
    init_request(ctx, session2)
    record_decision(session2, "L1", "ALLOW")
    assert session2.classification == "BOT_BASIC"

def test_automation():
    session = Session(session_id="ck-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    
    session.state = "RESTRICTED"
    record_decision(session, "L2", "RESTRICT")
    
    assert session.classification == "AUTOMATION"


def test_l2_restriction_classification_takes_precedence_over_l1_bot_signal():
    session = Session(session_id="ck-test-key", client_key="test-key", state="RESTRICTED")
    session.l1_reasons.append("L1_AUTOMATION_UA")

    assert classify_session(session) == "AUTOMATION"

def test_sophisticated_scraper():
    session = Session(session_id="ck-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    
    # Passes origin initially
    record_decision(session, "ORIGIN", "ALLOW")
    assert session.classification == "HUMAN_LIKELY"
    
    # Now it hits a trap
    session.state = "TRAPPED"
    session.traps_triggered.append("TRAP-ROBOTS-01")
    record_decision(session, "L3", "TRAP")
    
    assert session.classification == "SOPHISTICATED_SCRAPER"

def test_unknown_classification():
    # Brand new session with no path
    session = Session(session_id="ck-test-key", client_key="test-key")
    assert classify_session(session) == "UNKNOWN"
    
def test_classification_changes_with_evidence():
    session = Session(session_id="ck-test-key", client_key="test-key")
    ctx = make_ctx()
    init_request(ctx, session)
    
    # Initially unknown because no layer paths
    assert session.classification == "UNKNOWN"
    
    # Reaches origin successfully -> HUMAN_LIKELY
    record_decision(session, "ORIGIN", "ALLOW")
    assert session.classification == "HUMAN_LIKELY"
    
    # Next request flags L1_AUTOMATION_UA
    session.l1_reasons.append("L1_AUTOMATION_UA")
    record_decision(session, "L1", "BLOCK")
    
    assert session.classification == "BOT_BASIC"
