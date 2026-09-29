"""Shared constants and Playwright helpers for the ScapeBusters demo attackers.

Attackers never self-identify: no custom headers, query params or cookies beyond
what the chosen client naturally sends. Everything is deterministic (fixed page
order, fixed pacing, seeded randomness).
"""
from __future__ import annotations

import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

DEFAULT_BASE = "http://localhost:8000"
INTERSTITIAL_MARKER = "Checking your browser"
ANCHORS = ("Oriel Vantrask", "Hexaquorum", "quasar-reconcile", "velvet-anchor", "ORCHID-7")


@dataclass(frozen=True)
class Site:
    """Upstream behind the edge: fixed page order plus content markers.

    ``marker`` must be in the raw response (HTTP bots see only this); ``rendered``
    must be in the rendered text (browser bots), empty when the HTML is server-rendered.
    """

    pages: tuple[str, ...]
    marker: str
    rendered: str = ""


SITES = {
    # Public links in CampusCart's navigation (Firebase SPA; no authenticated pages).
    "campuscart": Site(
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
    # Local ExampleCorp origin (:8001) used by the pytest validation suites (master plan §13).
    "examplecorp": Site(
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

NAV_TIMEOUT_MS = 20_000
HYDRATE_TIMEOUT_MS = 10_000
INTERSTITIAL_TIMEOUT_MS = 15_000
PATCHED_ARGS = ["--disable-blink-features=AutomationControlled"]
WEBDRIVER_PATCH = "Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => undefined});"
TEXT_JS = "() => { const m = document.querySelector('main#content'); return (m || document.body).innerText; }"
LINKS_JS = "els => els.map(a => a.href)"
DOC_JS = (
    "() => { const n = performance.getEntriesByType('navigation')[0];"
    " return {status: n ? n.responseStatus : 0, ctype: document.contentType}; }"
)
PRE_JS = "() => { const p = document.querySelector('pre'); return p ? p.innerText : (document.body ? document.body.innerText : ''); }"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def emit(result: dict) -> None:
    """Machine-readable result: exactly one JSON object on stdout."""
    print(json.dumps(result, sort_keys=True), flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def anchors_in(text: str) -> list[str]:
    low = text.lower()
    return [a for a in ANCHORS if a.lower() in low]


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def same_origin(url: str, base: str) -> bool:
    a, b = urlsplit(url), urlsplit(base)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


def parse_disallows(robots_text: str) -> list[str]:
    """Disallow paths from the `User-agent: *` group, in file order."""
    out: list[str] = []
    applies = False
    for raw in robots_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            applies = value == "*"
        elif key == "disallow" and applies and value:
            out.append(value)
    return out


def is_disallowed(path: str, disallows: list[str]) -> bool:
    return any(path.startswith(d) for d in disallows)


def desktop_chrome_ua(browser_version: str) -> str:
    """Chrome's reduced UA string for the real bundled browser version."""
    major = browser_version.split(".", 1)[0]
    if sys.platform == "win32":
        platform = "Windows NT 10.0; Win64; x64"
    elif sys.platform == "darwin":
        platform = "Macintosh; Intel Mac OS X 10_15_7"
    else:
        platform = "X11; Linux x86_64"
    return (
        f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


def launch_patched(playwright, headless: bool):
    """Scraper 3 / human-control browser: headed by default, automation flag patched."""
    browser = playwright.chromium.launch(headless=headless, args=PATCHED_ARGS)
    ua = desktop_chrome_ua(browser.version)
    context = browser.new_context(
        user_agent=ua,
        locale="en-US",
        viewport={"width": 1366, "height": 768},
    )
    context.add_init_script(WEBDRIVER_PATCH)
    return browser, context, ua


def synthetic_interaction(page, rng: random.Random) -> None:
    """~12 seeded mouse moves + 2 scrolls, finished within ~1.2 s."""
    x, y = 400.0, 300.0
    for i in range(12):
        x = min(1300.0, max(10.0, x + rng.uniform(-120, 120)))
        y = min(740.0, max(10.0, y + rng.uniform(-90, 90)))
        page.mouse.move(x, y, steps=2)
        page.wait_for_timeout(rng.randint(40, 65))
        if i in (4, 9):
            page.mouse.wheel(0, rng.randint(80, 160))


@dataclass
class Visit:
    url: str
    status: int | None
    content_type: str = ""
    title: str = ""
    text: str = ""
    raw: str = ""
    links: list[str] = field(default_factory=list)
    interstitials: int = 0

    @property
    def is_json(self) -> bool:
        return "json" in self.content_type

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type


class PageDriver:
    """Drives one page; keeps main-frame document responses to read raw JSON/text bodies."""

    def __init__(self, page):
        self.page = page
        self.doc_responses: list = []
        page.on("response", self._on_response)

    def _on_response(self, response) -> None:
        req = response.request
        if req.is_navigation_request() and response.frame == self.page.main_frame:
            self.doc_responses.append(response)

    def _interstitial_visible(self) -> bool:
        try:
            return self.page.get_by_text(INTERSTITIAL_MARKER).count() > 0
        except Exception:  # context destroyed mid-navigation: re-check after load
            self.page.wait_for_load_state("load")
            return self.page.get_by_text(INTERSTITIAL_MARKER).count() > 0

    def wait_past_interstitial(self, rng: random.Random | None) -> int:
        """If the L2 interstitial is showing, optionally interact, then wait for it to go away.

        Returns the number of interstitials observed (0 or 1).
        """
        if not self._interstitial_visible():
            return 0
        if rng is not None:
            synthetic_interaction(self.page, rng)
        self.page.get_by_text(INTERSTITIAL_MARKER).first.wait_for(
            state="detached", timeout=INTERSTITIAL_TIMEOUT_MS
        )
        self.page.wait_for_load_state("load")
        return 1

    def click_and_wait(self, locator, rng: random.Random | None, wait_until: str = "load") -> None:
        with self.page.expect_navigation(wait_until=wait_until, timeout=NAV_TIMEOUT_MS):
            locator.click()

    def goto(self, url: str, rng: random.Random | None, wait_until: str = "domcontentloaded") -> Visit:
        start = len(self.doc_responses)
        self.page.goto(url, wait_until=wait_until, timeout=NAV_TIMEOUT_MS)
        return self.capture(url, rng, start)

    def capture(self, url: str, rng: random.Random | None, start: int) -> Visit:
        """Finish the current navigation (incl. interstitial) and snapshot the page."""
        interstitials = 0
        try:
            interstitials = self.wait_past_interstitial(rng)
        except Exception as exc:  # timeout: still stuck on the interstitial
            log(f"  interstitial did not clear for {url}: {exc.__class__.__name__}")
        # CampusCart is a client-rendered SPA: the document loads before its
        # navigation exists. Wait on observed hydration; routes that render no
        # links (e.g. the SPA fallback for /robots.txt) are logged, not fatal.
        if self.page.locator("#root").count():
            try:
                self.page.locator("#root a[href]").first.wait_for(
                    state="attached", timeout=HYDRATE_TIMEOUT_MS
                )
            except Exception as exc:
                log(f"  no hydrated links for {url}: {exc.__class__.__name__}")
        # Status/content type of the document actually displayed (response events can lag the DOM swap).
        doc = self.page.evaluate(DOC_JS)
        status = doc["status"] or None
        ctype = (doc["ctype"] or "").lower()
        visit = Visit(url=url, status=status, content_type=ctype, interstitials=interstitials)
        if "html" in ctype:
            visit.title = self.page.title()
            visit.text = self.page.evaluate(TEXT_JS) or ""
            visit.raw = self.page.content()
            visit.links = self.page.eval_on_selector_all("a[href]", LINKS_JS)
        else:  # JSON / text: the raw response body, not the browser's viewer markup
            final = self.page.url
            resp = next((r for r in reversed(self.doc_responses[start:]) if r.url == final), None)
            try:
                visit.raw = resp.text() if resp else ""
            except Exception:
                resp = None
            if resp is None:
                visit.raw = self.page.evaluate(PRE_JS) or ""
            visit.text = visit.raw
        return visit


def has_content(visit: Visit, site: Site) -> bool:
    """Real origin content (not interstitial / restricted / throttle pages)."""
    return (
        visit.status == 200
        and site.marker in visit.raw
        and site.rendered in visit.text
        and INTERSTITIAL_MARKER not in visit.raw
    )


def pace(started: float, interval_s: float) -> None:
    """Fixed attacker pacing (attacker behaviour, not a wait on system state)."""
    remaining = interval_s - (time.monotonic() - started)
    if remaining > 0:
        time.sleep(remaining)


def resolve(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/")) if not path.startswith("http") else path
