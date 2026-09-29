"""Scraper 1 — ordinary HTTP bot (master plan §4, ATK-02).

`requests` default User-Agent, no cookie persistence (fresh connection/session per
request), cycles the fixed page list with a thread pool. Prints a status histogram
and the number of bodies that carried real origin content. Always exits 0.

    python attacks/ordinary_bot.py --base http://127.0.0.1:8000 --requests 100 --threads 10
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
from common import BRAND, DEFAULT_BASE, PAGES, anchors_in, emit, log, resolve


def fetch(url: str) -> tuple[str, str]:
    try:
        resp = requests.get(url, timeout=10, allow_redirects=False)  # module-level get: no cookie jar reuse
        return str(resp.status_code), resp.text
    except requests.RequestException as exc:
        return f"ERR:{exc.__class__.__name__}", ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--threads", type=int, default=10)
    args = ap.parse_args()

    urls = [resolve(args.base, PAGES[i % len(PAGES)]) for i in range(args.requests)]
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        results = list(pool.map(fetch, urls))

    histogram = Counter(status for status, _ in results)
    content_bodies = sum(1 for _, body in results if BRAND in body)
    anchors = sorted({a for _, body in results for a in anchors_in(body)})

    log(f"ordinary_bot: {len(results)} requests -> {args.base}")
    for status, count in sorted(histogram.items()):
        log(f"  status {status}: {count}")
    log(f"  bodies containing '{BRAND}': {content_bodies}")
    emit({
        "scraper": "ordinary_bot",
        "requests": len(results),
        "status_histogram": dict(sorted(histogram.items())),
        "content_bodies": content_bodies,
        "anchors_found": anchors,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
