"""Human control (master plan §19 T-NU-1, ATK-06).

Same browser setup as scraper 3 (headed, patched, synthetic interaction), but
behaves like a person: starts at ``/``, clicks only *visible* navigation links
(``is_visible()``), respects robots.txt, 3 s between pages, 5 pages total.
UA carries the SD-4 ``SBDemo/human`` marker; ``--base`` must be loopback (SD-1).

    python attacks/human_control.py --base http://localhost:8000 [--site campuscart|examplecorp] [--headless]
"""
from __future__ import annotations

import argparse
import random
import time
from urllib.parse import urlsplit

from common import (
    add_base_args,
    check_base,
    check_budget,
    DEFAULT_SITE,
    SITES,
    PageDriver,
    anchors_in,
    emit,
    has_content,
    is_disallowed,
    launch_patched,
    log,
    normalize_url,
    parse_disallows,
    resolve,
    same_origin,
    synthetic_interaction,
)
from playwright.sync_api import sync_playwright

SEED = 7
PAGES = 5
DELAY_S = 3.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_base_args(ap)
    ap.add_argument("--site", choices=sorted(SITES), default=DEFAULT_SITE, help="upstream behind the edge")
    ap.add_argument("--pages", type=int, default=PAGES)
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    check_base(ap, args)
    check_budget(ap, "pages", args.pages, len(SITES[args.site].pages))

    rng = random.Random(SEED)
    results: list[dict] = []
    anchors: set[str] = set()
    with sync_playwright() as p:
        browser, context, ua = launch_patched(p, headless=args.headless, role="human")
        page = context.new_page()
        driver = PageDriver(page)

        def record(visit) -> None:
            anchors.update(anchors_in(visit.raw))
            results.append({"url": visit.url, "status": visit.status, "has_content": has_content(visit, SITES[args.site])})
            log(f"  [{len(results)}] {visit.status} {visit.url}")

        record(driver.goto(resolve(args.base, "/"), rng=rng))

        robots = context.request.get(resolve(args.base, "/robots.txt"))
        disallows = parse_disallows(robots.text()) if robots.ok else []
        log(f"  robots Disallow (respected): {disallows}")

        visited = {normalize_url(page.url)}
        while len(results) < args.pages:
            time.sleep(DELAY_S)
            target = None
            for link in page.locator("nav a[href]").all():
                href = link.evaluate("a => a.href")
                norm = normalize_url(href)
                if (
                    link.is_visible()
                    and same_origin(href, args.base)
                    and norm not in visited
                    and not is_disallowed(urlsplit(href).path, disallows)
                ):
                    target = (link, norm)
                    break
            if target is None:
                log("  no unvisited visible nav link left")
                break
            link, norm = target
            synthetic_interaction(page, rng)  # a person moves/scrolls before clicking
            start = len(driver.doc_responses)
            driver.click_and_wait(link, rng)
            visited.add(norm)
            record(driver.capture(norm, rng, start))
        browser.close()

    emit({
        "scraper": "human_control",
        "user_agent": ua,
        "pages": results,
        "content_pages": sum(r["has_content"] for r in results),
        "anchors_found": sorted(anchors),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
