"""Store package for ScrapeBuster: persistence, ledger, models, and canary bindings."""

from . import db
from .canaries import (
    format_canary_id,
    get_canary_binding,
    list_canary_bindings,
    reserve_canary_sequence,
    save_canary_binding,
)
from .ledger import (
    GENESIS,
    append_event,
    append_events_batch,
    canonical_json_bytes,
    get_ledger_events,
    get_ledger_head,
    persist_telemetry_batch,
    verify_chain,
)
from .models import (
    Session,
    TrafficEventRecord,
)
from .sessions import (
    get_session,
    list_sessions,
    save_session,
    save_session_snapshot,
    upsert_sessions_batch,
)
from .traffic import (
    count_traffic_events,
    get_decision_counts,
    get_traffic_event,
    get_traffic_events,
    insert_traffic_events_batch,
    save_traffic_event,
)

__all__ = [
    "GENESIS",
    "Session",
    "TrafficEventRecord",
    "append_event",
    "append_events_batch",
    "canonical_json_bytes",
    "count_traffic_events",
    "db",
    "format_canary_id",
    "get_canary_binding",
    "get_decision_counts",
    "get_ledger_events",
    "get_ledger_head",
    "get_session",
    "get_traffic_event",
    "get_traffic_events",
    "insert_traffic_events_batch",
    "list_canary_bindings",
    "list_sessions",
    "persist_telemetry_batch",
    "reserve_canary_sequence",
    "save_canary_binding",
    "save_session",
    "save_session_snapshot",
    "save_traffic_event",
    "upsert_sessions_batch",
    "verify_chain",
]
