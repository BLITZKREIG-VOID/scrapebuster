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

class UpstreamResponse:
    """Wrapper to fulfill TrapHooks interface"""
    def __init__(self, response: httpx.Response):
        self.content = response.content
        self.status_code = response.status_code
        self.headers = response.headers

async def proxy(ctx: RequestContext) -> httpx.Response:
    request = ctx.request
    method = request.method
    url = request.url.path
    if request.url.query:
        url += f"?{request.url.query}"
        
    headers = dict(request.headers)
    # Strip hop-by-hop headers
    headers.pop("host", None)
    
    # We must read body safely if it's there, but for GET it's usually empty
    # In a full reverse proxy we'd stream this, but for the hackathon we buffer
    body = await request.body()
    
    client = get_client()
    response = await client.request(
        method=method,
        url=url,
        headers=headers,
        content=body,
    )
    
    return response
