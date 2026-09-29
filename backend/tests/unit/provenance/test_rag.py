"""Unit tests for BM25 RAG indexing, retrieval, and PRV-01 canary acceptance."""

import math
from pathlib import Path

import pytest
import yaml
from sb.provenance import dataset, rag
from sb.provenance import reset as provenance_reset
from sb.provenance.rag import STOPWORDS, BM25Index, chunk_records, tokenize

CANARIES_PATH = Path(__file__).resolve().parents[4] / "backend" / "sb" / "canary" / "canaries.yaml"
CANARIES = yaml.safe_load(CANARIES_PATH.read_text(encoding="utf-8"))["canaries"]


def test_tokenize_drops_stopwords():
    """Tokenize converts to lowercase [a-z0-9]+ tokens and drops all STOPWORDS."""
    sample_text = (
        "The quick brown fox was jumping over a lazy dog, "
        "and it did not use its legs to walk!"
    )
    tokens = tokenize(sample_text)
    # Check stopwords are excluded
    for stopword in ("the", "was", "a", "and", "it", "did", "use", "its", "to"):
        assert stopword in STOPWORDS
        assert stopword not in tokens

    # Check non-stopwords are present
    assert "quick" in tokens
    assert "brown" in tokens
    assert "fox" in tokens
    assert "jumping" in tokens
    assert "lazy" in tokens
    assert "dog" in tokens
    assert "not" in tokens
    assert "legs" in tokens
    assert "walk" in tokens


def test_chunk_records():
    """Chunking splits on blank lines, drops < 20 chars, and assigns r<i>-p<j> ids."""
    records = [
        {
            "url": "http://example.com/1",
            "title": "Title 1",
            "text": (
                "First paragraph has sufficient length to be kept.\n\n"
                "Short\n\n"
                "Third paragraph also has sufficient length to be kept."
            ),
        },
        {
            "url": "http://example.com/2",
            "title": "Title 2",
            "text": "Second record paragraph is comfortably long enough.",
        },
    ]

    chunks = chunk_records(records)
    # 3 chunks kept, 1 dropped ("Short" < 20 chars)
    assert len(chunks) == 3
    assert chunks[0] == ("r0-p0", "First paragraph has sufficient length to be kept.")
    assert chunks[1] == ("r0-p2", "Third paragraph also has sufficient length to be kept.")
    assert chunks[2] == ("r1-p0", "Second record paragraph is comfortably long enough.")


def test_bm25_hand_check():
    """BM25 hand-check on a 3-doc toy corpus with exact score assert to 1e-9."""
    toy_chunks = [
        ("r0-p0", "apple banana orange grape"),
        ("r1-p0", "apple apple banana melon"),
        ("r2-p0", "grape melon kiwi lemon"),
    ]
    index = BM25Index(toy_chunks, k1=1.5, b=0.75)

    # Document length calculations:
    # doc0: ['apple', 'banana', 'orange', 'grape'] -> len 4
    # doc1: ['apple', 'apple', 'banana', 'melon']  -> len 4
    # doc2: ['grape', 'melon', 'kiwi', 'lemon']    -> len 4
    # N = 3, avgdl = 4.0
    # For all docs: |d| == avgdl, so (1 - b + b * (|d|/avgdl)) == 1.0
    # Denominator for tf f is f + k1 * 1.0 = f + 1.5
    # Numerator for tf f is idf * f * (k1 + 1.0) = idf * f * 2.5
    # Query: "apple banana"
    # df(apple) = 2 (in doc0, doc1)
    # df(banana) = 2 (in doc0, doc1)
    # idf(apple) = idf(banana) = ln(1 + (3 - 2 + 0.5) / (2 + 0.5)) = ln(1 + 1.5 / 2.5) = ln(1.6)
    #
    # doc0:
    # tf(apple) = 1 -> term = ln(1.6) * 1 * 2.5 / (1 + 1.5) = ln(1.6)
    # tf(banana) = 1 -> term = ln(1.6) * 1 * 2.5 / (1 + 1.5) = ln(1.6)
    # doc0 total = 2.0 * ln(1.6)
    #
    # doc1:
    # tf(apple) = 2 -> term = ln(1.6) * 2 * 2.5 / (2 + 1.5) = ln(1.6) * 5.0 / 3.5 = (10/7) * ln(1.6)
    # tf(banana) = 1 -> term = ln(1.6)
    # doc1 total = (10/7 + 1) * ln(1.6) = (17/7) * ln(1.6)
    #
    # doc2:
    # tf(apple) = 0, tf(banana) = 0 -> score = 0.0 (excluded from search results)

    expected_doc1_score = (17.0 / 7.0) * math.log(1.6)
    expected_doc0_score = 2.0 * math.log(1.6)

    results = index.search("apple banana", k=3)
    assert len(results) == 2  # doc2 has 0 score, excluded

    # Ranked doc1 first, doc0 second
    assert results[0][0] == "r1-p0"
    assert abs(results[0][1] - expected_doc1_score) < 1e-9

    assert results[1][0] == "r0-p0"
    assert abs(results[1][1] - expected_doc0_score) < 1e-9


def test_retrieve_sorted_and_k(sample_path: Path):
    """retrieve returns <= k results sorted descending by score."""
    ds = dataset.ingest(sample_path, role="target")
    results = rag.retrieve(ds.dataset_id, "ExampleCorp Nimbus Platform", k=2)

    assert len(results) <= 2
    assert len(results) == 2
    assert results[0][1] >= results[1][1]


def test_cache_miss_rebuilds_via_load_records(sample_path: Path):
    """Cache miss after sb.provenance.reset() rebuilds via dataset.load_records."""
    ds = dataset.ingest(sample_path, role="target")

    # Clear caches
    provenance_reset()
    assert ds.dataset_id not in rag._INDEX_CACHE
    assert ds.dataset_id not in dataset._RECORDS_CACHE

    results = rag.retrieve(ds.dataset_id, "Hexaquorum protocol", k=3)
    assert len(results) > 0
    assert "Hexaquorum" in results[0][2]
    assert ds.dataset_id in rag._INDEX_CACHE


@pytest.mark.parametrize("canary", CANARIES, ids=[c["canary_id"] for c in CANARIES])
def test_prv01_canary_acceptance(sample_path: Path, canary: dict):
    """PRV-01 acceptance: every canary's probe prompt retrieves its own chunk top-1."""
    ds = dataset.ingest(sample_path, role="target")
    results = rag.retrieve(ds.dataset_id, canary["probe_prompts"][0], k=3)

    assert len(results) > 0
    assert results[0][2] == canary["content"]
