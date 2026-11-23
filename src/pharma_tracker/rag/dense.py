"""Stage 2 - dense bi-encoder retrieval: normalised embeddings + FAISS inner product == cosine similarity."""
from __future__ import annotations

from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ..config import DENSE_TOP_K


class DenseRetriever:
    def __init__(self, chunks: list[Document], embeddings: Embeddings, k: int = DENSE_TOP_K):
        self.k = k
        self.embeddings = embeddings
        self.store: FAISS | None = None
        if chunks:
            self.store = FAISS.from_documents(
                chunks, embeddings, distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
                ids=[c.metadata["chunk_id"] for c in chunks])

    def add(self, chunks: list[Document]) -> None:
        if not chunks:
            return
        ids = [c.metadata["chunk_id"] for c in chunks]
        if self.store is None:
            self.store = FAISS.from_documents(chunks, self.embeddings,
                                              distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT, ids=ids)
        else:
            self.store.add_documents(chunks, ids=ids)

    def search(self, query: str, k: int | None = None) -> list[tuple[Document, float]]:
        """Top-k (doc, cosine_similarity), highest first."""
        if self.store is None:
            return []
        hits = self.store.similarity_search_with_score(query, k=k or self.k)
        return sorted(((d, float(s)) for d, s in hits), key=lambda x: (-x[1], x[0].metadata["chunk_id"]))
