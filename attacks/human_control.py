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
    DEFAULT_SITE,
    SAFETY_STOP_EXIT_CODE,
    SITES,
    PageDriver,
    add_base_args,
    anchors_in,
    check_base,
    check_budget,
    emit,
    has_content,
    is_disallowed,
    is_safety_stop_status,
    launch_patched,
    log,
    normalize_url,
    parse_disallows,
    resolve,
    same_origin,
    synthetic_interaction,
)
from playwright.sync_api import Error as PlaywrightError
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
    safety_stop: tuple[int | str, str] | None = None

    with sync_playwright() as p:
        browser, context, ua = launch_patched(p, headless=args.headless, role="human")
        page = context.new_page()
        driver = PageDriver(page)

        def record(visit) -> None:
            anchors.update(anchors_in(visit.raw))
            results.append({"url": visit.url, "status": visit.status, "has_content": has_content(visit, SITES[args.site])})
            log(f"  [{len(results)}] {visit.status} {visit.url}")

        home_url = resolve(args.base, "/")
        try:
            first_visit = driver.goto(home_url, rng=rng)
            record(first_visit)
            if is_safety_stop_status(first_visit.status):
                safety_stop = (first_visit.status, home_url)
        except PlaywrightError as exc:
            log(f"  {home_url}: {exc.__class__.__name__}: {exc}")
            results.append({"url": home_url, "status": None, "has_content": False})

        disallows: list[str] = []
        if not safety_stop:
            robots_url = resolve(args.base, "/robots.txt")
            try:
                robots = context.request.get(robots_url)
                if is_safety_stop_status(robots.status):
                    safety_stop = (robots.status, robots_url)
                else:
                    disallows = parse_disallows(robots.text()) if robots.ok else []
                    log(f"  robots Disallow (respected): {disallows}")
            except PlaywrightError as exc:
                log(f"  robots.txt request failed: {exc.__class__.__name__}: {exc}")

        if not safety_stop:
            visited = {normalize_url(page.url)}
            while not safety_stop and len(results) < args.pages:
                time.sleep(DELAY_S)
                target = None
                for link in page.locator("nav a[href]").all():
                    try:
                        href = link.evaluate("a => a.href")
                    except PlaywrightError:
                        continue
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
                try:
                    driver.click_and_wait(link, rng)
                    visited.add(norm)
                    visit = driver.capture(norm, rng, start)
                    record(visit)
                    if is_safety_stop_status(visit.status):
                        safety_stop = (visit.status, norm)
                        break
                except PlaywrightError as exc:
                    log(f"  {norm}: {exc.__class__.__name__}: {exc}")
                    results.append({"url": norm, "status": None, "has_content": False})
        browser.close()

    emit({
        "scraper": "human_control",
        "user_agent": ua,
        "pages": results,
        "content_pages": sum(r["has_content"] for r in results),
        "anchors_found": sorted(anchors),
    })

    if safety_stop:
        status, url = safety_stop
        log(
            f"SAFETY STOP: observed HTTP {status} on {url} "
            f"(Phase 10 tradeoff: conservative stop on 429/5xx - edge may emit 429 due to L1, "
            f"no reliable provenance in attack response). Stopped navigation."
        )
        return SAFETY_STOP_EXIT_CODE

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
