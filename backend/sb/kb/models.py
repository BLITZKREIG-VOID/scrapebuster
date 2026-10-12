"""KB/RAG data models for ScrapeBuster Phase 3."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass
class KBDocument:
    """A document in the knowledge base."""
    doc_id: str
    title: str
    content: str
    source: str  # "catalog", "brand", "schema", "manual"
    doc_type: str  # "html", "json", "markdown", "text"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    chunk_ids: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "doc_type": self.doc_type,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "chunk_ids": self.chunk_ids,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KBDocument":
        return cls(
            doc_id=data["doc_id"],
            title=data["title"],
            content=data["content"],
            source=data["source"],
            doc_type=data["doc_type"],
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
            chunk_ids=data.get("chunk_ids", []),
        )


@dataclass
class KBChunk:
    """A chunk of a document for vector retrieval."""
    chunk_id: str
    doc_id: str
    content: str
    chunk_index: int
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KBChunk":
        return cls(
            chunk_id=data["chunk_id"],
            doc_id=data["doc_id"],
            content=data["content"],
            chunk_index=data["chunk_index"],
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", now_iso()),
        )


class KBQuery(BaseModel):
    """A query to the knowledge base."""
    query: str = Field(..., description="Natural language query or search text")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    filters: dict[str, Any] = Field(default_factory=dict, description="Metadata filters")
    include_content: bool = Field(default=True, description="Include chunk content in results")
    session_id: str | None = Field(default=None, description="Session ID for context")


class KBResult(BaseModel):
    """A single result from KB query."""
    chunk_id: str
    doc_id: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str
    chunk_index: int


class KBQueryResponse(BaseModel):
    """Response from KB query."""
    query: str
    results: list[KBResult]
    total_found: int
    query_time_ms: float
    fallback_used: bool = False


class KBIngestRequest(BaseModel):
    """Request to ingest a document."""
    title: str
    content: str
    source: str
    doc_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)


class KBIngestResponse(BaseModel):
    """Response from document ingestion."""
    doc_id: str
    chunks_created: int
    status: str


class KBStats(BaseModel):
    """KB statistics."""
    total_documents: int
    total_chunks: int
    total_vectors: int
    storage_size_bytes: int
    last_updated: str