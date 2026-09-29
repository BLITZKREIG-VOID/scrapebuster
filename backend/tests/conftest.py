import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse


@pytest.fixture(scope="session")
def origin_server():
    import uvicorn

    origin_app = FastAPI()

    @origin_app.get("/{path:path}")
    async def catch(path: str):
        return HTMLResponse(content=f"<main id='content'>Origin {path}</main>")

    config = uvicorn.Config(app=origin_app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    time.sleep(2)
    yield

    server.should_exit = True
    thread.join(timeout=2)


@pytest.fixture(autouse=True)
def reset_proxy_client():
    """
    Reset the httpx client singleton before every test so it is always
    created inside the currently-running event loop.  Without this,
    pytest-asyncio creates a new loop per test but the singleton was bound
    to a previous (now-closed) loop, causing 'Event loop is closed'.
    """
    import sb.edge.proxy as proxy_module
    proxy_module._client = None
    yield
    proxy_module._client = None
