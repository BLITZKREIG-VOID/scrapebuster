"""Scraper 1 — ordinary HTTP bot (master plan §4, ATK-02).

`requests` default User-Agent plus the SD-4 ``SBDemo/scraper1`` marker, no cookie
persistence (fresh connection/session per request), cycles the fixed page list
with a thread pool. Prints a status histogram and the number of responses
carrying the upstream document marker. Exits 0 after a run; 2 on a refused
base or budget (safe demo mode, sites.py).

    python attacks/ordinary_bot.py --base http://localhost:8000 --requests 100 --threads 10 [--site campuscart|examplecorp]
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
from common import (
    DEFAULT_SITE,
    MAX_REQUESTS,
    MAX_THREADS,
    SAFETY_STOP_EXIT_CODE,
    SITES,
    add_base_args,
    anchors_in,
    check_base,
    check_budget,
    demo_ua,
    emit,
    is_safety_stop_status,
    log,
    resolve,
)

USER_AGENT = demo_ua(requests.utils.default_user_agent(), "scraper1")


def fetch(url: str) -> tuple[str, str]:
    try:
        # module-level get: no cookie jar reuse
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10, allow_redirects=False)
        return str(resp.status_code), resp.text
    except requests.RequestException as exc:
        return f"ERR:{exc.__class__.__name__}", ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_base_args(ap)
    ap.add_argument("--site", choices=sorted(SITES), default=DEFAULT_SITE, help="upstream behind the edge")
    ap.add_argument("--requests", type=int, default=MAX_REQUESTS)
    ap.add_argument("--threads", type=int, default=MAX_THREADS)
    args = ap.parse_args()
    check_base(ap, args)
    check_budget(ap, "requests", args.requests, MAX_REQUESTS)
    check_budget(ap, "threads", args.threads, MAX_THREADS)

    site = SITES[args.site]
    urls = [resolve(args.base, site.pages[i % len(site.pages)]) for i in range(args.requests)]
    results: list[tuple[str, str]] = []
    stop_status: str | None = None
    stop_url: str | None = None

    # At-most-threads in-flight batch scheduling (§Phase 8 Slice A):
    # submit only one batch of size <= threads at a time. Finish the current bounded batch,
    # and if any request returns HTTP 429 or 5xx, dispatch no further batches.
    batch_size = max(1, args.threads)
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        for offset in range(0, len(urls), batch_size):
            batch = urls[offset : offset + batch_size]
            batch_results = list(pool.map(fetch, batch))
            results.extend(batch_results)
            for (status, _), url in zip(batch_results, batch):
                if is_safety_stop_status(status):
                    stop_status = status
                    stop_url = url
                    break
            if stop_status is not None:
                break

    histogram = Counter(status for status, _ in results)
    content_bodies = sum(1 for _, body in results if site.marker in body)
    anchors = sorted({a for _, body in results for a in anchors_in(body)})

    log(f"ordinary_bot: {len(results)} requests -> {args.base} as {USER_AGENT!r}")
    for status, count in sorted(histogram.items()):
        log(f"  status {status}: {count}")
    log(f"  bodies containing '{site.marker}': {content_bodies}")
    emit({
        "scraper": "ordinary_bot",
        "user_agent": USER_AGENT,
        "requests": len(results),
        "status_histogram": dict(sorted(histogram.items())),
        "content_bodies": content_bodies,
        "anchors_found": anchors,
    })

    if stop_status is not None:
        log(
            f"SAFETY STOP: observed HTTP {stop_status} on {stop_url} "
            f"(Phase 10 tradeoff: conservative stop on 429/5xx - edge may emit 429 due to L1, "
            f"no reliable provenance in attack response). Dispatched no further batches."
        )
        return SAFETY_STOP_EXIT_CODE

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
