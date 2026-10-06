from urllib.parse import urlsplit

import httpx

from ..config import SB_ORIGIN_URL, SB_UPSTREAM_ORIGIN
from .context import RequestContext

# Global async client for proxying
_client = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        origin = SB_UPSTREAM_ORIGIN or SB_ORIGIN_URL
        _client = httpx.AsyncClient(base_url=origin, follow_redirects=False)
    return _client


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
    """Wrapper to fulfill offense transformation interface."""

    def __init__(self, response: httpx.Response):
        self.content = response.content
        self.status_code = response.status_code
        self.headers = response.headers


async def proxy(ctx: RequestContext) -> httpx.Response:
    """Proxy request to upstream origin without site-specific lures or hardcoding."""
    request = ctx.request
    method = request.method

    # Strip any scheme/host to ensure path cannot select arbitrary upstream
    raw_path = urlsplit(request.url.path).path
    if not raw_path.startswith("/"):
        raw_path = "/" + raw_path
    url = raw_path

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

    # Derive host from configured upstream origin
    origin = SB_UPSTREAM_ORIGIN or SB_ORIGIN_URL
    if origin:
        netloc = urlsplit(origin).netloc
        if netloc:
            headers["host"] = netloc

    # Request identity encoding so response content is uncompressed for mutation
    headers["accept-encoding"] = "identity"

    # Forward body safely
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
