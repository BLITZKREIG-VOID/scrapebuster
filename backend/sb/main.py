from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .edge.pipeline import handle


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from .edge.proxy import client
    await client.aclose()

app = FastAPI(title="ScapeBusters", lifespan=lifespan)

@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok"})

@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def api_namespace(path: str, request: Request):
    return JSONResponse(content={"msg": f"API stub for {path}"})

@app.api_route("/_sb/{path:path}", methods=["GET", "POST"])
async def sb_namespace(path: str, request: Request):
    return JSONResponse(content={"msg": f"SB stub for {path}"})

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def catch_all(path: str, request: Request):
    # Route through the edge pipeline
    return await handle(request)
