"""One-time setup: cache the bi-encoder and cross-encoder weights locally.

After this, run the app with HF_HUB_OFFLINE=1 - the runtime never touches the network.
Usage: python scripts/download_models.py
"""
from __future__ import annotations

from sentence_transformers import CrossEncoder, SentenceTransformer

from pharma_tracker.config import EMBED_MODEL, RERANK_MODEL


def main() -> None:
    print(f"Caching bi-encoder  : {EMBED_MODEL}")
    emb = SentenceTransformer(EMBED_MODEL, device="cpu")
    print(f"  max_seq_length={emb.max_seq_length}, dim={emb.get_sentence_embedding_dimension()}")
    print(f"Caching cross-encoder: {RERANK_MODEL}")
    ce = CrossEncoder(RERANK_MODEL, device="cpu")
    print(f"  probe score={float(ce.predict([('lot recall', 'zebra stripes')])[0]):.4f}")
    print("Done. Set HF_HUB_OFFLINE=1 for fully offline runtime.")


if __name__ == "__main__":
    main()
