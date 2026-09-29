from urllib.parse import urlsplit

import httpx

from ..config import SB_ORIGIN_URL
from .context import RequestContext

# Global async client for proxying
_client = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=SB_ORIGIN_URL)
    return _client

# Layer 3 lure: the edge owns robots.txt so every upstream (CampusCart has
# none) advertises the TRAP-ROBOTS-01 prefix. Never forwarded upstream.
ROBOTS_TXT = b"User-agent: *\nDisallow: /internal/\n"

# Standard hop-by-hop headers (RFC 7230 §6.1) that must not be forwarded
HOP_BY_HOP_HEADERS = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "trailers",
    "transfer-encoding",
    "upgrade",
})


class UpstreamResponse:
    """Wrapper to fulfill TrapHooks interface"""
    def __init__(self, response: httpx.Response):
        self.content = response.content
        self.status_code = response.status_code
        self.headers = response.headers

async def proxy(ctx: RequestContext) -> httpx.Response:
    request = ctx.request
    method = request.method

    # Strip any scheme/host to ensure path cannot select arbitrary upstream
    raw_path = urlsplit(request.url.path).path
    if not raw_path.startswith("/"):
        raw_path = "/" + raw_path
    url = raw_path

    if method in ("GET", "HEAD") and url == "/robots.txt":
        return httpx.Response(
            200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=ROBOTS_TXT if method == "GET" else b"",
        )
    if request.url.query:
        url += f"?{request.url.query}"
        
    # Filter hop-by-hop headers, including Connection token-nominated headers
    raw_headers = {k.lower(): v for k, v in request.headers.items()}
    connection_tokens = set()
    if "connection" in raw_headers:
        for token in raw_headers["connection"].split(","):
            t = token.strip().lower()
            if t:
                connection_tokens.add(t)

    drop_headers = HOP_BY_HOP_HEADERS | connection_tokens
    headers = {k: v for k, v in raw_headers.items() if k not in drop_headers}

    # The inbound host is localhost:8000; Firebase requires its own hostname.
    # Derive it from the selected origin so local overrides still work.
    headers["host"] = urlsplit(SB_ORIGIN_URL).netloc
    # httpx returns decoded response content, while the pipeline drops the
    # upstream Content-Encoding header. Request identity to keep browser bytes
    # and metadata consistent (Firebase otherwise serves Brotli here).
    headers["accept-encoding"] = "identity"
    # We must read body safely if it's there, but for GET it's usually empty
    # In a full reverse proxy we'd stream this, but for the hackathon we buffer
    body = await request.body()
    if not body:
        headers.pop("content-length", None)
    
    client = get_client()
    response = await client.request(
        method=method,
        url=url,
        headers=headers,
        content=body,
    )
    
    return response
