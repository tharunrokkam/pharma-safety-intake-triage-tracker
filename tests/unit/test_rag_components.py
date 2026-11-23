"""RAG unit tests: tokenizer, BM25 params, RRF math, threshold, composer abstain, chunking."""
from __future__ import annotations

import pytest
from langchain_core.documents import Document

from pharma_tracker.config import BM25_B, BM25_K1, CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS, RRF_K
from pharma_tracker.rag.chunking import approx_token_len, chunk_documents, make_splitter
from pharma_tracker.rag.composer import ABSTAIN_MESSAGE, compose
from pharma_tracker.rag.fusion import reciprocal_rank_fusion
from pharma_tracker.rag.rerank import apply_threshold, sigmoid
from pharma_tracker.rag.sparse import SparseRetriever, pharma_tokenize


def _doc(cid: str, text: str) -> Document:
    return Document(page_content=text, metadata={"chunk_id": cid, "citation": cid, "doc_id": cid})


def test_config_matches_spec():
    assert 1.2 <= BM25_K1 <= 1.5 and BM25_B == 0.75 and RRF_K == 60
    assert (CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS) == (512, 64)


def test_tokenizer_keeps_identifiers_whole():
    toks = pharma_tokenize("Lot LOT-88392 and REF-2026-0001 per SOP-03: Anaphylaxis!")
    assert "lot-88392" in toks and "ref-2026-0001" in toks and "sop-03" in toks and "anaphylaxis" in toks
    assert "and" not in toks


def test_bm25_params_applied_and_exact_lot_match():
    docs = [_doc("a", "Cracked tablets in LOT-10457 reported by pharmacist."),
            _doc("b", "Dyspnea reported after dose from LOT-88392."),
            _doc("c", "General SOP text about intake and triage workflow.")]
    sr = SparseRetriever(docs)
    assert sr.retriever.vectorizer.k1 == BM25_K1 and sr.retriever.vectorizer.b == BM25_B
    hits = sr.search("LOT-88392")
    assert hits[0][0].metadata["chunk_id"] == "b"
    assert all(score > 0 for _, score in hits)
    assert sr.search("zzzz-nothing") == []


def test_rrf_hand_computed():
    fused = dict(reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]], k=60))
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["d"] == pytest.approx(1 / 62)
    assert fused["c"] == pytest.approx(1 / 63)
    order = [cid for cid, _ in reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]], k=60)]
    assert order == ["b", "a", "d", "c"]


def test_rrf_k_dampens_single_first_place():
    # an item ranked 1st in one list only vs. an item ranked 2nd in both lists
    fused = dict(reciprocal_rank_fusion([["x", "y"], ["z", "y"]], k=60))
    assert fused["y"] > fused["x"]


def test_rrf_ignores_duplicates_within_list():
    fused = dict(reciprocal_rank_fusion([["a", "a", "b"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61) and fused["b"] == pytest.approx(1 / 63)


def test_threshold_and_cap():
    scored = [(f"c{i}", s) for i, s in enumerate([0.99, 0.95, 0.9, 0.8, 0.7, 0.6, 0.39, 0.1])]
    kept = apply_threshold(scored, threshold=0.40, max_k=5)
    assert [c for c, _ in kept] == ["c0", "c1", "c2", "c3", "c4"]
    assert apply_threshold([("a", 0.39)], 0.40) == []
    assert apply_threshold([("a", 0.40)], 0.40) == [("a", 0.40)]


def test_sigmoid_maps_logits():
    assert sigmoid(0) == 0.5 and sigmoid(-11) < 0.001 and sigmoid(8) > 0.99


def test_composer_abstains_without_evidence():
    ans = compose("anything", [])
    assert ans.abstained and ans.text == ABSTAIN_MESSAGE


def test_composer_is_extractive():
    text = "Reference REF-2026-0001.\nDescription: Dyspnea reported after dose. Unrelated sentence here."
    ans = compose("dyspnea", [({"chunk_id": "r#0", "citation": "REF-2026-0001", "text": text, "source": "report"}, 0.9)])
    assert not ans.abstained
    for ev in ans.evidence:
        for part in ev.quote.split(" … "):
            assert part in text  # every quoted sentence exists verbatim in the source chunk
    assert "[REF-2026-0001]" in ans.text and "does not assess causality" in ans.text


def test_chunking_size_and_overlap():
    long = " ".join(f"word{i}." for i in range(1500))
    chunks = chunk_documents([Document(page_content=long, metadata={"doc_id": "D"})], make_splitter(None))
    assert len(chunks) >= 3
    assert all(approx_token_len(c.page_content) <= CHUNK_SIZE_TOKENS for c in chunks)
    assert len({c.metadata["chunk_id"] for c in chunks}) == len(chunks)
    # consecutive chunks overlap
    assert chunks[0].page_content.split()[-1] in chunks[1].page_content
