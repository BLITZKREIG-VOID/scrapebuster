from datetime import datetime, timezone

from sb.edge.context import RequestContext
from sb.edge.session import Session


def init_request(ctx: RequestContext, session: Session) -> None:
    """Initialize or update basic profile fields on an incoming request."""
    now = datetime.now(timezone.utc).isoformat()
    
    if not session.first_seen:
        session.first_seen = now
        session.ip = ctx.ip
        session.user_agent = ctx.user_agent or ""
        session.header_fp = ctx.header_fp
        
    session.last_seen = now
    session.request_count += 1
    
    # Track unique pages hit
    if ctx.path not in session.pages:
        session.pages.append(ctx.path)


def record_decision(session: Session, layer: str, decision: str) -> None:
    """Record a pipeline decision to the session's layer path and re-classify."""
    session.layer_path.append({
        "layer": layer,
        "decision": decision,
        "ts": datetime.now(timezone.utc).isoformat()
    })
    session.classification = classify_session(session)


def classify_session(session: Session) -> str:
    """
    Deterministic rule engine for scraper classification.
    
    AUTOMATION: L2-restricted session
    BOT_BASIC: L1_AUTOMATION_UA or L1 BLOCK
    SOPHISTICATED_SCRAPER: TRAPPED or L2 TRAP-band outcome
    HUMAN_LIKELY: reaches ORIGIN with PASS/ALLOW and no trap exposure
    UNKNOWN: otherwise
    """
    # A completed L2 restriction is the most specific outcome, even when L1
    # also recognized an automation-style User-Agent.
    if session.state == "RESTRICTED":
        return "AUTOMATION"

    # 1. BOT_BASIC
    has_bot_ua = "L1_AUTOMATION_UA" in session.l1_reasons
    has_l1_block = any(p.get("layer") == "L1" and p.get("decision") == "BLOCK" for p in session.layer_path)
    
    if has_bot_ua or has_l1_block:
        return "BOT_BASIC"
        
    # 2. SOPHISTICATED_SCRAPER
    if session.state == "TRAPPED" or len(session.traps_triggered) > 0:
        return "SOPHISTICATED_SCRAPER"
        
    # 3. HUMAN_LIKELY
    has_origin_pass = any(p.get("layer") == "ORIGIN" and p.get("decision") in ("ALLOW", "PASS") for p in session.layer_path)
    if has_origin_pass and not session.traps_triggered and session.state != "TRAPPED":
        return "HUMAN_LIKELY"
        
    # 4. UNKNOWN
    return "UNKNOWN"
