"""Unit tests for KB/RAG Engine (Phase 3)."""

import pytest
from types import SimpleNamespace

from sb.kb.engine import get_kb_engine
from sb.kb.models import (
    KBQuery,
    KBIngestRequest,
    KBIngestResponse,
    KBStats,
    KBDocument,
    KBChunk,
    KBResult,
)


@pytest.fixture(autouse=True)
def reset_kb():
    """Reset KB store before each test."""
    from sb.kb.store import get_kb_store
    store = get_kb_store()
    store.reset()
    yield
    store.reset()


def test_kb_engine_initialization():
    """Test KB engine initializes correctly."""
    engine = get_kb_engine()
    assert engine is not None
    assert hasattr(engine, 'ingest')
    assert hasattr(engine, 'query')
    assert hasattr(engine, 'get_stats')


def test_kb_ingest_document():
    """Test document ingestion."""
    engine = get_kb_engine()
    
    request = KBIngestRequest(
        title="Test Document",
        content="This is a test document about refund policies.",
        source="brand",
        doc_type="text"
    )
    
    result = engine.ingest(request)
    assert isinstance(result, KBIngestResponse)
    assert result.doc_id.startswith("doc-")
    assert result.chunks_created >= 1
    assert result.status == "success"
    
    # Verify document stored
    doc = engine.get_document(result.doc_id)
    assert doc is not None
    assert doc["title"] == "Test Document"
    assert doc["source"] == "brand"
    assert doc["doc_type"] == "text"


def test_kb_ingest_catalog():
    """Test catalog ingestion."""
    engine = get_kb_engine()
    
    catalog = {
        "id": "cat-001",
        "title": "Product Catalog",
        "items": [
            {"id": "prod-1", "name": "Premium Plan", "price": 99.99},
            {"id": "prod-2", "name": "Basic Plan", "price": 19.99},
        ]
    }
    
    result = engine.ingest_catalog(catalog)
    assert isinstance(result, KBIngestResponse)
    assert result.doc_id.startswith("doc-")
    assert result.status == "success"
    
    doc = engine.get_document(result.doc_id)
    assert doc["source"] == "catalog"
    assert doc["doc_type"] == "json"


def test_kb_ingest_brand_schema():
    """Test brand schema ingestion."""
    engine = get_kb_engine()
    
    brand = {
        "id": "brand-001",
        "title": "Brand Guidelines",
        "refund_policy": "Full refund within 30 days for premium.",
        "brand_voice": "professional",
    }
    
    result = engine.ingest_brand_schema(brand)
    assert isinstance(result, KBIngestResponse)
    assert result.status == "success"
    
    doc = engine.get_document(result.doc_id)
    assert doc["source"] == "brand"
    assert doc["doc_type"] == "json"


def test_kb_query():
    """Test KB query with text search."""
    engine = get_kb_engine()
    
    # Ingest a document
    request = KBIngestRequest(
        title="Refund Policy",
        content="Premium subscribers get full refunds within 30 days. Basic users get store credit.",
        source="brand",
        doc_type="text"
    )
    engine.ingest(request)
    
    # Query
    query = KBQuery(query="refund policy premium", top_k=3)
    response = engine.query(query)
    
    assert hasattr(response, 'results')
    assert len(response.results) >= 1
    assert hasattr(response, 'query_time_ms')
    assert response.query_time_ms >= 0


def test_kb_query_with_embedding():
    """Test KB query with vector similarity."""
    engine = get_kb_engine()
    
    request = KBIngestRequest(
        title="Test Doc",
        content="Premium subscribers receive priority support and full refunds within 30 days.",
        source="brand",
        doc_type="text"
    )
    engine.ingest(request)
    
    query = KBQuery(query="premium refund", top_k=3)
    response = engine.query(query)
    
    assert len(response.results) >= 1
    # Check that results have scores
    for r in response.results:
        assert hasattr(r, 'score')
        assert isinstance(r.score, float)


def test_kb_query_filters():
    """Test KB query with source filter."""
    engine = get_kb_engine()
    
    # Ingest catalog and brand docs
    engine.ingest(KBIngestRequest(
        title="Catalog Item",
        content="Product A details",
        source="catalog",
        doc_type="text"
    ))
    engine.ingest(KBIngestRequest(
        title="Brand Policy",
        content="Brand voice guidelines",
        source="brand",
        doc_type="text"
    ))
    
    # Query with source filter
    query = KBQuery(query="details", top_k=5, filters={"source": "catalog"})
    response = engine.query(query)
    
    # Should find catalog doc
    assert len(response.results) >= 1
    for r in response.results:
        assert r.source == "catalog"


def test_kb_query_no_results():
    """Test KB query with no matching results."""
    engine = get_kb_engine()
    
    query = KBQuery(query="nonexistent query xyz123", top_k=5)
    response = engine.query(query)
    
    assert len(response.results) == 0
    assert response.total_found == 0


