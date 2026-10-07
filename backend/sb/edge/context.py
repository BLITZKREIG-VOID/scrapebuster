import hashlib

from fastapi import Request


class RequestContext:
    def __init__(self, request: Request | None = None):
        self.request = request
        self.ip = request.client.host if (request and request.client) else "127.0.0.1"
        self.user_agent = request.headers.get("user-agent", "") if request else ""
        self.path = request.url.path if request else "/"

        # Server-side client key derivation
        raw_key = f"{self.ip}|{self.user_agent}".encode()
        self.client_key = hashlib.sha256(raw_key).hexdigest()[:16]

        # Header ordering fingerprint
        headers_order = ",".join(k.lower() for k in request.headers) if request else ""
        self.header_fp = hashlib.sha256(headers_order.encode("utf-8")).hexdigest()[:16]

        self.is_document = not (
            self.path.startswith("/api/")
            or self.path.startswith("/static/")
            or self.path == "/health"
            or self.path == "/favicon.ico"
        )


def build_context(request: Request) -> RequestContext:
    return RequestContext(request)
