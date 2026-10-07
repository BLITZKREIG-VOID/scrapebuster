"""Edge intel and session profile tracking for Phase0."""

from __future__ import annotations

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

    session.ip = ctx.ip
    session.user_agent = ctx.user_agent or ""
    session.header_fp = ctx.header_fp
    session.last_seen = now
    session.request_count += 1

    if ctx.path not in session.pages:
        session.pages.append(ctx.path)


def record_decision(session: Session, stage: str, decision: str) -> None:
    """Record a pipeline decision to the session and update classification."""
    if decision == "SANDBOX":
        session.state = "SANDBOX"
    session.classification = classify_session(session)


def classify_session(session: Session) -> str:
    """Deterministic rule engine for scraper classification in Phase0.

    SOPHISTICATED_SCRAPER: traps triggered or canaries exposed
    HUMAN_LIKELY: requests processed with no trap or canary triggers
    UNKNOWN: initial uninspected state
    """
    if len(session.traps_triggered) > 0 or len(session.canaries_exposed) > 0:
        return "SOPHISTICATED_SCRAPER"

    if session.request_count > 0:
        return "HUMAN_LIKELY"

    return "UNKNOWN"
