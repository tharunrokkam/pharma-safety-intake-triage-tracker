"""Stage 4 - precision reranking with a cross-encoder (joint attention over query/chunk pairs).

Scores are mapped to [0, 1] (sigmoid of the logit) so the 0.40 relevance threshold is meaningful.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

from ..config import RERANK_MAX_K, RERANK_THRESHOLD


class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        """Relevance probabilities in [0, 1], one per text."""


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class CrossEncoderReranker:
    """Wraps LangChain's HuggingFaceCrossEncoder (sentence-transformers CrossEncoder)."""

    def __init__(self, model_name: str, local_files_only: bool = True):
        from langchain_community.cross_encoders import HuggingFaceCrossEncoder

        self.name = model_name
        self.model = HuggingFaceCrossEncoder(
            model_name=model_name, model_kwargs={"device": "cpu", "local_files_only": local_files_only})
        # Calibrate once: depending on the sentence-transformers version / model config, predict()
        # returns raw logits or already-sigmoided probabilities. An unrelated pair gives a strongly
        # negative logit, so an out-of-[0,1] value means we must apply the sigmoid ourselves.
        probe = float(self.model.score([("batch recall procedure", "zebra stripes in savanna grassland")])[0])
        self._apply_sigmoid = not (0.0 <= probe <= 1.0)

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        raw = self.model.score([(query, t) for t in texts])
        vals = [float(x) for x in raw]
        return [sigmoid(v) for v in vals] if self._apply_sigmoid else vals


def apply_threshold(scored: list[tuple[str, float]], threshold: float = RERANK_THRESHOLD,
                    max_k: int = RERANK_MAX_K) -> list[tuple[str, float]]:
    """Keep candidates with score >= threshold, highest first, capped at max_k (never padded)."""
    kept = [(cid, s) for cid, s in scored if s >= threshold]
    kept.sort(key=lambda kv: (-kv[1], kv[0]))
    return kept[:max_k]
