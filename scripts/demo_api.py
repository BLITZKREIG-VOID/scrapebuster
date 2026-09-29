"""Call a demo control endpoint on the running backend (``make reset`` / ``make restore-golden``).

    python scripts/demo_api.py http://127.0.0.1:8000 reset|restore-golden

Prints the response and exits 1 unless it is HTTP 200 and (for reset) every §21 check
passed. Stdlib only; one request, no retries.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

ACTIONS = ("reset", "restore-golden")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ACTIONS:
        print(f"usage: demo_api.py EDGE_URL {{{'|'.join(ACTIONS)}}}", file=sys.stderr)
        return 2
    edge, action = argv
    url = f"{edge.rstrip('/')}/api/v1/demo/{action}"
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            code, body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        code, body = exc.code, exc.read()
    except OSError as exc:
        print(f"FAIL  POST {url}: {exc}")
        return 1
    try:
        payload = json.loads(body)
    except ValueError:
        print(f"FAIL  POST {url} -> HTTP {code}, non-JSON body: {body[:300]!r}")
        return 1
    if code != 200:
        print(f"FAIL  POST {url} -> HTTP {code}: {payload}")
        return 1
    if action == "reset":
        for check in payload.get("checks", []):
            print(f"{'PASS' if check.get('ok') else 'FAIL'}  {check.get('name')}: {check.get('detail', '')}")
        print(f"run_id {payload.get('run_id')}")
        if not payload.get("ok"):
            print("RESET FAIL")
            return 1
        print("RESET PASS")
        return 0
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
