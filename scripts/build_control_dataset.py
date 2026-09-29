#!/usr/bin/env python3
"""Build the clean CampusCart control dataset straight from the origin (plan Part I, F-06/R-11).

CampusCart (https://campuscart-c73de.web.app) is a client-rendered Firebase SPA, so the text
only exists after hydration: each public route is rendered with Playwright Chromium (the same
toolchain as ``attacks/``) and captured the same way Scraper 3 captures it (``main#content``
or ``<body>`` ``innerText``). Fetches go to the origin directly, never through the ScapeBusters
edge, so no canary can be present. Volume is fixed and low: one browser, the listed public
routes once each, sequentially, with a pause between navigations.

Output: one dataset-contract record per route, ``{"url","fetched_at","title","text"}``, in
``data/control/control_clean.jsonl``. The run fails (and writes nothing) if a page looks
edge-served (honeypot link present), renders no text, or contains a canary anchor.

Needs: ``pip install playwright && python -m playwright install chromium``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sb.canary.hashing import normalize_for_match
from sb.canary.registry import load_definitions
from sb.trap.honeypots import HIDDEN_LINK_PATH

DEFAULT_BASE = "https://campuscart-c73de.web.app"
# Public, unauthenticated CampusCart routes: the non-trap pages Scraper 3 collects.
ROUTES = (
    "/",
    "/login",
    "/?category=sale",
    "/?category=rent",
    "/?category=projects",
    "/?category=sports",
    "/?category=books",
    "/?category=tech",
    "/?category=room",
    "/?category=stationary",
    "/?category=others",
    "/requests",
    "/messages",
    "/events",
)
PAUSE_S = 1.5
NAV_TIMEOUT_MS = 30_000
HYDRATE_TIMEOUT_MS = 15_000
TEXT_JS = "() => { const m = document.querySelector('main#content'); return (m || document.body).innerText; }"
USER_AGENT_SUFFIX = " ScapeBusters-control-builder/1.0"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check(url: str, html: str, text: str, anchors: list[str]) -> None:
    if f'href="{HIDDEN_LINK_PATH}"' in html:
        raise SystemExit(f"{url}: honeypot link present, page was served through the edge")
    if not text.strip():
        raise SystemExit(f"{url}: rendered no text")
    leaked = [a for a in anchors if a in normalize_for_match(html + "\n" + text)]
    if leaked:
        raise SystemExit(f"{url}: canary anchor(s) {leaked} in origin content")


def build(base: str, out_path: Path, routes: tuple[str, ...] = ROUTES) -> int:
    if base.rstrip("/") != DEFAULT_BASE:
        raise SystemExit("control acquisition must use the public CampusCart origin directly")
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("error: playwright is required: pip install playwright && python -m playwright install chromium",
              file=sys.stderr)
        return 0

    anchors = [normalize_for_match(c["anchor"]) for c in load_definitions()]
    records = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            ua = browser.new_page().evaluate("navigator.userAgent") + USER_AGENT_SUFFIX
            page = browser.new_context(user_agent=ua).new_page()
            for i, route in enumerate(routes):
                if i:
                    time.sleep(PAUSE_S)
                url = urljoin(base.rstrip("/") + "/", route.lstrip("/"))
                response = page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                if response is None or response.status != 200:
                    raise SystemExit(f"{url}: origin did not return HTTP 200")
                if urlsplit(page.url).netloc != urlsplit(DEFAULT_BASE).netloc:
                    raise SystemExit(f"{url}: navigation left the CampusCart origin")
                try:
                    page.locator("#root a[href]").first.wait_for(state="attached", timeout=HYDRATE_TIMEOUT_MS)
                except PlaywrightError as exc:
                    raise SystemExit(f"{url}: SPA did not hydrate ({exc.__class__.__name__})") from exc
                text = page.evaluate(TEXT_JS) or ""
                _check(url, page.content(), page.title() + "\n" + text, anchors)
                records.append({"url": url, "fetched_at": _utc_now(), "title": page.title(), "text": text})
                print(f"  {url}: {len(text)} chars", file=sys.stderr)
        finally:
            browser.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(records)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=DEFAULT_BASE, help="CampusCart origin (never the edge)")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "control" / "control_clean.jsonl")
    args = ap.parse_args(argv)
    count = build(args.base, args.out)
    if not count:
        return 1
    print(f"wrote {count} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
