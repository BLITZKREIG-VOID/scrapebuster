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
    "db",
    "Session",
    "TrafficEventRecord",
    "format_canary_id",
    "reserve_canary_sequence",
    "save_canary_binding",
    "get_canary_binding",
    "list_canary_bindings",
    "append_event",
    "append_events_batch",
    "persist_telemetry_batch",
    "verify_chain",
    "canonical_json_bytes",
    "get_ledger_head",
    "get_ledger_events",
    "GENESIS",
    "save_session",
    "save_session_snapshot",
    "upsert_sessions_batch",
    "get_session",
    "list_sessions",
    "save_traffic_event",
    "insert_traffic_events_batch",
    "get_traffic_events",
    "get_traffic_event",
    "count_traffic_events",
    "get_decision_counts",
]
