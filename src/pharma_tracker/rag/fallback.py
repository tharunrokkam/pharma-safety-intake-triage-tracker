"""Deterministic offline stand-ins used when encoder weights are not cached, and in fast tests.

They keep the 4-stage pipeline fully functional (but less semantic) with zero downloads.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from langchain_core.embeddings import Embeddings

from .sparse import pharma_tokenize


class HashEmbeddings(Embeddings):
    """Hashed bag-of-words + character trigrams, L2-normalised (cosine == inner product)."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _features(self, text: str) -> list[str]:
        toks = pharma_tokenize(text)
        grams = [t[i:i + 3] for t in toks if len(t) > 3 for i in range(len(t) - 2)]
        return toks + grams

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for f in self._features(text):
            h = int(hashlib.md5(f.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0 if (h >> 1) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class KeywordCrossEncoder:
    """Query-term coverage score in [0, 1]; identifier tokens (LOT-/REF-/SOP-) weigh double."""

    name = "keyword-coverage-fallback"

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        q = set(pharma_tokenize(query))
        if not q:
            return [0.0 for _ in texts]
        weights = {t: (2.0 if "-" in t else 1.0) for t in q}
        total = sum(weights.values())
        out = []
        for text in texts:
            d = set(pharma_tokenize(text))
            out.append(round(sum(w for t, w in weights.items() if t in d) / total, 4))
        return out
