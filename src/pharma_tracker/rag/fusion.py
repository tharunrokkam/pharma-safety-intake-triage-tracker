"""Stage 3 - Reciprocal Rank Fusion.

    RRF(d) = sum_i 1 / (k + rank_i(d))        ranks are 1-based, k = 60

Rank-only, so BM25 (unbounded) and cosine ([-1, 1]) scores need no normalisation; the constant k
flattens the curve so a single first-place rank cannot dominate the fused list.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..config import RRF_K


def reciprocal_rank_fusion(ranked_lists: Sequence[Sequence[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in ranked_lists:
        seen: set[str] = set()
        for rank, item in enumerate(ranking, start=1):
            if item in seen:  # duplicate within one list: only best rank counts
                continue
            seen.add(item)
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
