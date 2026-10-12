"""KB Engine: High-level RAG interface for ScrapeBuster Phase 3.

Provides configurable, offline-capable knowledge base with:
- Local vector store (SQLite with embeddings)
- Configurable external backend support (pluggable)
- Catalog/brand/schema ingestion
- Deterministic offline fallback
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from sb.kb.models import (
    KBQuery,
    KBQueryResponse,
    KBResult,
    KBIngestRequest,
    KBIngestResponse,
    KBStats,
)
from sb.kb.store import get_kb_store

logger = logging.getLogger("sb.kb.engine")


class ExternalKBBackend:
    """Interface for external KB backends (e.g., pgvector, Pinecone, Weaviate)."""
    
    def ingest(self, doc_id: str, chunks: list[dict[str, Any]]) -> bool:
        """Ingest document chunks. Return True on success."""
        raise NotImplementedError
    
    def query(self, query_embedding: list[float], top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query by embedding vector."""
        raise NotImplementedError
    
    def delete(self, doc_id: str) -> bool:
        """Delete document."""
        raise NotImplementedError
    
    def health_check(self) -> bool:
        """Check backend health."""
        raise NotImplementedError


class KBEngine:
    """Main KB/RAG engine with local and external backend support."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._local_store = get_kb_store()
        self._external_backend: Optional[ExternalKBBackend] = None
        self._lock = threading.RLock()
        self._initialized = False
        self._embedding_cache: dict[str, list[float]] = {}
        
        # Initialize external backend if configured
        self._init_external_backend()
    
    def _init_external_backend(self) -> None:
        """Initialize external KB backend if configured."""
        backend_type = self.config.get("external_backend", "").lower()
        if not backend_type:
            logger.info("No external KB backend configured; using local store only")
            return
        
        try:
            if backend_type == "pgvector":
                from sb.kb.backends.pgvector import PgVectorBackend
                self._external_backend = PgVectorBackend(self.config.get("pgvector", {}))
            elif backend_type == "pinecone":
                from sb.kb.backends.pinecone import PineconeBackend
                self._external_backend = PineconeBackend(self.config.get("pinecone", {}))
            elif backend_type == "weaviate":
                from sb.kb.backends.weaviate import WeaviateBackend
                self._external_backend = WeaviateBackend(self.config.get("weaviate", {}))
            else:
                logger.warning("Unknown external KB backend: %s", backend_type)
                return
            
            if self._external_backend.health_check():
                logger.info("External KB backend initialized: %s", backend_type)
            else:
                logger.warning("External KB backend health check failed: %s", backend_type)
                self._external_backend = None
        except ImportError:
            logger.warning("External KB backend %s not available (missing dependencies)", backend_type)
        except Exception as exc:
            logger.error("Failed to initialize external KB backend: %s", exc)
    
    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text. Uses deterministic hash-based embedding for offline mode."""
        # Check cache first
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        
        # Deterministic hash-based embedding (offline-capable)
        # This is a simple hash-based embedding for deterministic offline operation
        import hashlib
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        # Convert to 384-dim vector (common embedding size)
        embedding = []
        for i in range(0, min(len(hash_bytes), 48), 6):
            chunk = hash_bytes[i:i+6]
            if len(chunk) == 6:
                val = int.from_bytes(chunk, "big") / (2**48 - 1)
                embedding.append(val * 2 - 1)  # Normalize to [-1, 1]
        
        # Pad to 384 dimensions
        while len(embedding) < 384:
            embedding.append(0.0)
        
        self._embedding_cache[text] = embedding
        return embedding
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap
            if start >= len(text):
                break
        return chunks
    
    def ingest(self, request: KBIngestRequest) -> KBIngestResponse:
        """Ingest a document into the KB."""
        with self._lock:
            # Add document
            doc_id = self._local_store.add_document(
                title=request.title,
                content=request.content,
                source=request.source,
                doc_type=request.doc_type,
                metadata=request.metadata,
            )
            
            # Chunk the content
            chunks = self._chunk_text(request.content, request.chunk_size, request.chunk_overlap)
            chunks_created = 0
            
            for i, chunk_text in enumerate(chunks):
                # Generate embedding
                embedding = self._get_embedding(chunk_text)
                
                # Add to local store
                chunk_id = self._local_store.add_chunk(
                    doc_id=doc_id,
                    content=chunk_text,
                    chunk_index=i,
                    embedding=embedding,
                    metadata={"chunk_index": i, "total_chunks": len(chunks)},
                )
                chunks_created += 1
                
                # Also ingest to external backend if available
                if self._external_backend:
                    try:
                        self._external_backend.ingest(doc_id, [{
                            "chunk_id": chunk_id,
                            "content": chunk_text,
                            "embedding": embedding,
                            "doc_id": doc_id,
                            "index": i,
                        }])
                    except Exception as exc:
                        logger.warning("External backend ingest failed for %s: %s", doc_id, exc)
            
            logger.info("Ingested document %s with %d chunks", doc_id, chunks_created)
            return KBIngestResponse(doc_id=doc_id, chunks_created=chunks_created, status="success")
    
    def ingest_catalog(self, catalog_data: dict[str, Any]) -> KBIngestResponse:
        """Ingest a product catalog."""
        # Convert catalog to documents
        title = catalog_data.get("title", "Product Catalog")
        content = json.dumps(catalog_data, ensure_ascii=False, indent=2)
        
        request = KBIngestRequest(
            title=title,
            content=content,
            source="catalog",
            doc_type="json",
            metadata={"catalog_id": catalog_data.get("id", "")},
        )
        return self.ingest(request)
    
    def ingest_brand_schema(self, brand_data: dict[str, Any]) -> KBIngestResponse:
        """Ingest brand schema/guidelines."""
        title = brand_data.get("title", "Brand Schema")
        content = json.dumps(brand_data, ensure_ascii=False, indent=2)
        
        request = KBIngestRequest(
            title=title,
            content=content,
            source="brand",
            doc_type="json",
            metadata={"brand_id": brand_data.get("id", "")},
        )
        return self.ingest(request)
    
    def query(self, query: KBQuery) -> KBQueryResponse:
        """Query the KB with automatic fallback to local store."""
        import time
        start_time = time.perf_counter()
        fallback_used = False
        
        # Generate query embedding
        query_embedding = self._get_embedding(query.query)
        
        # Try external backend first if available
        results = []
        if self._external_backend:
            try:
                ext_results = self._external_backend.query(
                    query_embedding=query.query_embedding,
                    top_k=query.top_k,
                    filters=query.filters,
                )
                results = ext_results
            except Exception as exc:
                logger.warning("External KB query failed, falling back to local: %s", exc)
                fallback_used = True
        
        # Fallback to local store
        if not results or fallback_used:
            local_results = self._local_store.search_chunks(
                query_embedding=query_embedding,
                query_text=query.query if fallback_used else None,
                top_k=query.top_k,
                source=query.filters.get("source"),
            )
            results = local_results
            fallback_used = True
        
        # Convert to KBResult objects
        kb_results = []
        for r in results[:query.top_k]:
            metadata = r.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            kb_results.append(KBResult(
                chunk_id=r.get("chunk_id", ""),
                doc_id=r.get("doc_id", ""),
                title=r.get("title", ""),
                content=r.get("content", "") if query.include_content else "",
                score=float(r.get("score", 0.0)),
                metadata=metadata,
                source=r.get("source", ""),
                chunk_index=r.get("chunk_index", 0),
            ))
        
        query_time_ms = (time.perf_counter() - start_time) * 1000
        
        return KBQueryResponse(
            query=query.query,
            results=kb_results,
            total_found=len(results),
            query_time_ms=query_time_ms,
            fallback_used=fallback_used,
        )
    
    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Get document by ID."""
        return self._local_store.get_document(doc_id)
    
    def list_documents(self, source: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """List documents."""
        return self._local_store.list_documents(source, limit, offset)
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document from all backends."""
        with self._lock:
            local_ok = self._local_store.delete_document(doc_id)
            ext_ok = True
            if self._external_backend:
                try:
                    ext_ok = self._external_backend.delete(doc_id)
                except Exception:
                    ext_ok = False
            return local_ok and ext_ok
    
    def get_stats(self) -> KBStats:
        """Get KB statistics."""
        stats = self._local_store.get_stats()
        return KBStats(**stats)
    
    def health_check(self) -> dict[str, Any]:
        """Check health of all backends."""
        local_ok = True
        ext_ok = self._external_backend is not None
        if ext_ok:
            try:
                ext_ok = self._external_backend.health_check()
            except Exception:
                ext_ok = False
        
        return {
            "local_store": "healthy" if local_ok else "unhealthy",
            "external_backend": "healthy" if ext_ok else ("unhealthy" if ext_ok else "not_configured"),
            "overall": "healthy" if local_ok and (not self._external_backend or ext_ok) else "degraded",
        }


# Global KB engine instance
_kb_engine: KBEngine | None = None
_engine_lock = threading.Lock()


def get_kb_engine(config: dict[str, Any] | None = None) -> KBEngine:
    """Get or create global KB engine instance."""
    global _kb_engine
    with _engine_lock:
        if _kb_engine is None:
            _kb_engine = KBEngine(config)
        return _kb_engine