"""API router for probe endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..provenance import doberman, investigate
from ..contracts import ProbeListResponse, ProbeRun, ProbeRunResponse

router = APIRouter()


class ProbeRunRequest(BaseModel):
    target_dataset_id: str | None = None
    control_dataset_id: str | None = None
    canary_ids: list[str] | None = None


@router.post("/probes/run", response_model=ProbeRunResponse)
def run_probe(payload: ProbeRunRequest | None = None) -> ProbeRunResponse:
    req = payload or ProbeRunRequest()
    try:
        res = investigate.investigate(
            target_dataset_id=req.target_dataset_id,
            control_dataset_id=req.control_dataset_id,
            canary_ids=req.canary_ids,
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
def list_probes() -> ProbeListResponse:
    probes = doberman.list_probes()
    return ProbeListResponse(probes=[ProbeRun.model_validate(p) for p in probes])


@router.get("/probes/{probe_id}", response_model=ProbeRun)
def get_probe(probe_id: str) -> ProbeRun:
    probe = doberman.get_probe(probe_id)
    if probe is None:
        raise HTTPException(status_code=404, detail=f"Probe run {probe_id} not found")
    return ProbeRun.model_validate(probe)
