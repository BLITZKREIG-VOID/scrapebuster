"""Scraper 2 — advanced automation (master plan §5, ATK-03).

Default headless Playwright Chromium: no stealth patches, the default (HeadlessChrome)
UA plus the SD-4 ``SBDemo/scraper2`` marker, locale en-US. Visits the first N public
routes at 1 page/s, waits for the SPA's navigation to hydrate (its Firebase requests
may prevent networkidle), lets any interstitial JS run, and never moves the mouse,
types or scrolls. Prints [(url, status, has_content)] as JSON on stdout.

    python attacks/advanced_scraper.py --base http://localhost:8000 --pages 6 [--site campuscart|examplecorp]
"""
from __future__ import annotations

import argparse
import time

from common import (
    DEFAULT_SITE,
    SAFETY_STOP_EXIT_CODE,
    SITES,
    PageDriver,
    add_base_args,
    anchors_in,
    check_base,
    check_budget,
    demo_ua,
    emit,
    has_content,
    is_safety_stop_status,
    log,
    pace,
    resolve,
)
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


def default_user_agent(browser) -> str:
    """The browser's own headless UA, read from a throwaway context."""
    probe = browser.new_context()
    try:
        return probe.new_page().evaluate("() => navigator.userAgent")
    finally:
        probe.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_base_args(ap)
    ap.add_argument("--site", choices=sorted(SITES), default=DEFAULT_SITE, help="upstream behind the edge")
    ap.add_argument("--pages", type=int, default=6)
    args = ap.parse_args()
    check_base(ap, args)
    site = SITES[args.site]
    check_budget(ap, "pages", args.pages, len(site.pages))

    results = []
    anchors: set[str] = set()
    safety_stop_triggered = False
    stop_status = None
    stop_url = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ua = demo_ua(default_user_agent(browser), "scraper2")
        context = browser.new_context(locale="en-US", user_agent=ua)
        page = context.new_page()
        driver = PageDriver(page)
        for path in site.pages[: args.pages]:
            started = time.monotonic()
            url = resolve(args.base, path)
            try:
                visit = driver.goto(url, rng=None)  # rng=None: no interaction
                ok = has_content(visit, site)
                anchors.update(anchors_in(visit.text))
                results.append({"url": url, "status": visit.status, "has_content": ok})
            except PlaywrightError as exc:
                log(f"  {url}: {exc.__class__.__name__}: {exc}")
                results.append({"url": url, "status": None, "has_content": False})
            log(f"  {results[-1]}")
            pace(started, 1.0)
            if results and is_safety_stop_status(results[-1]["status"]):
                safety_stop_triggered = True
                stop_status = results[-1]["status"]
                stop_url = url
                break
        browser.close()

    emit({
        "scraper": "advanced_scraper",
        "user_agent": ua,
        "pages": results,
        "content_pages": sum(r["has_content"] for r in results),
        "anchors_found": sorted(anchors),
    })

    if safety_stop_triggered:
        log(
            f"SAFETY STOP: observed HTTP {stop_status} on {stop_url} "
            f"(Phase 10 tradeoff: conservative stop on 429/5xx - edge may emit 429 due to L1, "
            f"no reliable provenance in attack response). Stopped crawl."
        )
        return SAFETY_STOP_EXIT_CODE

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
