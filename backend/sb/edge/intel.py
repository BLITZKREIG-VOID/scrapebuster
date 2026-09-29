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
    
    BOT_BASIC: any L1_AUTOMATION_UA or BLOCKED by L1
    AUTOMATION: RESTRICTED by L2 (or SUSPICIOUS in our state)
    SOPHISTICATED_SCRAPER: TRAPPED after a PASS, or TRAP band
    HUMAN_LIKELY: PASS, no trap hits
    UNKNOWN: otherwise
    """
    # 1. BOT_BASIC
    # A known bot pattern triggered, or L1 outright blocked it
    has_bot_ua = any("ua:bot_pattern" in r for r in session.l1_reasons)
    has_l1_block = any(p.get("layer") == "L1" and p.get("decision") == "BLOCK" for p in session.layer_path)
    
    if has_bot_ua or has_l1_block:
        return "BOT_BASIC"
        
    # 2. AUTOMATION
    # Failed Layer 2 challenges / restricted states
    if session.state in ("RESTRICTED", "SUSPICIOUS"):
        return "AUTOMATION"
        
    # 3. SOPHISTICATED_SCRAPER
    # Hit a Layer 3 honeypot/trap
    if session.state == "TRAPPED" or len(session.traps_triggered) > 0:
        return "SOPHISTICATED_SCRAPER"
        
    # 4. HUMAN_LIKELY
    # Allowed through the proxy with no trap hits
    has_origin_pass = any(p.get("layer") == "ORIGIN" and p.get("decision") in ("ALLOW", "ESCALATE", "CHALLENGE_BYPASSED") for p in session.layer_path)
    # Also if it bypassed challenges, that implies human. But let's stick to simple "Allowed"
    if has_origin_pass and not session.traps_triggered:
        return "HUMAN_LIKELY"
        
    # 5. UNKNOWN
    return "UNKNOWN"
