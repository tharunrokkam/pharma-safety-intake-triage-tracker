"""Headless Streamlit smoke tests (AppTest): every page renders, the form validates and submits."""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
PAGES = ["app.py", "pages/1_New_Report.py", "pages/2_Dashboard.py", "pages/3_Triage_Approvals.py",
         "pages/4_Knowledge_Agent.py", "pages/5_Audit_Trail.py"]


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMA_DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.setenv("PHARMA_RAG_MODE", "fallback")
    from pharma_tracker.ui.common import get_service
    get_service.clear()
    yield
    get_service.clear()


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=60).run()
    assert not at.exception, at.exception


def test_new_report_form_errors_then_success():
    at = AppTest.from_file(str(ROOT / "pages/1_New_Report.py"), default_timeout=60).run()
    submit = lambda: at.button(key="FormSubmitter:intake-Submit report").click().run()  # noqa: E731
    # AE (default type) with malformed lot and no onset date -> contextual inline errors
    at.text_input[0].input("Fictivex 20mg")
    at.text_input[1].input("LOT-123")
    submit()
    errors = [e.value for e in at.error]
    assert any("Submission blocked" in e for e in errors)
    assert any("Batch/Lot number must be" in e for e in errors)
    assert any("Event onset date is required" in e for e in errors)
    assert any("Reporter type is required" in e for e in errors)
    # switch to PQC and submit valid data
    at.radio[0].set_value("Product Quality Complaint").run()
    at.text_input[0].input("Placebrix 5mg")
    at.text_input[1].input("LOT-10457")
    at.selectbox[0].set_value("Pharmacist")
    at.text_area[0].input("Discoloured tablets found in two sealed bottles from the same lot.")
    submit()
    assert any("REF-" in s.value for s in at.success), [e.value for e in at.error]


def test_knowledge_agent_example_query():
    at = AppTest.from_file(str(ROOT / "pages/4_Knowledge_Agent.py"), default_timeout=60).run()
    at.chat_input[0].set_value("what does the SOP say about closing a report?").run()
    assert not at.exception
    assert any("Retrieved evidence" in m.value or "No sufficiently" in m.value for m in at.markdown)
