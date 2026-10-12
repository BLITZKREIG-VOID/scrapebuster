"""KB/RAG Engine for ScrapeBuster Phase 3.

Provides configurable, offline-capable knowledge base with local vector store,
configurable external backend support, catalog/brand/schema ingestion,
and deterministic offline fallback.
"""

from __future__ import annotations

from .engine import KBEngine, get_kb_engine
from .models import KBDocument, KBChunk, KBQuery, KBQueryResponse, KBResult
from .store import KBStore, get_kb_store
from .ingest import router as ingest_router

__all__ = [
    "KBEngine",
    "get_kb_engine",
    "KBDocument",
    "KBChunk",
    "KBQuery",
    "KBQueryResponse",
    "KBResult",
    "KBStore",
    "get_kb_store",
    "ingest_router",
]