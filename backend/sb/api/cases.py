"""API router for case endpoints."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..contracts import Case, CaseSummary
from ..provenance import evidence, investigate
from ..store import db

router = APIRouter()


class EvidenceObject(BaseModel):
    name: str
    sha256: str
    bytes: int
    local_path: str
    s3_key: str | None = None
    s3_version_id: str | None = None
    retain_until: str | None = None


class CaseEvidenceResponse(BaseModel):
    manifest: dict[str, Any]
    objects: list[EvidenceObject]
    receipt: dict[str, Any] | None = None


@router.get("/cases", response_model=list[CaseSummary])
async def list_cases() -> list[CaseSummary]:
    return investigate.list_cases()


@router.get("/cases/{case_id}", response_model=Case)
async def get_case(case_id: str) -> Case:
    c = investigate.get_case(case_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return c


@router.get("/cases/{case_id}/evidence", response_model=CaseEvidenceResponse)
async def get_case_evidence(case_id: str) -> CaseEvidenceResponse:
    c = investigate.get_case(case_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    with closing(db.get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT name, sha256, bytes, local_path, s3_key, s3_version_id, retain_until
            FROM evidence_objects
            WHERE case_id = ?
            ORDER BY name ASC
            """,
            (case_id,),
        ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No evidence found for case {case_id}")

    manifest_row = next((r for r in rows if r["name"] == "manifest.json"), None)
    if manifest_row is None:
        raise HTTPException(status_code=404, detail=f"Manifest missing for case {case_id}")

    manifest_path = Path(manifest_row["local_path"])
    if not manifest_path.is_file():
        raise HTTPException(status_code=404, detail=f"Manifest file not found on disk for case {case_id}")

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error reading manifest: {exc}") from exc

    receipt_data = None
    receipt_path = manifest_path.parent / "vault_receipt.json"
    if receipt_path.is_file():
        try:
            receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    objects = [
        EvidenceObject(
            name=r["name"],
            sha256=r["sha256"],
            bytes=r["bytes"],
            local_path=r["local_path"],
            s3_key=r["s3_key"],
            s3_version_id=r["s3_version_id"],
            retain_until=r["retain_until"],
        )
        for r in rows
    ]

    return CaseEvidenceResponse(
        manifest=manifest_data,
        objects=objects,
        receipt=receipt_data,
    )


@router.post("/cases/{case_id}/verify")
async def verify_case(case_id: str) -> dict[str, Any]:
    try:
        return evidence.verify_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
