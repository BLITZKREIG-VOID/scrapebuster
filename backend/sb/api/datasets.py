"""API router for dataset endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..contracts import Dataset, DatasetsResponse
from ..provenance import dataset
from ..provenance.dataset import DatasetValidationError

router = APIRouter()


class DatasetIngestRequest(BaseModel):
    path: str
    role: str


@router.post("/datasets/ingest", response_model=Dataset)
def ingest_dataset(payload: DatasetIngestRequest) -> Dataset:
    path_obj = Path(payload.path)
    if not path_obj.is_file():
        raise HTTPException(status_code=404, detail=f"Dataset file not found: {payload.path}")

    try:
        ds = dataset.ingest(path=path_obj, role=payload.role)
        return ds
    except (DatasetValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/datasets", response_model=DatasetsResponse)
def list_datasets() -> DatasetsResponse:
    datasets = dataset.list_datasets()
    return DatasetsResponse(datasets=datasets)
