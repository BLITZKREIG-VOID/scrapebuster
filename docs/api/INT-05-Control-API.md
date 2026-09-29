# ScapeBusters Control API

The Control API exposes the backend's internal state to the dashboard.

## Health API

**Endpoint**: `GET /api/v1/health`
**Purpose**: Determine whether the ScapeBusters backend is functioning.

**Parameters**: None

**Response**:
```json
{
  "status": "ok"
}
```

## Traffic API

**Endpoint**: `GET /api/v1/traffic/events`
**Purpose**: Fetch traffic events to display real-time proxy decisions. 

**Parameters**:
- `after` (int): Fetch events with sequence numbers greater than this value. Defaults to 0.
- `limit` (int): Maximum number of events to return. Defaults to 200.

**Response**:
```json
{
  "events": [
    {
      "seq": 1,
      "event_id": "evt-1234abcd",
      "ts": "2026-09-29T12:00:00Z",
      "session_id": "ck-abcdef123456",
      "client_key": "abcdef123456",
      "ip": "127.0.0.1",
      "method": "GET",
      "path": "/",
      "status_code": 200,
      "user_agent": "Mozilla/5.0",
      "layer": "L1",
      "decision": "ALLOW",
      "risk_score": 0,
      "reasons": []
    }
  ],
  "last_seq": 1
}
```

## Sessions API

**Endpoint**: `GET /api/v1/sessions`
**Purpose**: List currently tracked sessions in memory.

**Parameters**:
- `classification` (optional string): Filter sessions by their classification (e.g., `BOT_BASIC`, `SOPHISTICATED_SCRAPER`).

**Response**:
```json
{
  "sessions": [
    {
      "session_id": "ck-abcdef123456",
      "classification": "UNKNOWN",
      "request_count": 5,
      "state": "NEW"
    }
  ]
}
```

**Endpoint**: `GET /api/v1/sessions/{id}`
**Purpose**: Retrieve full profile details for a specific session.

**Response**:
Matches the `SessionDetail` contract schema.

## Overview API

**Endpoint**: `GET /api/v1/overview`
**Purpose**: Summary of ScapeBusters status for the main dashboard display. Includes traffic counts by decision, ladder aggregation, and session aggregation.

**Parameters**: None

**Response**:
```json
{
  "run_id": "NO_RUN_ID",
  "counts": {
    "ALLOW": 15,
    "BLOCK": 2
  },
  "ladder": {
    "safe": 15,
    "suspicious": 0,
    "challenge_restrict": 0,
    "block": 2,
    "trap": 0,
    "provenance": 0
  },
  "sessions_by_class": {
    "UNKNOWN": 3
  },
  "canaries": {
    "active": 0,
    "exposed": 0,
    "observed": 0
  },
  "cases": {
    "total": 0,
    "detected": 0
  },
  "pipeline": [
    {"stage": "edge", "status": "ok"},
    {"stage": "trap", "status": "ok"}
  ],
  "latest_case": null
}
```
