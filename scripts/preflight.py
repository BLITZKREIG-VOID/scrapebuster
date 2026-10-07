"""ScrapeBusters Phase 0 preflight check (``make preflight``).

Prints a PASS/WARN/FAIL table and exits 1 on any FAIL. Stdlib only, so it runs
before dependencies are installed.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]

MIN_PY = (3, 11)
MIN_NODE = 20
MIN_DISK_GB = 2.0


def load_env() -> dict[str, str]:
    """``.env`` values overridden by process environment."""
    env: dict[str, str] = {}
    path = REPO / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("SB_", "AWS_"))})
    return env


ENV = load_env()
EDGE = ENV.get("SB_EDGE_URL", "http://127.0.0.1:8000")
ORIGIN = ENV.get("SB_UPSTREAM_ORIGIN", "http://127.0.0.1:8001")
DASHBOARD = "http://127.0.0.1:5173"

rows: list[tuple[str, str, str]] = []


def add(status: str, name: str, detail: str) -> None:
    rows.append((status, name, detail))


def port_open(url: str) -> bool:
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex((parts.hostname or "127.0.0.1", port)) == 0


def check_python() -> None:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PY
    add("PASS" if ok else "FAIL", "python", f"{v.major}.{v.minor}.{v.micro} (need >= {MIN_PY[0]}.{MIN_PY[1]})")


def check_node() -> None:
    node = shutil.which("node")
    if not node:
        add("WARN", "node", "node not on PATH (optional for dashboard dev)")
        return
    out = subprocess.run([node, "--version"], capture_output=True, text=True, check=False).stdout.strip()
    major = int(re.match(r"v?(\d+)", out).group(1)) if re.match(r"v?(\d+)", out) else 0
    add("PASS" if major >= MIN_NODE else "WARN", "node", f"{out} (recommended >= {MIN_NODE})")


def check_ports() -> None:
    for name, url, required in (("backend", EDGE, False), ("origin", ORIGIN, False), ("dashboard", DASHBOARD, False)):
        if port_open(url):
            add("PASS", f"port {name}", f"{url} listening")
        else:
            add("WARN", f"port {name}", f"{url} not currently listening")


def check_db() -> None:
    raw = Path(ENV.get("SB_DB_PATH", "sb.db"))
    path = raw if raw.is_absolute() else REPO / raw
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if not path.parent.is_dir():
        add("FAIL", "db writable", f"directory missing: {path.parent}")
        return
    try:
        if not path.exists():
            probe = path.parent / ".preflight_probe"
            probe.write_bytes(b"")
            probe.unlink()
            add("PASS", "db writable", f"{path} (directory writable)")
            return
        conn = sqlite3.connect(path, timeout=5)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("ROLLBACK")
        finally:
            conn.close()
        add("PASS", "db writable", str(path))
    except (sqlite3.Error, OSError) as exc:
        add("FAIL", "db writable", f"{path}: {exc}")


def check_canary_config() -> None:
    yaml_path = REPO / "backend" / "sb" / "canary" / "canaries.yaml"
    if not yaml_path.is_file():
        add("FAIL", "canary config", "backend/sb/canary/canaries.yaml missing")
        return
    add("PASS", "canary config", "backend/sb/canary/canaries.yaml present")


def check_disk() -> None:
    free_gb = shutil.disk_usage(REPO).free / 1e9
    add("PASS" if free_gb >= MIN_DISK_GB else "FAIL", "disk free", f"{free_gb:.1f} GB (need >= {MIN_DISK_GB:.0f} GB)")


def main() -> int:
    for check in (check_python, check_node, check_ports, check_db, check_canary_config, check_disk):
        try:
            check()
        except Exception as exc:
            add("FAIL", check.__name__.removeprefix("check_"), f"{exc.__class__.__name__}: {exc}")
    width = max(len(name) for _, name, _ in rows)
    print(f"{'STATUS':<6}  {'CHECK':<{width}}  DETAIL")
    for status, name, detail in rows:
        print(f"{status:<6}  {name:<{width}}  {detail}")
    fails = sum(1 for s, _, _ in rows if s == "FAIL")
    warns = sum(1 for s, _, _ in rows if s == "WARN")
    print(f"\nPREFLIGHT {'FAIL' if fails else 'PASS'}: {fails} FAIL, {warns} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
