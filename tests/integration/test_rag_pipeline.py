"""End-to-end hybrid RAG over the real SOP corpus. Fast tests use fallbacks; @models tests use real encoders."""
from __future__ import annotations

import json

import pytest

from pharma_tracker.config import SEED_FILE, SOP_DIR
from pharma_tracker.domain.schemas import IntakeReportIn
from pharma_tracker.rag.corpus import load_sop_documents
from pharma_tracker.rag.indexer import build_index, make_pipeline


@pytest.fixture
def seeded_repo(repo):
    for r in json.loads(SEED_FILE.read_text(encoding="utf-8"))["historical"]:
        repo.create_report(IntakeReportIn.model_validate(r), "OP-01")
    return repo


def test_sop_corpus_loads_sections():
    docs = load_sop_documents(SOP_DIR)
    assert {d.metadata["doc_id"] for d in docs} >= {"SOP-01", "SOP-02", "SOP-03", "SOP-04", "SOP-05", "SOP-06"}
    assert all(d.metadata["citation"].startswith("SOP-") for d in docs)


def test_fallback_pipeline_stages(seeded_repo):
    p = make_pipeline("fallback")
    assert build_index(seeded_repo, p, write_manifest=False) > 20
    r = p.search("LOT-10457 cracked tablets")
    assert r.bm25 and r.dense and r.fused and r.final
    assert len(r.fused) >= max(len(r.bm25), len(r.dense))
    assert len(r.final) <= 5 and all(h.score >= 0.40 for h in r.final)
    assert r.final[0].citation == "REF-2026-0002"


def test_fallback_abstains_on_off_topic(seeded_repo):
    p = make_pipeline("fallback")
    build_index(seeded_repo, p, write_manifest=False)
    r = p.search("chocolate cake recipe")
    assert r.abstained and r.final == [] and "No sufficiently relevant" in r.answer


def test_incremental_add(seeded_repo, ae_fields):
    p = make_pipeline("fallback")
    n0 = build_index(seeded_repo, p, write_manifest=False)
    ref = seeded_repo.create_report(IntakeReportIn.model_validate(ae_fields), "OP-01")
    from pharma_tracker.rag.indexer import add_report
    assert add_report(seeded_repo, p, ref) == 1 and p.size == n0 + 1
    assert ref in [h.citation for h in p.search(f"{ref} throat").final] or ref in p.search("thirty minutes").citations


@pytest.mark.models
def test_real_dense_matches_synonyms(seeded_repo):
    p = make_pipeline("real")
    build_index(seeded_repo, p, write_manifest=False)
    dense = p.dense.search("patient had trouble breathing", k=5)
    top_ids = [d.metadata["citation"] for d, _ in dense]
    assert "REF-2026-0001" in top_ids  # stored as 'shortness of breath ... Dyspnea'


@pytest.mark.models
def test_real_pipeline_exact_lot_and_threshold(seeded_repo):
    p = make_pipeline("real")
    build_index(seeded_repo, p, write_manifest=False)
    r = p.search("any history of difficulty breathing with LOT-88392?")
    assert r.bm25[0].citation in {"REF-2026-0001", "REF-2026-0004", "SOP-05 §1", "SOP-05 §2"}
    assert "REF-2026-0001" in r.citations
    assert all(0.0 <= h.score <= 1.0 for h in r.reranked)
    off = p.search("chocolate cake recipe")
    assert off.abstained


@pytest.mark.models
def test_real_sop_question(seeded_repo):
    p = make_pipeline("real")
    build_index(seeded_repo, p, write_manifest=False)
    r = p.search("how do I close a report?")
    assert r.citations and r.citations[0].startswith("SOP-03")
