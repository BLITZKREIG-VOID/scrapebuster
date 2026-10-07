import os
from urllib.parse import urlsplit

import httpx

from ..config import SB_UPSTREAM_ORIGIN
from .context import RequestContext

# Global async client for proxying
_client = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        origin = os.getenv("SB_UPSTREAM_ORIGIN", SB_UPSTREAM_ORIGIN)
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

    # Preserve raw encoded path/query bytes from ASGI scope where available
    scope = getattr(request, "scope", {})
    raw_path_bytes = scope.get("raw_path") if isinstance(scope, dict) else None
    if raw_path_bytes:
        path = raw_path_bytes.decode("latin1")
        if not path.startswith("/"):
            path = "/" + path
    else:
        raw_path = urlsplit(request.url.path).path
        if not raw_path.startswith("/"):
            raw_path = "/" + raw_path
        path = raw_path

    query_bytes = scope.get("query_string") if isinstance(scope, dict) else None
    if query_bytes:
        url = f"{path}?{query_bytes.decode('latin1')}"
    elif request.url.query:
        url = f"{path}?{request.url.query}"
    else:
        url = path

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

    # Derive host from canonical configured upstream origin
    origin = os.getenv("SB_UPSTREAM_ORIGIN", SB_UPSTREAM_ORIGIN)
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
