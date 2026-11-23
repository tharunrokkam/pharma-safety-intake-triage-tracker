"""Seed fictional history + run the capstone demonstration, writing evidence to docs/demo/.

Demonstrates: two fictional reports, a status transition through the HITL gate, a multi-stage RAG query,
the circuit breaker and the audit records.

Usage: python scripts/seed_demo.py [--reset]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from pharma_tracker.agent.service import AgentService, TurnResult  # noqa: E402
from pharma_tracker.config import ROOT_DIR, SEED_FILE, db_path  # noqa: E402

DEMO_DIR = ROOT_DIR / "docs" / "demo"


def log_step(lines: list[str], title: str, res: TurnResult | None = None, extra: str = "") -> None:
    lines.append(f"\n### {title}\n")
    if res is not None:
        lines.append(f"- route: `{res.route}` (rule `{res.route_rule}`)  interrupted: `{res.interrupted}`  "
                     f"halted: `{res.halted}`\n")
        lines.append("\n" + "\n".join("> " + ln for ln in res.response.splitlines()) + "\n")
        if res.trace:
            lines.append("\n| step | thought | action | observation |\n|---|---|---|---|\n")
            for t in res.trace:
                lines.append(f"| {t['step']} | {t['thought']} | `{t['action']}` | {t['observation']} |\n")
    if extra:
        lines.append(extra + "\n")
    print(f"- {title}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete the local demo DB (data/db) first")
    args = ap.parse_args()

    path = db_path()
    if path.exists():
        if not args.reset:
            print(f"{path} already exists - rerun with --reset to rebuild the demo database.")
            return 1
        for suffix in ("", "-wal", "-shm"):
            p = path.with_name(path.name + suffix)
            if p.exists():
                p.unlink()

    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    svc = AgentService(path, write_manifest=True)
    lines = [f"# Demonstration walkthrough (generated {datetime.now(timezone.utc).isoformat(timespec='seconds')})\n",
             f"\nRAG mode: `{svc.pipeline.mode}`\n"]
    print(f"RAG mode: {svc.pipeline.mode}")

    # 1. fictional history (gives the RAG corpus something to retrieve)
    for r in seed["historical"]:
        res = svc.submit_report("seed", r, "OP-01")
        if not res.ok:  # explicit check (asserts vanish under python -O)
            raise SystemExit(f"Seeding failed: {res.response}")
    lines.append(f"\nSeeded {len(seed['historical'])} historical fictional reports (REF-2026-0001..0006).\n")

    # 2. the two demo reports (form path through the LangGraph control plane)
    ae, pqc = seed["demo"]
    bad = {k: v for k, v in ae.items() if k != "event_onset_date"} | {"batch_id": "LOT-883"}
    log_step(lines, "Validation demo - AE missing onset date and malformed lot", svc.submit_report("demo-form", bad, "OP-01"))
    r_ae = svc.submit_report("demo-form", {**ae, "batch_id": "lot 88392"}, "OP-01")
    log_step(lines, "Demo report 1 - Suspected Adverse Event (lot auto-repaired)", r_ae)
    r_pqc = svc.submit_report("demo-form", pqc, "OP-02")
    log_step(lines, "Demo report 2 - Product Quality Complaint", r_pqc)
    ref_ae, ref_pqc = r_ae.result["data"]["ref_id"], r_pqc.result["data"]["ref_id"]

    # 3. status transitions incl. the HITL gate
    log_step(lines, f"Chat: move {ref_ae} to in review", svc.chat("demo-chat", f"move {ref_ae} to in review", "OP-01"))
    close = svc.chat("demo-chat", f"close {ref_ae}", "OP-01")
    log_step(lines, f"Chat: close {ref_ae} -> HITL interrupt (state frozen)", close,
             f"\nStatus while frozen: **{svc.repo.get_report(ref_ae)['status']}**; "
             f"pending approvals: {[a['id'] for a in svc.repo.list_approvals('PENDING')]}\n")
    ap_id = svc.repo.list_approvals("PENDING")[0]["id"]
    log_step(lines, "Reviewer REV-02 approves -> LangGraph resume", svc.decide_approval(
        ap_id, "REV-02", "approve", "Mandatory fields verified; hand-off to PV system confirmed."))
    svc.update_status("demo-ui", ref_pqc, "In Review", "OP-02")
    # leave one closure pending for the Triage Approvals page
    svc.update_status("seed", "REF-2026-0002", "In Review", "OP-01")
    pending = svc.update_status("seed-close", "REF-2026-0002", "Closed", "OP-01")
    lines.append(f"\nLeft REF-2026-0002 with a PENDING closure approval (interrupted={pending.interrupted}) for the UI demo.\n")

    # 4. multi-stage RAG
    q = "any history of difficulty breathing with LOT-88392?"
    rag = svc.chat("demo-rag", q, "OP-01")
    log_step(lines, f"Hybrid RAG query: \"{q}\"", rag)
    r = rag.retrieval
    lines.append("\n| stage | candidates | top-3 (citation: score) |\n|---|---|---|\n")
    for name, key in (("1 BM25 (k1=1.3,b=0.75)", "bm25"), ("2 Bi-encoder cosine", "dense"),
                      ("3 RRF k=60", "fused"), ("4 Cross-encoder (sigmoid)", "reranked"), ("Final >= 0.40, max 5", "final")):
        lines.append(f"| {name} | {len(r[key])} | " + ", ".join(f"{h['citation']}: {h['score']:.4f}" for h in r[key][:3]) + " |\n")
    (DEMO_DIR).mkdir(parents=True, exist_ok=True)
    (DEMO_DIR / "rag_query_result.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    log_step(lines, "Off-topic query -> abstain", svc.chat("demo-rag", "chocolate cake recipe ideas", "OP-01"))
    log_step(lines, "Clinical question -> refusal", svc.chat("demo-rag", "Was the dyspnea caused by Fictivex?", "OP-01"))

    # 5. circuit breaker
    for i in range(3):
        res = svc.chat("demo-breaker", "move REF-2026-0999 to in review", "OP-01")
        log_step(lines, f"Circuit breaker attempt {i + 1}", res)

    # 6. audit evidence
    audit = list(reversed(svc.repo.list_audit(limit=10000)))
    with (DEMO_DIR / "audit_trail.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(audit[0]))
        w.writeheader()
        w.writerows(audit)
    chain = svc.repo.verify_audit_chain()
    (DEMO_DIR / "audit_chain_verification.txt").write_text(
        f"chain {'OK' if chain.ok else 'BROKEN'} - {chain.checked} events verified\n", encoding="utf-8")
    lines.append(f"\n### Audit trail ({len(audit)} events, chain {'OK' if chain.ok else 'BROKEN'})\n")
    lines.append("\n| id | ts_utc | actor | action | ref | from -> to | details |\n|---|---|---|---|---|---|---|\n")
    for a in audit:
        lines.append(f"| {a['id']} | {a['ts_utc']} | {a['actor_id']} | {a['action']} | {a['ref_id'] or ''} | "
                     f"{a['from_status'] or ''} -> {a['to_status'] or ''} | `{a['details_json']}` |\n")
    (DEMO_DIR / "walkthrough.md").write_text("".join(lines), encoding="utf-8")
    print(f"Evidence written to {DEMO_DIR} - chain {'OK' if chain.ok else 'BROKEN'} ({chain.checked} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
