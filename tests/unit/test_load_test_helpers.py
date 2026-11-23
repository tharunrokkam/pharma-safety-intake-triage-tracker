"""The load-test generator must only produce valid, PII-free fictional reports; percentile maths is correct."""
from __future__ import annotations

import importlib.util
import random
from pathlib import Path

from pharma_tracker.domain.guards import find_pii
from pharma_tracker.domain.schemas import IntakeReportIn

_spec = importlib.util.spec_from_file_location(
    "load_test", Path(__file__).resolve().parents[2] / "scripts" / "load_test.py")
load_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_test)


def test_synthetic_reports_are_valid_and_pii_free():
    rng = random.Random(7)
    for _ in range(300):
        r = load_test.synthetic_report(rng)
        IntakeReportIn.model_validate(r)
        assert not find_pii(r["description"]) and not find_pii(r.get("event_description"))
        assert r["description"].startswith("Fictional")


def test_percentiles():
    xs = [float(i) for i in range(1, 101)]
    assert load_test.pct(xs, 50) == 50.5
    assert round(load_test.pct(xs, 95), 2) == 95.05
    s = load_test.summary([10.0, 20.0, 30.0], 0.5)
    assert s["n"] == 3 and s["p50_ms"] == 20.0 and s["throughput_per_s"] == 6.0
