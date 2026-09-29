"""API router for canary endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..canary import registry
from ..contracts import Canary, CanaryDetail, CanariesResponse

router = APIRouter()


@router.get("/canaries", response_model=CanariesResponse)
def list_canaries() -> CanariesResponse:
    canaries = registry.list_canaries()
    return CanariesResponse(canaries=canaries)


@router.get("/canaries/{canary_id}", response_model=CanaryDetail)
def get_canary(canary_id: str) -> CanaryDetail:
    canary = registry.get(canary_id)
    if canary is None:
        raise HTTPException(status_code=404, detail=f"Canary {canary_id} not found")

    pub = registry.get_publication(canary_id)
    exps = registry.list_exposures(canary_id)

    data = canary.model_dump()
    data["publication"] = pub
    data["exposures"] = exps
    return CanaryDetail.model_validate(data)
