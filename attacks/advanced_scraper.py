"""Scraper 2 — advanced automation (master plan §5, ATK-03).

Default headless Playwright Chromium: no stealth patches, default UA, locale en-US.
Visits the first N public CampusCart routes at 1 page/s, waits for the SPA's
navigation to hydrate (its Firebase requests may prevent networkidle), lets any
interstitial JS run, and never moves the mouse, types or scrolls. Prints
[(url, status, has_content)] as JSON on stdout.

    python attacks/advanced_scraper.py --base http://localhost:8000 --pages 6 [--site campuscart|examplecorp]
"""
from __future__ import annotations

import argparse
import time

from common import (
    DEFAULT_BASE,
    DEFAULT_SITE,
    SITES,
    PageDriver,
    anchors_in,
    emit,
    has_content,
    log,
    pace,
    resolve,
)
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--site", choices=sorted(SITES), default=DEFAULT_SITE, help="upstream behind the edge")
    ap.add_argument("--pages", type=int, default=6)
    args = ap.parse_args()

    results = []
    anchors: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="en-US")
        page = context.new_page()
        driver = PageDriver(page)
        ua = page.evaluate("() => navigator.userAgent")
        site = SITES[args.site]
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
        browser.close()

    emit({
        "scraper": "advanced_scraper",
        "user_agent": ua,
        "pages": results,
        "content_pages": sum(r["has_content"] for r in results),
        "anchors_found": sorted(anchors),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
