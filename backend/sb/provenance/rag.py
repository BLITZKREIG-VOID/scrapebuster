"""BM25 retrieval-augmented generation (RAG) index and text processing."""

import math
import re

STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does",
    "for", "from", "has", "have", "how", "in", "is", "it", "its", "of",
    "on", "or", "s", "the", "their", "they", "to", "use", "used", "uses",
    "was", "what", "when", "where", "which", "who", "why", "with",
})

_INDEX_CACHE: dict[str, "BM25Index"] = {}


def reset() -> None:
    """Clear the in-memory index cache."""
    _INDEX_CACHE.clear()


def tokenize(text: str) -> list[str]:
    """Lowercase [a-z0-9]+ tokens minus STOPWORDS."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def chunk_records(records: list[dict]) -> list[tuple[str, str]]:
    """Split each record's text on blank lines, strip, and keep chunks of length >= 20.

    Returns a list of (chunk_id, text) tuples where chunk_id is 'r<record_index>-p<paragraph_index>'.
    """
    chunks: list[tuple[str, str]] = []
    for r_idx, rec in enumerate(records):
        text = rec.get("text", "")
        paragraphs = re.split(r"\n\s*\n", text)
        for p_idx, para in enumerate(paragraphs):
            stripped = para.strip()
            if len(stripped) >= 20:
                chunks.append((f"r{r_idx}-p{p_idx}", stripped))
    return chunks


class BM25Index:
    """Hand-written BM25 index over text chunks."""

    def __init__(
        self,
        chunks: list[tuple[str, str]],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.N = len(chunks)
        self.doc_tokens: list[list[str]] = [tokenize(text) for _, text in chunks]
        self.doc_lens: list[int] = [len(dt) for dt in self.doc_tokens]
        self.avgdl: float = (sum(self.doc_lens) / self.N) if self.N > 0 else 0.0

        self.df: dict[str, int] = {}
        for dt in self.doc_tokens:
            for term in set(dt):
                self.df[term] = self.df.get(term, 0) + 1

        self.doc_tfs: list[dict[str, int]] = []
        for dt in self.doc_tokens:
            tf: dict[str, int] = {}
            for term in dt:
                tf[term] = tf.get(term, 0) + 1
            self.doc_tfs.append(tf)

    def search(self, query: str, k: int = 3) -> list[tuple[str, float, str]]:
        """Return top-k scored chunks as (chunk_id, score, text).

        Sorted by score descending then chunk_id ascending; zero-score chunks excluded.
        Query terms repeated count once per occurrence (plain sum over tokens).
        """
        if self.N == 0 or k <= 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple[str, float, str]] = []
        for i, (chunk_id, text) in enumerate(self.chunks):
            d_len = self.doc_lens[i]
            tf_map = self.doc_tfs[i]
            score = 0.0

            for t in query_tokens:
                f = tf_map.get(t, 0)
                if f > 0:
                    df_t = self.df.get(t, 0)
                    idf = math.log(1.0 + (self.N - df_t + 0.5) / (df_t + 0.5))
                    len_ratio = (d_len / self.avgdl) if self.avgdl > 0.0 else 0.0
                    den = f + self.k1 * (1.0 - self.b + self.b * len_ratio)
                    num = idf * f * (self.k1 + 1.0)
                    score += num / den

            if score > 0.0:
                scored.append((chunk_id, score, text))

        # Sort by score desc, then chunk_id asc
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:k]


def build_index(dataset_id: str, records: list[dict]) -> BM25Index:
    """Build and cache a BM25Index for the dataset records."""
    chunks = chunk_records(records)
    index = BM25Index(chunks)
    _INDEX_CACHE[dataset_id] = index
    return index


def retrieve(dataset_id: str, query: str, k: int = 3) -> list[tuple[str, float, str]]:
    """Retrieve top-k chunks for query against the dataset.

    On cache miss: lazily loads records from sb.provenance.dataset and builds the index.
    """
    index = _INDEX_CACHE.get(dataset_id)
    if index is None:
        from sb.provenance import dataset
        records = dataset.load_records(dataset_id)
        index = build_index(dataset_id, records)
    return index.search(query, k)
