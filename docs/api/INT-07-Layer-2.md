# INT-07: Layer 2 JS/PoW Challenge

## Overview

Layer 2 provides an active defense mechanism that forces suspicious traffic to execute JavaScript and solve a small computational challenge (Proof-of-Work). 

When **Layer 1** scores a request in the `CHALLENGE` band (60-89 points), the request is intercepted before reaching the proxy. Layer 2 serves an HTML/JS page containing the challenge. The client must solve the challenge and submit the result to a dedicated verification endpoint (`/_sb/challenge/verify`).

## Architecture

```
                          Layer 1
                             |
                      [CHALLENGE band]
                             |
                             v
+-----------------------------------------------------------+
| Layer 2 (JS + PoW)                                        |
| 1. Generate unique, session-bound challenge (nonce)       |
| 2. Serve HTML page with challenge.js                      |
| 3. Client JS computes SHA256(nonce + answer)              |
| 4. Solution submitted to /_sb/challenge/verify            |
+-----------------------------------------------------------+
                             |
                     +-------+-------+
                     |               |
                [VERIFIED]       [FAILED]
                     |               |
             Session updated  Session escalated
                     |               |
                 [ALLOW]         [ESCALATE]
```

## Challenge Generation

Challenges are:
1. **Unpredictable:** Nonces are randomly generated (UUID).
2. **Session-Bound:** The challenge ID is tied to the current session (which is tied to the client IP and User-Agent).
3. **Short-Lived:** Expires after a configurable TTL (e.g., 300 seconds).
4. **Single-Use:** Once verified (or failed), the challenge cannot be replayed.

## Verification Endpoint

**Endpoint:** `POST /_sb/challenge/verify`

**Request Payload:**
```json
{
  "challenge_id": "ch-abc123def...",
  "solution": "12345",
  "signals": {
    "userAgent": "Mozilla/5.0...",
    "language": "en-US"
  }
}
```

**Response:**
* **Success (200 OK):**
```json
{
  "status": "ok"
}
```
* **Failure (403 Forbidden):**
```json
{
  "status": "failed"
}
```

## Validation Rules

The server strictly and independently verifies:
1. **Challenge exists:** Ensure `challenge_id` is known.
2. **Session match:** Ensure `challenge.session_id == current_session.id`.
3. **Expiry:** Ensure `current_time < challenge.expiry`.
4. **Single-use:** Ensure `challenge.used == False`.
5. **PoW validation:** Verify that `SHA256(nonce + solution)` starts with the required difficulty prefix (e.g., `POW_DIFFICULTY = "000"`).

## Session State Transitions

- When Layer 1 triggers a challenge, the session state is updated to `CHALLENGED`.
- Upon successful verification via the `/_sb/challenge/verify` endpoint, the session state is updated to `VERIFIED`.
- Subsequent requests by a `VERIFIED` session will bypass the challenge block and be allowed to proceed through the proxy.
- If verification fails, the session state is marked as `SUSPICIOUS`, and the client is denied access.

## Configuration

The difficulty of the PoW is configurable to balance the computational burden on legitimate clients against the cost to automated bots.
- `POW_DIFFICULTY`: The required starting string of the SHA-256 hash (e.g., `"000"`).
- `CHALLENGE_TTL_SECS`: Time-to-live for a challenge in seconds (e.g., `300`).
