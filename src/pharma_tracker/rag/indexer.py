"""Build the hybrid RAG pipeline from local SOPs + stored reports.

PHARMA_RAG_MODE = auto (default: real encoders if cached, else fallback) | real | fallback.
Real encoders are loaded with local_files_only=True - no network access at runtime.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ..config import EMBED_MODEL, INDEX_DIR, RERANK_MODEL, SOP_DIR
from ..persistence.repository import Repository
from .chunking import make_splitter
from .corpus import load_sop_documents, report_to_document
from .fallback import HashEmbeddings, KeywordCrossEncoder
from .pipeline import HybridRAGPipeline

log = logging.getLogger(__name__)


def load_real_encoders():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from langchain_huggingface import HuggingFaceEmbeddings

    from .rerank import CrossEncoderReranker

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu", "local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )
    tokenizer = embeddings._client.tokenizer  # same tokenizer as the encoder -> exact 512-token chunks
    reranker = CrossEncoderReranker(RERANK_MODEL, local_files_only=True)
    return embeddings, reranker, tokenizer


def make_pipeline(mode: str | None = None) -> HybridRAGPipeline:
    mode = (mode or os.environ.get("PHARMA_RAG_MODE", "auto")).lower()
    if mode in ("auto", "real"):
        try:
            emb, rr, tok = load_real_encoders()
            return HybridRAGPipeline(emb, rr, make_splitter(tok), mode=f"real ({EMBED_MODEL} + {RERANK_MODEL})")
        except Exception as exc:  # noqa: BLE001 - weights missing / offline: degrade deterministically
            if mode == "real":
                raise
            log.warning("Real encoders unavailable (%s); using deterministic fallback.", type(exc).__name__)
    return HybridRAGPipeline(HashEmbeddings(), KeywordCrossEncoder(), make_splitter(None),
                             mode="fallback (hash embeddings + keyword reranker)")


def build_index(repo: Repository, pipeline: HybridRAGPipeline, sop_dir: Path = SOP_DIR,
                write_manifest: bool = True) -> int:
    docs = load_sop_documents(sop_dir) + [report_to_document(r) for r in repo.list_reports()]
    n = pipeline.build(docs)
    if write_manifest:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        (INDEX_DIR / "manifest.json").write_text(json.dumps({
            "mode": pipeline.mode, "chunks": n, "documents": len(docs),
            "chunk_ids": sorted(pipeline.chunks)}, indent=2), encoding="utf-8")
    return n


def add_report(repo: Repository, pipeline: HybridRAGPipeline, ref_id: str) -> int:
    rep = repo.get_report(ref_id)
    return pipeline.add_documents([report_to_document(rep)]) if rep else 0
