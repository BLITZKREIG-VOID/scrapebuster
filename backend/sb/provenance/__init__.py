"""Provenance package for dataset ingest and retrieval."""


def reset() -> None:
    """Reset provenance in-memory caches (RAG indices and dataset records)."""
    from sb.provenance import dataset, rag

    rag.reset()
    dataset.reset()
