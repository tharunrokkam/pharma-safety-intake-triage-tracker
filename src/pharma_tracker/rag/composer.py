"""Deterministic extractive composer: quotes retrieved text verbatim with citations, or abstains.

No text is generated - every sentence in an answer is copied from a chunk that passed the
cross-encoder threshold. This is the zero-hallucination guarantee of the pipeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .sparse import pharma_tokenize

DISCLAIMER = ("Retrieval only - quoted from fictional records/SOPs. This tool does not assess causality, "
              "recommend treatment or determine regulatory reportability.")
ABSTAIN_MESSAGE = ("No sufficiently relevant records found (no candidate reached the 0.40 relevance threshold). "
                   "I will not guess - try different keywords, a batch number (LOT-12345) or a reference id.")

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class Evidence:
    citation: str
    chunk_id: str
    score: float
    quote: str
    source: str


@dataclass
class Answer:
    text: str
    abstained: bool
    evidence: list[Evidence] = field(default_factory=list)


def best_sentences(query: str, text: str, max_sentences: int = 2) -> str:
    """Pick the sentences with the highest query-term overlap, verbatim and in original order."""
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    if not sentences:
        return text.strip()
    q = set(pharma_tokenize(query))
    scored = [(len(q & set(pharma_tokenize(s))), -i, i) for i, s in enumerate(sentences)]
    top = sorted(scored, reverse=True)[:max_sentences]
    keep = sorted(i for *_, i in top)
    return " … ".join(sentences[i] for i in keep)


def compose(query: str, ranked: list[tuple[dict, float]]) -> Answer:
    """``ranked`` = [(chunk_metadata_with_text, rerank_score)] already thresholded, best first."""
    if not ranked:
        return Answer(text=ABSTAIN_MESSAGE, abstained=True)
    evidence = [
        Evidence(citation=meta.get("citation", meta.get("chunk_id", "?")), chunk_id=meta["chunk_id"],
                 score=score, quote=best_sentences(query, meta["text"]), source=meta.get("source", ""))
        for meta, score in ranked
    ]
    lines = [f"**Retrieved evidence - {len(evidence)} source(s), extractive (no generated content):**", ""]
    for i, ev in enumerate(evidence, 1):
        kind = "Report" if ev.source == "report" else "SOP"
        lines.append(f"{i}. **[{ev.citation}]** ({kind}, relevance {ev.score:.2f})  \n   > \"{ev.quote}\"")
    lines += ["", f"_{DISCLAIMER}_"]
    return Answer(text="\n".join(lines), abstained=False, evidence=evidence)
