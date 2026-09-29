"""Demo control API — master plan §16 (Arnav).

Mount in ``sb/main.py`` (Anirudh): ``app.include_router(sb.api.demo.router)``.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from sb.demo import DemoBusy
from sb.demo import golden, runner
from sb.demo.reset import reset_demo

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class RunRequest(BaseModel):
    step: int | None = Field(default=None, ge=1, le=len(runner.STEPS))


@router.post("/reset")
def post_reset() -> dict:
    """``{ok, run_id, checks: [{name, ok, detail}]}``; 409 while a run holds the lock."""
    try:
        return reset_demo()
    except DemoBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/run")
def post_run(body: RunRequest | None = Body(default=None)) -> dict:
    """Start all steps (or one) in the background; returns the initial ``DemoStatus``."""
    try:
        return runner.start(body.step if body else None)
    except DemoBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status")
def get_status() -> dict:
    return runner.get_status()


@router.post("/restore-golden")
def post_restore_golden() -> dict:
    try:
        return golden.restore()
    except DemoBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except golden.GoldenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
