"""Central configuration. All RAG / guardrail constants live here (see CLAUDE.md section 3)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SOP_DIR = DATA_DIR / "sops"
SEED_FILE = DATA_DIR / "seed" / "synthetic_reports.json"
INDEX_DIR = DATA_DIR / "index"
DEFAULT_DB_PATH = DATA_DIR / "db" / "pharma_tracker.db"


def db_path() -> Path:
    """DB location; override with PHARMA_DB_PATH (tests always use tmp_path)."""
    return Path(os.environ.get("PHARMA_DB_PATH", DEFAULT_DB_PATH))


# ---- Stage 0: chunking (tokens of the embedding model's tokenizer)
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64

# ---- Stage 1: BM25 sparse retrieval
BM25_K1 = 1.3          # term-frequency saturation (spec: 1.2 - 1.5)
BM25_B = 0.75          # document length normalisation
SPARSE_TOP_K = 50

# ---- Stage 2: dense bi-encoder retrieval
EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # 512-token window, 384-dim
DENSE_TOP_K = 50

# ---- Stage 3: reciprocal rank fusion
RRF_K = 60

# ---- Stage 4: cross-encoder reranking
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_THRESHOLD = 0.40
RERANK_MIN_K = 3       # target lower bound (never padded with sub-threshold chunks)
RERANK_MAX_K = 5

# ---- Control plane
BREAKER_MAX_CONSECUTIVE_FAILURES = 2    # the 3rd identical invalid call opens the breaker
TOOL_NAME_FUZZY_CUTOFF = 0.85

# ---- Pseudonymous actors available in the UI (no real names)
OPERATORS = ["OP-01", "OP-02"]
REVIEWERS = ["REV-01", "REV-02"]
