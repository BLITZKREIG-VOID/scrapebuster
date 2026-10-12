"""KB Store: Local SQLite-based vector store for ScrapeBuster Phase 3.

Provides durable document/chunk storage with vector embeddings
for retrieval-augmented generation (RAG).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sb.store import db

logger = logging.getLogger("sb.kb.store")

# Thread-local connection cache
_conn_local = threading.local()


def get_kb_connection() -> sqlite3.Connection:
    """Get a KB-specific SQLite connection."""
    if not hasattr(_conn_local, "conn") or _conn_local.conn is None:
        _conn_local.conn = sqlite3.connect(
            db.DB_PATH, check_same_thread=False, timeout=30.0
        )
        _conn_local.conn.row_factory = sqlite3.Row
        _conn_local.conn.execute("PRAGMA journal_mode=WAL")
        _conn_local.conn.execute("PRAGMA synchronous=NORMAL")
        _conn_local.conn.execute("PRAGMA busy_timeout=30000")
    return _conn_local.conn


def init_kb_schema() -> None:
    """Initialize KB tables."""
    conn = get_kb_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kb_documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                chunk_ids TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS kb_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                embedding TEXT,  -- JSON array of floats
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES kb_documents(doc_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_id ON kb_chunks(doc_id);
            CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding ON kb_chunks(embedding) WHERE embedding IS NOT NULL;
        """)
        conn.commit()
        logger.info("KB schema initialized")
    except Exception as exc:
        logger.error("Failed to initialize KB schema: %s", exc)
        raise


