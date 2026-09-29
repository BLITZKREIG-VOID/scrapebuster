"""Site profiles and safe-demo guards shared by the attackers and the test harness.

Stdlib only, so the pytest harness can import it without Playwright.

Safe demo mode (master plan §I.C.3):

* SD-1: ``--base`` must be a loopback edge unless ``--allow-remote-base`` is passed.
* SD-2: per-run request/page budgets are hard-capped (``check_budget``).
* SD-4: every demo client appends ``SBDemo/<role>`` to its User-Agent so demo traffic
  is identifiable in ``traffic_events``. The token is a label for operators and
  dashboards, not a signal: the client's real UA stays in front of it.
"""
from __future__ import annotations

import argparse
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

ANCHORS = ("Oriel Vantrask", "Hexaquorum", "quasar-reconcile", "velvet-anchor", "ORCHID-7")
DEFAULT_BASE = "http://localhost:8000"
DEMO_UA_TOKEN = "SBDemo"
MAX_REQUESTS = 100  # SD-2: ordinary bot requests per run
MAX_THREADS = 10  # SD-2: ordinary bot concurrency


@dataclass(frozen=True)
class Site:
    """Upstream behind the edge: fixed page order plus content markers.

    ``marker`` must be in the raw response (HTTP bots see only this); ``rendered``
    must be in the rendered text (browser bots), empty when the HTML is server-rendered.
    ``origin`` is the upstream the edge forwards to for this profile.
    """

    origin: str
    pages: tuple[str, ...]
    marker: str
    rendered: str = ""


SITES = {
    # Demo target (plan §I.A C1): public links in CampusCart's navigation (Firebase SPA).
    "campuscart": Site(
        origin="https://campuscart-c73de.web.app",
        pages=(
            "/",
            "/?category=sale",
            "/?category=rent",
            "/?category=projects",
            "/?category=sports",
            "/?category=books",
            "/?category=tech",
            "/events",
            "/login",
        ),
        marker="<title>campuscart</title>",
        rendered="CampusCart",
    ),
    # LOCAL TEST FIXTURE ONLY: the v1 ExampleCorp stand-in on :8001 (plan §13, superseded by C1).
    "examplecorp": Site(
        origin="http://127.0.0.1:8001",
        pages=(
            "/",
            "/docs/",
            "/docs/getting-started",
            "/docs/architecture",
            "/docs/api",
            "/docs/team",
            "/docs/operations",
            "/docs/metrics",
            "/pricing",
        ),
        marker="ExampleCorp Nimbus Platform",
    ),
}
DEFAULT_SITE = "campuscart"


def is_loopback(base: str) -> bool:
    host = (urlsplit(base).hostname or "").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def add_base_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--base", default=DEFAULT_BASE, help="ScrapeBuster edge (loopback only unless overridden)")
    ap.add_argument(
        "--allow-remote-base", action="store_true",
        help="SD-1 override: permit a non-loopback --base (never point this at a third-party site)",
    )


def check_base(ap: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """SD-1: exit 2 (argparse error) for a non-loopback base without the override."""
    parts = urlsplit(args.base)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        ap.error(f"--base must be an http(s) URL, got {args.base!r}")
    canonical_upstream = (urlsplit(SITES["campuscart"].origin).hostname or "").lower()
    if (parts.hostname or "").lower() == canonical_upstream:
        ap.error(
            f"refusing direct upstream --base {args.base!r}: attack scripts must target "
            "the ScrapeBuster edge, never CampusCart directly"
        )
    if not is_loopback(args.base) and not args.allow_remote_base:
        ap.error(
            f"refusing non-loopback --base {args.base!r}: attacks go only to the local edge "
            "(pass --allow-remote-base to override)"
        )


def check_budget(ap: argparse.ArgumentParser, name: str, value: int, cap: int) -> None:
    """SD-2: exit 2 when a per-run budget is outside 1..cap."""
    if not 1 <= value <= cap:
        ap.error(f"--{name} {value} outside the safe-demo budget 1..{cap}")


def demo_ua(user_agent: str, role: str) -> str:
    """SD-4: the client's real UA with the demo marker appended."""
    return f"{user_agent} {DEMO_UA_TOKEN}/{role}"
