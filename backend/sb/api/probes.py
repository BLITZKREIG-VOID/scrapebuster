"""API router for probe endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..provenance import doberman, investigate

router = APIRouter()


class ProbeResult(BaseModel):
    result_id: str
    canary_id: str
    prompt: str
    retrieved: list[dict[str, Any]]
    response_text: str
    response_sha256: str
    latency_ms: int
    ts: str


class ProbeRun(BaseModel):
    probe_id: str
    target: str
    status: str
    dataset_id: str
    dataset_sha256: str
    started_at: str
    finished_at: str | None = None
    model: dict[str, Any]
    results: list[ProbeResult] = []


class ProbeRunRequest(BaseModel):
    target_dataset_id: str | None = None
    control_dataset_id: str | None = None
    canary_ids: list[str] | None = None


class ProbeRunResponse(BaseModel):
    probe_ids: dict[str, str]
    case_id: str | None = None


class ProbeListResponse(BaseModel):
    probes: list[ProbeRun]


@router.post("/probes/run", response_model=ProbeRunResponse)
async def run_probe(payload: ProbeRunRequest = ProbeRunRequest()) -> ProbeRunResponse:
    try:
        res = investigate.investigate(
            target_dataset_id=payload.target_dataset_id,
            control_dataset_id=payload.control_dataset_id,
            canary_ids=payload.canary_ids,
        )
        return ProbeRunResponse.model_validate(res)
    except ValueError as exc:
        msg = str(exc)
        if "no target dataset" in msg.lower() or "no control dataset" in msg.lower():
            raise HTTPException(status_code=409, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/probes", response_model=ProbeListResponse)
async def list_probes() -> ProbeListResponse:
    probes = doberman.list_probes()
    return ProbeListResponse(probes=[ProbeRun.model_validate(p) for p in probes])


@router.get("/probes/{probe_id}", response_model=ProbeRun)
async def get_probe(probe_id: str) -> ProbeRun:
    probe = doberman.get_probe(probe_id)
    if probe is None:
        raise HTTPException(status_code=404, detail=f"Probe run {probe_id} not found")
    return ProbeRun.model_validate(probe)
