"""Provenance package for dataset ingest and retrieval."""


def reset() -> None:
    """Reset provenance in-memory state (RAG indices, dataset records, vault last error)."""
    from sb.provenance import dataset, rag, vault_s3

    rag.reset()
    dataset.reset()
    vault_s3.reset()