def test_kb_stats():
    """Test KB statistics."""
    engine = get_kb_engine()
    
    # Ingest some docs
    engine.ingest(KBIngestRequest(
        title="Doc 1", content="Content 1", source="test", doc_type="text"
    ))
    engine.ingest(KBIngestRequest(
        title="Doc 2", content="Content 2", source="test", doc_type="text"
    ))
    
    stats = engine.get_stats()
    assert isinstance(stats, KBStats)
    assert stats.total_documents >= 2
    assert stats.total_chunks >= 2
    assert stats.total_vectors >= 2
    assert stats.storage_size_bytes >= 0
    assert stats.last_updated is not None


def test_kb_list_documents():
    """Test listing documents."""
    engine = get_kb_engine()
    
    # Ingest a few docs
    engine.ingest(KBIngestRequest(
        title="Doc 1", content="Content 1", source="test", doc_type="text"
    ))
    engine.ingest(KBIngestRequest(
        title="Doc 2", content="Content 2", source="catalog", doc_type="text"
    ))
    
    docs = engine.list_documents(limit=10)
    assert len(docs) >= 2
    
    # Filter by source
    catalog_docs = engine.list_documents(source="catalog", limit=10)
    assert len(catalog_docs) >= 1
    for d in catalog_docs:
        assert d["source"] == "catalog"


def test_kb_delete_document():
    """Test deleting a document."""
    engine = get_kb_engine()
    
    request = KBIngestRequest(
        title="To Delete",
        content="This will be deleted",
        source="test",
        doc_type="text"
    )
    result = engine.ingest(request)
    
    # Verify exists
    doc = engine.get_document(result.doc_id)
    assert doc is not None
    
    # Delete
    ok = engine.delete_document(result.doc_id)
    assert ok is True
    
    # Verify deleted
    doc = engine.get_document(result.doc_id)
    assert doc is None


def test_kb_health_check():
    """Test KB health check."""
    engine = get_kb_engine()
    
    health = engine.health_check()
    assert "local_store" in health
    assert "external_backend" in health
    assert "overall" in health
    assert health["local_store"] == "healthy"
    assert health["overall"] in ("healthy", "degraded")


def test_kb_ingest_json():
    """Test ingesting JSON document."""
    engine = get_kb_engine()
    
    request = KBIngestRequest(
        title="JSON Test",
        content='{"products": [{"id": 1, "name": "Test"}]}',
        source="catalog",
        doc_type="json"
    )
    result = engine.ingest(request)
    
    assert result.chunks_created >= 1
    
    # Query the JSON content
    query = KBQuery(query="product", top_k=3)
    response = engine.query(query)
    assert len(response.results) >= 1


def test_kb_offline_fallback():
    """Test KB works without external backend (offline mode)."""
    engine = get_kb_engine()
    
    # Verify external backend is not configured (offline mode)
    health = engine.health_check()
    assert health["external_backend"] in ("not_configured", "unhealthy")
    assert health["local_store"] == "healthy"
    assert health["overall"] in ("healthy", "degraded")


def test_kb_get_watermark_matrix_info():
    """Test getting watermark matrix info."""
    from sb.offense.injector import get_watermark_matrix_info
    
    info = get_watermark_matrix_info()
    assert "vectors" in info
    assert "placement_strategies" in info
    assert info["total_vectors"] == 6  # TEXT, API, JSONLD, BEACON, HONEYKEY, SYNTHETIC_JSON
    assert info["total_strategies"] == 9


def test_kb_deterministic_embedding():
    """Test that embeddings are deterministic for same text."""
    engine = get_kb_engine()
    
    text = "Test document for embedding"
    emb1 = engine._get_embedding(text)
    emb2 = engine._get_embedding(text)
    
    assert emb1 == emb2
    assert len(emb1) == 384  # Standard embedding dimension


def test_kb_chunking():
    """Test text chunking logic."""
    engine = get_kb_engine()
    
    # Short text - single chunk
    short = "Short text"
    chunks = engine._chunk_text(short, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == short
    
    # Long text - multiple chunks
    long = "A " * 600  # ~1200 chars
    chunks = engine._chunk_text(long, chunk_size=500, overlap=50)
    assert len(chunks) >= 2
    # Test degenerate cases where overlap >= chunk_size
    degen_chunks = engine._chunk_text("abcdefghijklmnop", chunk_size=4, overlap=10)
    assert len(degen_chunks) > 0
    # Empty string
    empty_chunks = engine._chunk_text("", chunk_size=500, overlap=50)
    assert empty_chunks == [""]


def test_kb_models():
    """Test KB model validation."""
    from sb.kb.models import KBQuery, KBIngestRequest, KBStats, KBResult
    
    # KBQuery
    query = KBQuery(query="test", top_k=5)
    assert query.query == "test"
    assert query.top_k == 5
    
    # KBIngestRequest
    req = KBIngestRequest(
        title="Test", content="Content", source="test", doc_type="text"
    )
    assert req.title == "Test"
    
    # KBStats
    stats = KBStats(
        total_documents=10,
        total_chunks=20,
        total_vectors=15,
        storage_size_bytes=1024,
        last_updated="2026-01-01T00:00:00Z"
    )
    assert stats.total_documents == 10
    
    # KBResult
    result = KBResult(
        chunk_id="chunk-1",
        doc_id="doc-1",
        title="Test",
        content="Content",
        score=0.95,
        metadata={},
        source="test",
        chunk_index=0
    )
    assert result.score == 0.95