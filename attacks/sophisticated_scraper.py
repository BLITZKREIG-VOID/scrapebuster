"""Scraper 3 — sophisticated scraper (master plan §5–§6, §9, ATK-04).

Headed Chromium (``--headless`` optional) with the AutomationControlled blink
feature disabled, navigator.webdriver patched to undefined, a realistic desktop
Chrome UA for the bundled browser version, locale en-US, viewport 1366x768.
On an L2 interstitial it performs ~12 seeded mouse moves + 2 scrolls within
~1.2 s and waits for the interstitial to navigate away.

Crawl order (fixed): ``/`` -> ``/robots.txt`` (parse Disallow) -> every disallowed
path -> BFS over *all* ``<a href>`` (hidden ones included), same-origin, deduped,
max 20 pages (SD-2 cap), 2 s ± 0.5 s (seeded) between pages. Ignores robots.txt.
UA carries the SD-4 ``SBDemo/scraper3`` marker; ``--base`` must be loopback (SD-1).
Writes one dataset JSONL record per page: {"url","fetched_at","title","text"}.

    python attacks/sophisticated_scraper.py --base http://localhost:8000 \
        --out data/datasets/<run_id>_scraper3.jsonl [--headless] [--dump-signals]
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import deque
from pathlib import Path

from common import (
    PageDriver,
    SAFETY_STOP_EXIT_CODE,
    add_base_args,
    anchors_in,
    check_base,
    emit,
    is_safety_stop_status,
    launch_patched,
    log,
    normalize_url,
    parse_disallows,
    resolve,
    same_origin,
    utc_now,
)
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

SEED = 1337
MAX_PAGES = 20
DELAY_S = 2.0
JITTER_S = 0.5


def attach_signal_dump(page) -> None:
    """H9 tuning aid: intercept /_sb/verify and print the payload + server verdict (read-only passthrough)."""

    def handle(route):
        log(f"[verify request] {route.request.post_data}")
        response = route.fetch()
        log(f"[verify response {response.status}] {response.text()}")
        route.fulfill(response=response)

    page.route("**/_sb/verify", handle)


def to_record(visit) -> dict | None:
    if visit.status is None or visit.status >= 400:
        return None
    if visit.is_html:
        return {"url": visit.url, "fetched_at": utc_now(), "title": visit.title, "text": visit.text}
    if visit.is_json:
        return {"url": visit.url, "fetched_at": utc_now(), "title": "", "text": visit.raw}
    return None


def crawl(base: str, out: Path, headless: bool, dump_signals: bool) -> dict:
    move_rng = random.Random(SEED)
    delay_rng = random.Random(SEED + 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    visited: list[dict] = []
    records = 0
    anchors: set[str] = set()

    with sync_playwright() as p, out.open("w", encoding="utf-8") as fh:
        browser, context, ua = launch_patched(p, headless=headless, role="scraper3")
        page = context.new_page()
        if dump_signals:
            attach_signal_dump(page)
        driver = PageDriver(page)
        seen: set[str] = set()
        queue: deque[str] = deque()
        safety_stop: tuple[int | str, str] | None = None

        def visit(url: str):
            nonlocal records, safety_stop
            if visited:
                time.sleep(DELAY_S + delay_rng.uniform(-JITTER_S, JITTER_S))
            try:
                v = driver.goto(url, rng=move_rng)
            except PlaywrightError as exc:
                log(f"  {url}: {exc.__class__.__name__}: {exc}")
                visited.append({"url": url, "status": None})
                return None
            visited.append({"url": url, "status": v.status, "interstitial": bool(v.interstitials)})
            log(f"  [{len(visited):02d}] {v.status} {url}")
            if is_safety_stop_status(v.status):
                safety_stop = (v.status, url)
                return v
            rec = to_record(v)
            if rec is not None:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                records += 1
                anchors.update(anchors_in(rec["text"]))
            return v

        def enqueue(links: list[str]) -> None:
            for link in links:
                if len(queue) >= MAX_PAGES:
                    break
                if not link.startswith("http") or not same_origin(link, base):
                    continue
                norm = normalize_url(link)
                if norm not in seen:
                    seen.add(norm)
                    queue.append(norm)

        home = normalize_url(resolve(base, "/"))
        seen.add(home)
        first = visit(home)
        if first is not None and not safety_stop:
            enqueue(first.links)

        disallows: list[str] = []
        if not safety_stop:
            robots_url = normalize_url(resolve(base, "/robots.txt"))
            seen.add(robots_url)
            try:
                robots = driver.goto(robots_url, rng=move_rng)
                if is_safety_stop_status(robots.status):
                    safety_stop = (robots.status, robots_url)
                else:
                    disallows = parse_disallows(robots.raw)[:MAX_PAGES]
            except PlaywrightError as exc:
                log(f"  robots.txt: {exc.__class__.__name__}: {exc}")
            log(f"  robots Disallow: {disallows}")

        if not safety_stop:
            for path in disallows:
                # A malformed robots Disallow must never choose a different host.
                if not path.startswith("/") or path.startswith("//"):
                    continue
                if len(visited) >= MAX_PAGES:
                    break
                url = normalize_url(resolve(base, path))
                if not same_origin(url, base):
                    continue
                if url in seen and url not in queue:
                    continue
                seen.add(url)
                if url in queue:
                    queue.remove(url)
                v = visit(url)
                if safety_stop:
                    break
                if v is not None:
                    enqueue(v.links)

        if not safety_stop:
            while queue and len(visited) < MAX_PAGES:
                v = visit(queue.popleft())
                if safety_stop:
                    break
                if v is not None:
                    enqueue(v.links)
        browser.close()

    res = {
        "scraper": "sophisticated_scraper",
        "user_agent": ua,
        "out": str(out),
        "pages": len(visited),
        "records": records,
        "visited": visited,
        "disallows": disallows,
        "anchors_found": sorted(anchors),
    }
    if safety_stop:
        res["safety_stop"] = {"status": safety_stop[0], "url": safety_stop[1]}
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_base_args(ap)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--headless", action="store_true", help="fallback when no display is available")
    ap.add_argument("--dump-signals", action="store_true", help="log /_sb/verify payloads (H9 tuning)")
    args = ap.parse_args()
    check_base(ap, args)

    result = crawl(args.base, args.out, args.headless, args.dump_signals)
    log(f"sophisticated_scraper: {result['pages']} pages, {result['records']} records -> {result['out']}")
    log(f"  anchors in collected text: {result['anchors_found'] or 'none'}")
    emit(result)
    if "safety_stop" in result:
        stop = result["safety_stop"]
        log(
            f"SAFETY STOP: observed HTTP {stop['status']} on {stop['url']} "
            f"(Phase 10 tradeoff: conservative stop on 429/5xx - edge may emit 429 due to L1, "
            f"no reliable provenance in attack response). Stopped crawl."
        )
        return SAFETY_STOP_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