class KBStore:
    """Local knowledge base store with vector embeddings."""

    def __init__(self):
        init_kb_schema()

    def _content_hash(self, content: str) -> str:
        """Generate content hash for deduplication."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def add_document(
        self,
        title: str,
        content: str,
        source: str,
        doc_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a document to the KB. Returns doc_id."""
        conn = get_kb_connection()
        doc_id = f"doc-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

        with closing(conn.cursor()) as cur:
            cur.execute(
                """INSERT INTO kb_documents 
                   (doc_id, title, content, source, doc_type, metadata, created_at, updated_at, chunk_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    doc_id,
                    title,
                    content,
                    source,
                    doc_type,
                    json.dumps(metadata or {}),
                    now,
                    now,
                    json.dumps([]),
                ),
            )
        conn.commit()
        logger.info("Added KB document: %s (%s)", doc_id, title)
        return doc_id

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by ID."""
        conn = get_kb_connection()
        with closing(conn.cursor()) as cur:
            row = cur.execute(
                "SELECT * FROM kb_documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its chunks."""
        conn = get_kb_connection()
        with closing(conn.cursor()) as cur:
            cur.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
            cur.execute("DELETE FROM kb_documents WHERE doc_id = ?", (doc_id,))
        conn.commit()
        return True

    def list_documents(
        self,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List documents with optional source filter."""
        conn = get_kb_connection()
        with closing(conn.cursor()) as cur:
            if source:
                rows = cur.execute(
                    "SELECT * FROM kb_documents WHERE source = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (source, limit, offset),
                ).fetchall()
            else:
                rows = cur.execute(
                    "SELECT * FROM kb_documents ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [dict(row) for row in rows]

    def add_chunk(
        self,
        doc_id: str,
        content: str,
        chunk_index: int,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a chunk to a document."""
        conn = get_kb_connection()
        chunk_id = f"chunk-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

        with closing(conn.cursor()) as cur:
            cur.execute(
                """INSERT INTO kb_chunks
                   (chunk_id, doc_id, content, chunk_index, embedding, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk_id,
                    doc_id,
                    content,
                    chunk_index,
                    json.dumps(embedding) if embedding else None,
                    json.dumps(metadata or {}),
                    now,
                ),
            )
        conn.commit()

        # Update document's chunk_ids
        doc = self.get_document(doc_id)
        if doc:
            chunk_ids = json.loads(doc["chunk_ids"] or "[]")
            if chunk_id not in chunk_ids:
                chunk_ids.append(chunk_id)
                with closing(conn.cursor()) as cur:
                    cur.execute(
                        "UPDATE kb_documents SET chunk_ids = ?, updated_at = ? WHERE doc_id = ?",
                        (json.dumps(chunk_ids), now, doc_id),
                    )
                conn.commit()

        return chunk_id

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """Retrieve a chunk by ID."""
        conn = get_kb_connection()
        with closing(conn.cursor()) as cur:
            row = cur.execute(
                "SELECT * FROM kb_chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_chunks_for_document(self, doc_id: str) -> list[dict[str, Any]]:
        """Get all chunks for a document."""
        conn = get_kb_connection()
        with closing(conn.cursor()) as cur:
            rows = cur.execute(
                "SELECT * FROM kb_chunks WHERE doc_id = ? ORDER BY chunk_index",
                (doc_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def search_chunks(
        self,
        query_embedding: list[float] | None = None,
        query_text: str | None = None,
        top_k: int = 10,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search chunks by embedding similarity or text match.
        
        If query_embedding provided, computes cosine similarity in Python.
        If query_text provided, uses simple text search.
        """
        conn = get_kb_connection()
        
        # Build base query
        base_query = """
            SELECT c.*, d.title, d.source, d.doc_type
            FROM kb_chunks c
            JOIN kb_documents d ON c.doc_id = d.doc_id
            WHERE (? IS NULL OR d.source = ?)
        """
        
        if query_embedding is not None:
            # Fetch all chunks with embeddings and compute similarity in Python
            query = base_query + " AND c.embedding IS NOT NULL"
            with closing(conn.cursor()) as cur:
                rows = cur.execute(query, (source, source)).fetchall()
            
            chunks = []
            import math
            query_vec = query_embedding
            query_norm = math.sqrt(sum(x * x for x in query_vec)) if query_vec else 1.0
            
            for row in rows:
                emb = json.loads(row["embedding"]) if row["embedding"] else None
                if not emb:
                    continue
                # Cosine similarity
                dot = sum(a * b for a, b in zip(query_vec, emb))
                emb_norm = math.sqrt(sum(x * x for x in emb))
                if query_norm > 0 and emb_norm > 0:
                    score = dot / (query_norm * emb_norm)
                else:
                    score = 0.0
                d = dict(row)
                d["score"] = score
                chunks.append(d)
            
            # Sort by score descending
            chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
            return chunks[:top_k]
        
        elif query_text is not None:
            # Simple text search using LIKE
            with closing(conn.cursor()) as cur:
                rows = cur.execute(
                    base_query + " LIMIT ?",
                    (source, source, top_k),
                ).fetchall()
            return [dict(row) for row in rows]
        
        return []

    def get_stats(self) -> dict[str, Any]:
        """Get KB statistics."""
        conn = get_kb_connection()
        with closing(conn.cursor()) as cur:
            doc_count = cur.execute("SELECT COUNT(*) FROM kb_documents").fetchone()[0]
            chunk_count = cur.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
            vector_count = cur.execute("SELECT COUNT(*) FROM kb_chunks WHERE embedding IS NOT NULL").fetchone()[0]
            size_bytes = cur.execute(
                "SELECT SUM(LENGTH(content)) FROM kb_chunks"
            ).fetchone()[0] or 0
        return {
            "total_documents": doc_count,
            "total_chunks": chunk_count,
            "total_vectors": vector_count,
            "storage_size_bytes": size_bytes,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def reset(self) -> None:
        """Reset KB (for testing)."""
        conn = get_kb_connection()
        with closing(conn.cursor()) as cur:
            cur.execute("DELETE FROM kb_chunks")
            cur.execute("DELETE FROM kb_documents")
        conn.commit()
        logger.info("KB store reset")


# Global KB store instance
_kb_store: KBStore | None = None


def get_kb_store() -> KBStore:
    """Get global KB store instance."""
    global _kb_store
    if _kb_store is None:
        _kb_store = KBStore()
    return _kb_store