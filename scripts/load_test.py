"""Local load / performance test (isolated temp DB, real encoders when cached).

Scenarios
  A  intake submissions through the full LangGraph control plane - sequential
  B  concurrent intake (1/4/8/16 threads) - throughput, errors, ref-id uniqueness, audit chain
  C  hybrid RAG queries through the agent - latency + per-stage timings
  D  concurrent RAG queries (1/4/8 threads)
  E  corpus scaling - index build time and query latency vs number of stored reports

Usage: python scripts/load_test.py [--quick]
Output: docs/presentation/load_test_results.json and load_test_charts.png
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import statistics
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from pharma_tracker.agent.service import AgentService  # noqa: E402
from pharma_tracker.config import ROOT_DIR, SEED_FILE  # noqa: E402
from pharma_tracker.domain.schemas import IntakeReportIn  # noqa: E402
from pharma_tracker.rag.indexer import build_index, make_pipeline  # noqa: E402

OUT = ROOT_DIR / "docs" / "presentation"
PRODUCTS = ["Fictivex 20mg", "Placebrix 5mg", "Nullamycin 250mg", "Sampleol 10mg", "Imaginox 50mg"]
PQC_TEXT = ["cracked tablets found in a sealed blister", "discoloured capsules with dark specks",
            "leaking bottle cap and residue on the neck", "missing patient leaflet in the carton",
            "smudged expiry date printing on outer carton", "broken tamper-evident seal on arrival"]
AE_TEXT = [("reporter described a headache after use", "Headache within two hours of use."),
           ("reporter described an itchy rash on the arms", "Pruritic rash on forearms on day two."),
           ("reporter described feeling dizzy when standing", "Dizziness on standing during week one."),
           ("reporter described stomach upset after the dose", "Nausea shortly after intake.")]
QUERIES = ["any history of difficulty breathing with LOT-88392?", "cracked or broken tablets complaints",
           "what does the SOP say about closing a report?", "rash or hives reports", "LOT-10457",
           "leaking bottle complaints", "how should lot numbers be formatted?", "dizziness when standing up"]


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summary(lat_ms: list[float], wall_s: float) -> dict:
    return {"n": len(lat_ms), "p50_ms": round(pct(lat_ms, 50), 1), "p95_ms": round(pct(lat_ms, 95), 1),
            "p99_ms": round(pct(lat_ms, 99), 1), "mean_ms": round(statistics.mean(lat_ms), 1) if lat_ms else 0,
            "throughput_per_s": round(len(lat_ms) / wall_s, 2) if wall_s else 0}


def synthetic_report(rng: random.Random) -> dict:
    lot = f"LOT-{rng.randint(10000, 99999)}"
    base = {"product_name": rng.choice(PRODUCTS), "batch_id": lot, "date_received": "2026-11-10",
            "reporter_type": rng.choice(["Consumer", "Pharmacist", "Healthcare Professional"])}
    if rng.random() < 0.5:
        return {**base, "report_type": "Product Quality Complaint",
                "description": f"Fictional complaint: {rng.choice(PQC_TEXT)} for batch {lot}."}
    d, e = rng.choice(AE_TEXT)
    return {**base, "report_type": "Suspected Adverse Event", "description": f"Fictional report: {d}.",
            "event_description": e, "event_onset_date": "2026-11-08"}


def timed(fn, *a):
    t = time.perf_counter()
    r = fn(*a)
    return r, (time.perf_counter() - t) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    scale = 0.3 if args.quick else 1.0
    rng = random.Random(42)
    tmp = Path(tempfile.mkdtemp(prefix="pharma_load_"))
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    results: dict = {"environment": {"cpu_count": os.cpu_count(), "rag_mode": None}}

    svc = AgentService(tmp / "load.db")
    results["environment"]["rag_mode"] = svc.pipeline.mode
    for r in seed["historical"]:
        svc.submit_report("seed", r, "OP-01")
    print("mode:", svc.pipeline.mode)

    # A ---------------------------------------------------------------- sequential intake
    lat = []
    t0 = time.perf_counter()
    for i in range(int(200 * scale)):
        res, ms = timed(svc.submit_report, f"a{i}", synthetic_report(rng), "OP-01")
        assert res.ok, res.response
        lat.append(ms)
    results["A_sequential_intake"] = summary(lat, time.perf_counter() - t0)
    print("A", results["A_sequential_intake"])

    # B ---------------------------------------------------------------- concurrent intake
    results["B_concurrent_intake"] = []
    for threads in (1, 4, 8, 16):
        per = max(5, int(25 * scale))
        lat_b: list[float] = []
        errors = 0
        refs: list[str] = []
        lock = threading.Lock()

        def worker(tid: int) -> None:
            nonlocal errors
            local_rng = random.Random(tid)
            for j in range(per):
                res, ms = timed(svc.submit_report, f"b{threads}-{tid}-{j}", synthetic_report(local_rng), "OP-02")
                with lock:
                    lat_b.append(ms)
                    if res.ok:
                        refs.append(res.result["data"]["ref_id"])
                    else:
                        errors += 1

        t0 = time.perf_counter()
        with ThreadPoolExecutor(threads) as ex:
            list(ex.map(worker, range(threads)))
        row = {"threads": threads, **summary(lat_b, time.perf_counter() - t0), "errors": errors,
               "unique_refs": len(set(refs)) == len(refs)}
        results["B_concurrent_intake"].append(row)
        print("B", row)
    chain = svc.repo.verify_audit_chain()
    results["B_audit_chain_after_load"] = {"ok": chain.ok, "events": chain.checked}

    # C ---------------------------------------------------------------- sequential RAG via agent
    lat_c, stages = [], {"bm25": [], "dense": [], "rrf": [], "rerank": []}
    t0 = time.perf_counter()
    for i in range(int(40 * scale)):
        res, ms = timed(svc.chat, f"c{i}", QUERIES[i % len(QUERIES)], "OP-01")
        lat_c.append(ms)
        for k in stages:
            stages[k].append(res.retrieval["timings_ms"][k])
    results["C_rag_sequential"] = {**summary(lat_c, time.perf_counter() - t0),
                                   "corpus_chunks": svc.pipeline.size,
                                   "stage_mean_ms": {k: round(statistics.mean(v), 2) for k, v in stages.items()}}
    print("C", results["C_rag_sequential"])

    # D ---------------------------------------------------------------- concurrent RAG
    results["D_rag_concurrent"] = []
    for threads in (1, 4, 8):
        per = max(2, int(8 * scale))
        lat_d: list[float] = []
        lock = threading.Lock()

        def rworker(tid: int) -> None:
            for j in range(per):
                _, ms = timed(svc.chat, f"d{threads}-{tid}-{j}", QUERIES[(tid + j) % len(QUERIES)], "OP-01")
                with lock:
                    lat_d.append(ms)

        t0 = time.perf_counter()
        with ThreadPoolExecutor(threads) as ex:
            list(ex.map(rworker, range(threads)))
        row = {"threads": threads, **summary(lat_d, time.perf_counter() - t0)}
        results["D_rag_concurrent"].append(row)
        print("D", row)

    # E ---------------------------------------------------------------- corpus scaling
    results["E_corpus_scaling"] = []
    from pharma_tracker.persistence.repository import Repository
    for n_reports in [int(x * scale) or 10 for x in (100, 500, 1000)]:
        repo = Repository(tmp / f"scale_{n_reports}.db")
        for _ in range(n_reports):
            repo.create_report(IntakeReportIn.model_validate(synthetic_report(rng)), "OP-01")
        pipe = make_pipeline()
        t0 = time.perf_counter()
        chunks = build_index(repo, pipe, write_manifest=False)
        build_s = time.perf_counter() - t0
        lat_e = [timed(pipe.search, QUERIES[i % len(QUERIES)])[1] for i in range(int(16 * scale) or 4)]
        row = {"reports": n_reports, "chunks": chunks, "index_build_s": round(build_s, 2),
               **summary(lat_e, sum(lat_e) / 1000)}
        results["E_corpus_scaling"].append(row)
        print("E", row)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "load_test_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    chart(results)
    print("written", OUT / "load_test_results.json")
    shutil.rmtree(tmp, ignore_errors=True)  # temp DBs hold synthetic data only, but don't leave them behind


def chart(r: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), dpi=150)
    ink, blue, teal, amber = "#0F172A", "#1D4ED8", "#0F766E", "#B45309"
    b = r["B_concurrent_intake"]
    ax = axes[0]
    ax.bar([str(x["threads"]) for x in b], [x["throughput_per_s"] for x in b], color=blue)
    ax.set_title("Intake throughput vs threads", color=ink, fontsize=12, weight="bold")
    ax.set_xlabel("concurrent threads")
    ax.set_ylabel("reports / second")
    for i, x in enumerate(b):
        ax.text(i, x["throughput_per_s"], f"{x['throughput_per_s']}\np95 {x['p95_ms']:.0f} ms", ha="center",
                va="bottom", fontsize=8.5)
    ax.set_ylim(0, max(x["throughput_per_s"] for x in b) * 1.35)
    ax = axes[1]
    st = r["C_rag_sequential"]["stage_mean_ms"]
    ax.barh(list(st)[::-1], list(st.values())[::-1], color=[amber, teal, teal, teal])
    ax.set_title(f"RAG stage latency (mean, {r['C_rag_sequential']['corpus_chunks']} chunks)", color=ink,
                 fontsize=12, weight="bold")
    ax.set_xlabel("milliseconds")
    for i, v in enumerate(list(st.values())[::-1]):
        ax.text(v, i, f" {v:.1f}", va="center", fontsize=9)
    ax = axes[2]
    e = r["E_corpus_scaling"]
    ax.plot([x["reports"] for x in e], [x["p50_ms"] for x in e], marker="o", color=teal, label="query p50")
    ax.plot([x["reports"] for x in e], [x["p95_ms"] for x in e], marker="o", color=amber, label="query p95")
    ax2 = ax.twinx()
    ax2.bar([x["reports"] for x in e], [x["index_build_s"] for x in e], width=60, alpha=0.25, color=blue,
            label="index build (s)")
    ax2.set_ylabel("index build seconds", color=blue)
    ax.set_title("Corpus scaling", color=ink, fontsize=12, weight="bold")
    ax.set_xlabel("stored reports")
    ax.set_ylabel("query latency ms")
    ax.legend(loc="upper left", fontsize=8.5)
    for a in axes:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "load_test_charts.png", facecolor="white")


if __name__ == "__main__":
    main()
