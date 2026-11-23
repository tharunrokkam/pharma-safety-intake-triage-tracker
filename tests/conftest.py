"""Shared fixtures. Every test uses an isolated SQLite file under tmp_path (never data/db/)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from pharma_tracker.agent.service import AgentService  # noqa: E402
from pharma_tracker.domain.schemas import IntakeReportIn  # noqa: E402
from pharma_tracker.persistence.repository import Repository  # noqa: E402
from pharma_tracker.rag.indexer import make_pipeline  # noqa: E402


@pytest.fixture
def ae_fields() -> dict:
    return {
        "report_type": "Suspected Adverse Event",
        "product_name": "Fictivex 20mg",
        "batch_id": "LOT-88392",
        "date_received": "2026-11-20",
        "reporter_type": "Healthcare Professional",
        "description": "Reporter described difficulty breathing shortly after the dose.",
        "event_description": "Difficulty breathing within thirty minutes of use.",
        "event_onset_date": "2026-11-19",
    }


@pytest.fixture
def pqc_fields() -> dict:
    return {
        "report_type": "Product Quality Complaint",
        "product_name": "Placebrix 5mg",
        "batch_id": "LOT-10457",
        "date_received": "2026-11-21",
        "reporter_type": "Pharmacist",
        "description": "Discoloured tablets found in two sealed bottles from the same lot.",
    }


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "test.db")


@pytest.fixture
def make_report(repo: Repository, ae_fields: dict, pqc_fields: dict):
    def _make(kind: str = "ae", actor: str = "OP-01") -> str:
        data = ae_fields if kind == "ae" else pqc_fields
        return repo.create_report(IntakeReportIn.model_validate(data), actor)
    return _make


@pytest.fixture
def service(tmp_path: Path) -> AgentService:
    return AgentService(tmp_path / "svc.db", pipeline=make_pipeline("fallback"))


def _models_cached() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        from pharma_tracker.config import EMBED_MODEL, RERANK_MODEL
        return all(isinstance(try_to_load_from_cache(m, "config.json"), str) for m in (EMBED_MODEL, RERANK_MODEL))
    except Exception:  # noqa: BLE001
        return False


def pytest_collection_modifyitems(config, items):
    if _models_cached():
        return
    skip = pytest.mark.skip(reason="encoder weights not cached - run scripts/download_models.py")
    for item in items:
        if "models" in item.keywords:
            item.add_marker(skip)
