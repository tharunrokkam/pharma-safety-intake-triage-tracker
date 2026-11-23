"""Stage 1 - lexical sparse retrieval with LangChain BM25Retriever (rank-bm25 Okapi BM25)."""
from __future__ import annotations

import re

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from ..config import BM25_B, BM25_K1, SPARSE_TOP_K

# Identifier-like tokens (LOT-88392, REF-2026-0001, SOP-03) are kept whole; then ordinary words.
_TOKEN_RE = re.compile(r"[a-z]+-\d+(?:-\d+)*|[a-z0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were with "
    "any all there their what which who how when where do does did can could would should about into "
    "than then them they we you your our me my i".split()
)


def pharma_tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class SparseRetriever:
    def __init__(self, chunks: list[Document], k: int = SPARSE_TOP_K):
        self.k = k
        self.chunks = list(chunks)
        self.retriever: BM25Retriever | None = None
        if self.chunks:
            self.retriever = BM25Retriever.from_documents(
                self.chunks, bm25_params={"k1": BM25_K1, "b": BM25_B}, preprocess_func=pharma_tokenize, k=k)

    def search(self, query: str, k: int | None = None) -> list[tuple[Document, float]]:
        """Top-k (doc, bm25_score) with score > 0 - zero-overlap chunks are not candidates."""
        if self.retriever is None:
            return []
        tokens = pharma_tokenize(query)
        if not tokens:
            return []
        scores = self.retriever.vectorizer.get_scores(tokens)
        ranked = sorted(range(len(self.chunks)),
                        key=lambda i: (-scores[i], self.chunks[i].metadata["chunk_id"]))
        return [(self.chunks[i], float(scores[i])) for i in ranked[: k or self.k] if scores[i] > 0]
