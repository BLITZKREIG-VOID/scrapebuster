"""KB Ingestion API for ScrapeBuster Phase 3.

Provides catalog, brand schema, and document ingestion endpoints.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from sb.kb.engine import get_kb_engine
from sb.kb.models import (
    KBIngestRequest,
    KBIngestResponse,
    KBQuery,
    KBQueryResponse,
    KBStats,
)

logger = logging.getLogger("sb.kb.ingest")

router = APIRouter(prefix="/kb", tags=["kb"])


@router.post("/ingest", response_model=KBIngestResponse)
async def ingest_document(request: KBIngestRequest) -> KBIngestResponse:
    """Ingest a document into the KB."""
    engine = get_kb_engine()
    try:
        return engine.ingest(request)
    except Exception as exc:
        logger.error("Document ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest/catalog", response_model=KBIngestResponse)
async def ingest_catalog(catalog: dict[str, Any]) -> KBIngestResponse:
    """Ingest a product catalog (JSON)."""
    engine = get_kb_engine()
    try:
        return engine.ingest_catalog(catalog)
    except Exception as exc:
        logger.error("Catalog ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest/brand", response_model=KBIngestResponse)
async def ingest_brand(brand: dict[str, Any]) -> KBIngestResponse:
    """Ingest brand schema/guidelines."""
    engine = get_kb_engine()
    try:
        return engine.ingest_brand_schema(brand)
    except Exception as exc:
        logger.error("Brand schema ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/query", response_model=KBQueryResponse)
async def query_kb(query: KBQuery) -> KBQueryResponse:
    """Query the knowledge base."""
    engine = get_kb_engine()
    try:
        return engine.query(query)
    except Exception as exc:
        logger.error("KB query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/documents")
async def list_documents(
    source: Optional[str] = Query(None, description="Filter by source"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """List KB documents."""
    engine = get_kb_engine()
    return engine.list_documents(source, limit, offset)


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str) -> dict[str, Any]:
    """Get a document by ID."""
    engine = get_kb_engine()
    doc = engine.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, Any]:
    """Delete a document."""
    engine = get_kb_engine()
    ok = engine.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete document")
    return {"status": "deleted", "doc_id": doc_id}


@router.get("/stats", response_model=KBStats)
async def get_stats() -> KBStats:
    """Get KB statistics."""
    engine = get_kb_engine()
    return engine.get_stats()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check for KB engine and backends."""
    engine = get_kb_engine()
    return engine.health_check()