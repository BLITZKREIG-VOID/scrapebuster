"""Demo control API — master plan §16 (Arnav).

Mount in ``sb/main.py`` (Anirudh): ``app.include_router(sb.api.demo.router)``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from sb.contracts import DemoResetResponse, DemoStatus
from sb.demo import DemoBusy, golden, runner
from sb.demo.reset import reset_demo

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class RunRequest(BaseModel):
    step: int | None = Field(default=None, ge=1, le=len(runner.STEPS))


@router.post("/reset", response_model=DemoResetResponse)
def post_reset() -> DemoResetResponse:
    """``{ok, run_id, checks: [{name, ok, detail}]}``; 409 while a run holds the lock."""
    try:
        return DemoResetResponse.model_validate(reset_demo())
    except DemoBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/run", response_model=DemoStatus)
def post_run(body: Annotated[RunRequest | None, Body()] = None) -> DemoStatus:
    """Start all steps (or one) in the background; returns the initial ``DemoStatus``."""
    try:
        return DemoStatus.model_validate(runner.start(body.step if body else None))
    except DemoBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status", response_model=DemoStatus)
def get_status() -> DemoStatus:
    return DemoStatus.model_validate(runner.get_status())


@router.post("/restore-golden")
def post_restore_golden() -> dict:
    try:
        return golden.restore()
    except DemoBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except golden.GoldenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
