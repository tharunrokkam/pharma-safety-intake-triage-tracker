"""Hybrid RAG pipeline orchestrator: Stage 1 || Stage 2 -> Stage 3 RRF -> Stage 4 rerank -> compose."""
from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import DENSE_TOP_K, RERANK_MAX_K, RERANK_THRESHOLD, RRF_K, SPARSE_TOP_K
from .chunking import chunk_documents
from .composer import compose
from .dense import DenseRetriever
from .fusion import reciprocal_rank_fusion
from .rerank import Reranker, apply_threshold
from .sparse import SparseRetriever


@dataclass
class Hit:
    rank: int
    chunk_id: str
    citation: str
    score: float
    preview: str


@dataclass
class RetrievalResult:
    query: str
    bm25: list[Hit] = field(default_factory=list)
    dense: list[Hit] = field(default_factory=list)
    fused: list[Hit] = field(default_factory=list)
    reranked: list[Hit] = field(default_factory=list)
    final: list[Hit] = field(default_factory=list)
    answer: str = ""
    abstained: bool = True
    citations: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _preview(text: str, n: int = 140) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1] + "…"


class HybridRAGPipeline:
    def __init__(self, embeddings: Embeddings, reranker: Reranker, splitter: RecursiveCharacterTextSplitter,
                 mode: str = "fallback"):
        self.embeddings = embeddings
        self.reranker = reranker
        self.splitter = splitter
        self.mode = mode
        self._lock = threading.RLock()
        self.chunks: dict[str, Document] = {}
        self.sparse = SparseRetriever([])
        self.dense = DenseRetriever([], embeddings)

    # ------------------------------------------------------------------ indexing
    def build(self, docs: list[Document]) -> int:
        with self._lock:
            chunks = chunk_documents(docs, self.splitter)
            self.chunks = {c.metadata["chunk_id"]: c for c in chunks}
            self.sparse = SparseRetriever(chunks)
            self.dense = DenseRetriever(chunks, self.embeddings)
            return len(chunks)

    def add_documents(self, docs: list[Document]) -> int:
        """Incremental add (new report). BM25 is rebuilt (cheap); FAISS appends vectors."""
        with self._lock:
            new = [c for c in chunk_documents(docs, self.splitter) if c.metadata["chunk_id"] not in self.chunks]
            for c in new:
                self.chunks[c.metadata["chunk_id"]] = c
            self.sparse = SparseRetriever(list(self.chunks.values()))
            self.dense.add(new)
            return len(new)

    @property
    def size(self) -> int:
        return len(self.chunks)

    # ------------------------------------------------------------------ query
    def search(self, query: str) -> RetrievalResult:
        with self._lock:
            res = RetrievalResult(query=query, params={
                "mode": self.mode, "bm25_top_k": SPARSE_TOP_K, "dense_top_k": DENSE_TOP_K, "rrf_k": RRF_K,
                "rerank_threshold": RERANK_THRESHOLD, "rerank_max_k": RERANK_MAX_K,
                "reranker": getattr(self.reranker, "name", type(self.reranker).__name__),
                "corpus_chunks": len(self.chunks)})
            t0 = time.perf_counter()
            sparse_hits = self.sparse.search(query, SPARSE_TOP_K)
            t1 = time.perf_counter()
            dense_hits = self.dense.search(query, DENSE_TOP_K)
            t2 = time.perf_counter()
            fused = reciprocal_rank_fusion(
                [[d.metadata["chunk_id"] for d, _ in sparse_hits], [d.metadata["chunk_id"] for d, _ in dense_hits]],
                k=RRF_K)
            t3 = time.perf_counter()
            fused_ids = [cid for cid, _ in fused]
            scores = self.reranker.score(query, [self.chunks[c].page_content for c in fused_ids])
            rerank_all = sorted(zip(fused_ids, scores), key=lambda kv: (-kv[1], kv[0]))
            final = apply_threshold(rerank_all)
            t4 = time.perf_counter()

            def hits(pairs: list[tuple[str, float]]) -> list[Hit]:
                return [Hit(i, cid, self.chunks[cid].metadata.get("citation", cid), round(float(s), 4),
                            _preview(self.chunks[cid].page_content)) for i, (cid, s) in enumerate(pairs, 1)]

            res.bm25 = hits([(d.metadata["chunk_id"], s) for d, s in sparse_hits])
            res.dense = hits([(d.metadata["chunk_id"], s) for d, s in dense_hits])
            res.fused = hits(fused)
            res.reranked = hits(rerank_all)
            res.final = hits(final)
            answer = compose(query, [({**self.chunks[cid].metadata, "text": self.chunks[cid].page_content}, s)
                                     for cid, s in final])
            res.answer, res.abstained = answer.text, answer.abstained
            res.citations = [e.citation for e in answer.evidence]
            res.timings_ms = {"bm25": round((t1 - t0) * 1000, 1), "dense": round((t2 - t1) * 1000, 1),
                              "rrf": round((t3 - t2) * 1000, 2), "rerank": round((t4 - t3) * 1000, 1)}
            return res
