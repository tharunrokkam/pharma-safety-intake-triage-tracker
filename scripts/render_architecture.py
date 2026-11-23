"""Render the Plan Mode architecture infographic for the Pharma Safety Intake & Triage Tracker.

Usage:  python scripts/render_architecture.py
Output: docs/architecture.png (4800x3000 @200 dpi) and docs/architecture.svg

Pure matplotlib, deterministic output, no network access, no data inputs.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import (  # noqa: E402
    Circle,
    Ellipse,
    FancyArrowPatch,
    FancyBboxPatch,
    Polygon,
    Rectangle,
    RegularPolygon,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "docs"

# ---------------------------------------------------------------- palette (per layer)
C = {
    "ui": ("#1D4ED8", "#DBEAFE"),
    "cp": ("#6D28D9", "#EDE9FE"),
    "rag": ("#0F766E", "#CCFBF1"),
    "db": ("#B45309", "#FEF3C7"),
    "gov": ("#334155", "#E2E8F0"),
    "guard": ("#B91C1C", "#FEE2E2"),
    "life": ("#15803D", "#DCFCE7"),
}
INK = "#0F172A"
MUTED = "#475569"

fig = plt.figure(figsize=(24, 15), dpi=200)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 240)
ax.set_ylim(0, 150)
ax.axis("off")
fig.patch.set_facecolor("white")


# ---------------------------------------------------------------- primitives
def lane(x, y, w, h, title, layer, subtitle=""):
    edge, fill = C[layer]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6",
                                fc=fill, ec=edge, lw=1.6, alpha=0.35, zorder=0))
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6",
                                fc="none", ec=edge, lw=1.6, zorder=1))
    ax.text(x + 1.4, y + h - 1.2, title, fontsize=13, weight="bold", color=edge, va="top", zorder=10,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.92))
    if subtitle:
        ax.text(x + w - 1.4, y + h - 1.3, subtitle, fontsize=9.5, color=edge, va="top", ha="right",
                style="italic", zorder=5)


def box(x, y, w, h, title, body="", layer="cp", title_size=10.5, body_size=8.6, fill=None):
    edge, light = C[layer]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.0",
                                fc=fill or "white", ec=edge, lw=1.5, zorder=3))
    ax.add_patch(FancyBboxPatch((x, y + h - 3.0), w, 3.0, boxstyle="round,pad=0,rounding_size=1.0",
                                fc=light, ec="none", zorder=3.5))
    ax.text(x + w / 2, y + h - 1.5, title, fontsize=title_size, weight="bold", color=edge,
            ha="center", va="center", zorder=6)
    if body:
        ax.text(x + 1.0, y + h - 3.7, body, fontsize=body_size, color=INK, ha="left", va="top",
                linespacing=1.35, zorder=6)


def badge(x, y, label, layer="cp", r=1.7, size=10.5):
    edge, _ = C[layer]
    ax.add_patch(Circle((x, y), r, fc=edge, ec="white", lw=1.5, zorder=8))
    ax.text(x, y - 0.05, label, fontsize=size, weight="bold", color="white", ha="center",
            va="center", zorder=9)


def arrow(p1, p2, label="", color=INK, style="-|>", ls="-", rad=0.0, lw=1.5, lpos=0.5,
          loff=(0, 0.9), lsize=8.2, lcolor=None):
    a = FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=14, color=color, lw=lw,
                        linestyle=ls, connectionstyle=f"arc3,rad={rad}", zorder=7,
                        shrinkA=1, shrinkB=1)
    ax.add_patch(a)
    if label:
        mx = p1[0] + (p2[0] - p1[0]) * lpos + loff[0]
        my = p1[1] + (p2[1] - p1[1]) * lpos + loff[1]
        ax.text(mx, my, label, fontsize=lsize, color=lcolor or color, ha="center", va="center",
                zorder=9, bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.9))


def cylinder(x, y, w, h, title, body, layer="db"):
    edge, fill = C[layer]
    eh = 2.2
    ax.add_patch(Rectangle((x, y + eh / 2), w, h - eh, fc=fill, ec="none", zorder=3))
    ax.plot([x, x], [y + eh / 2, y + h - eh / 2], color=edge, lw=1.5, zorder=4)
    ax.plot([x + w, x + w], [y + eh / 2, y + h - eh / 2], color=edge, lw=1.5, zorder=4)
    ax.add_patch(Ellipse((x + w / 2, y + eh / 2), w, eh, fc=fill, ec=edge, lw=1.5, zorder=3.5))
    ax.add_patch(Rectangle((x + 0.1, y + eh / 2), w - 0.2, 1.2, fc=fill, ec="none", zorder=3.6))
    ax.add_patch(Ellipse((x + w / 2, y + h - eh / 2), w, eh, fc="white", ec=edge, lw=1.5, zorder=4))
    ax.text(x + w / 2, y + h - eh - 1.4, title, fontsize=10, weight="bold", color=edge,
            ha="center", va="center", zorder=6)
    ax.text(x + w / 2, y + h - eh - 3.2, body, fontsize=8.1, color=INK, ha="center", va="top",
            linespacing=1.3, zorder=6)


def person(x, y, label, sub, layer="ui"):
    edge, fill = C[layer]
    ax.add_patch(Circle((x, y + 3.2), 1.3, fc=fill, ec=edge, lw=1.5, zorder=4))
    ax.add_patch(FancyBboxPatch((x - 2.2, y - 0.6), 4.4, 2.6, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=fill, ec=edge, lw=1.5, zorder=4))
    ax.text(x + 3.3, y + 2.6, label, fontsize=9.5, weight="bold", color=edge, va="center", zorder=6)
    ax.text(x + 3.3, y + 0.6, sub, fontsize=8.2, color=MUTED, va="center", zorder=6)


def chip(x, y, text, fc, ec, tc="white", size=9.5):
    ax.text(x, y, text, fontsize=size, color=tc, weight="bold", ha="center", va="center", zorder=9,
            bbox=dict(boxstyle="round,pad=0.45,rounding_size=0.9", fc=fc, ec=ec, lw=1.2))


# ================================================================ TITLE BANNER
ax.add_patch(FancyBboxPatch((2, 141), 236, 8, boxstyle="round,pad=0,rounding_size=1.6",
                            fc="#0B1F44", ec="none", zorder=1))
ax.text(4.5, 146.6, "Pharma Safety Intake & Triage Tracker  —  Solution Architecture",
        fontsize=22, weight="bold", color="white", va="center", zorder=5)
ax.text(4.5, 143.0, "Plan Mode output  |  Streamlit + LangGraph control plane + LangChain 4-stage hybrid RAG"
        "  |  deterministic (no LLM), strictly local, SQLite",
        fontsize=11, color="#BFDBFE", va="center", zorder=5)
chip(176, 145, "SYNTHETIC DATA ONLY", "#B45309", "#FDE68A")
chip(198.5, 145, "NON-CLINICAL", "#B91C1C", "#FECACA")
chip(222, 145, "LOCAL - NO CLOUD / NO LLM", "#15803D", "#BBF7D0")

# ================================================================ LANE 1 — UI
lane(2, 123, 189, 16.5, "1  Presentation  |  Streamlit multipage UI (localhost)", "ui",
     "every page calls the SAME tool layer")
person(6, 130.0, "Intake Operator", "OP-xx (pseudonymous)")
person(6, 124.6, "Triage Reviewer", "REV-xx (pseudonymous)")

pages = [
    (33, "Knowledge Agent", "chat: history & SOP lookup\n+ pipeline inspector"),
    (64, "New Report", "intake form, AE fields shown\nonly for Suspected AE"),
    (95, "Dashboard / Tracker", "table + filters by status &\ntype, metrics, actions"),
    (126, "Triage Approvals", "HITL queue: approve/reject\n+ mandatory justification"),
    (157, "Audit Trail", "read-only log viewer\n+ hash-chain verification"),
]
for px, t, b in pages:
    box(px, 124.3, 29.5, 11.6, t, b, "ui", title_size=10.5, body_size=8.4)

# ================================================================ LANE 2 — CONTROL PLANE
lane(2, 83, 189, 38.5, "2  LangGraph Control Plane  |  StateGraph(AgentState) — deterministic 5-step orchestration",
     "cp", "")

box(4, 95, 23, 17, "input_guard", "PII regex shield\n(email, phone, DOB,\n names, IDs)\nclinical-scope filter\n(causality, treatment,\n reportability)", "guard",
    body_size=8.2)
box(31, 95, 25, 17, "Semantic Router", "ordered regex rules,\nruns BEFORE any tool:\n1 scope refusal\n2 greeting / help\n3 REF-id + verb\n4 intake phrases\n5 default -> RAG", "cp",
    body_size=8.2)
badge(31.6, 111.6, "3")

routes = [
    (109, "Direct Response", "guard"),
    (101, "Intake Form Tool", "cp"),
    (93, "Status Workflow Mgr", "cp"),
    (85, "Hybrid RAG Lookup", "rag"),
]
for ry, t, layer in routes:
    edge, light = C[layer]
    ax.add_patch(FancyBboxPatch((61, ry), 26, 6, boxstyle="round,pad=0,rounding_size=1.0",
                                fc=light, ec=edge, lw=1.5, zorder=3))
    ax.text(74, ry + 3, t, fontsize=9.6, weight="bold", color=edge, ha="center", va="center", zorder=6)
    arrow((56, 103.5), (61, ry + 3), color=C["cp"][0], lw=1.3)

box(93, 93, 25, 19, "Tool Validator", "Pydantic v2 args_schema\nbatch_id ^LOT-\\d{5}$\nref_id ^REF-\\d{4}-\\d{4}$\nextra='forbid'\nauto-repair: tool-name\nfuzzy match, key aliases,\n'lot 88392'->'LOT-88392'", "cp",
    body_size=8.1)
badge(93.6, 111.6, "1")
arrow((87, 104), (93, 104), color=C["cp"][0])
arrow((87, 96), (93, 98), color=C["cp"][0])

box(123, 101, 21, 11, "Execute Tool", "LangChain StructuredTool\nsubmit_intake_report\nupdate_status, get_report", "cp",
    body_size=8.0)
arrow((118, 106), (123, 106), "valid", color=C["life"][0], loff=(0, 1.2))

box(123, 84.5, 21, 14, "Circuit Breaker", "sig = sha256(tool+args)\nsame invalid call\n> 2 consecutive -> OPEN\nreset on success or\nnew signature", "guard",
    body_size=8.0)
badge(123.6, 98.1, "5", "guard")
arrow((118, 96), (123, 93), "invalid", color=C["guard"][0], loff=(-0.4, 1.4))

hx, hy = 154.5, 89.5
ax.add_patch(RegularPolygon((hx, hy), numVertices=8, radius=4.6, orientation=0.3927,
                            fc=C["guard"][0], ec="white", lw=1.5, zorder=4))
ax.text(hx, hy + 0.6, "HALT", fontsize=10.5, weight="bold", color="white", ha="center", va="center", zorder=6)
ax.text(hx, hy - 1.5, "CIRCUIT_OPEN", fontsize=6.4, color="white", ha="center", va="center", zorder=6)
arrow((144, 89.5), (149.9, 89.5), "3rd", color=C["guard"][0], loff=(0, 1.2), lsize=7.6)
ax.text(161, 91.5, "<=2: structured\nerror returned,\nuser corrects input", fontsize=7.6, color=C["guard"][0],
        va="top", style="italic", zorder=6)

box(148, 100, 20, 14.5, "HITL Gate", "In Review -> Closed only\ninterrupt()  : state frozen\napprovals row = PENDING\nCommand(resume=...)", "guard",
    body_size=7.9)
badge(148.6, 114.1, "4", "guard")
arrow((144, 106), (148, 106), "close?", color=C["guard"][0], loff=(0, 1.2), lsize=7.6)

box(172, 107.5, 17.5, 8.5, "Approve", "commit Closed\naudit APPROVAL_GRANTED", "life", body_size=7.6)
box(172, 98.5, 17.5, 8, "Reject", "stays In Review\naudit APPROVAL_REJECTED", "guard", body_size=7.6)
arrow((168, 109), (172, 111), color=C["life"][0])
arrow((168, 104), (172, 102.5), color=C["guard"][0])

# UI -> control plane arrows
arrow((40, 124.3), (15.5, 112), "chat query", color=C["ui"][0], rad=0.12, lpos=0.66, loff=(1.5, 0))
arrow((78, 124.3), (101, 112), "form -> submit_intake_report", color=C["ui"][0], rad=-0.05, lpos=0.66, loff=(-4, 0))
arrow((109, 124.3), (111, 112), "status buttons", color=C["ui"][0], lpos=0.66, loff=(5.5, 0))
arrow((140, 124.3), (158, 114.5), "approve / reject -> Command(resume)", color=C["ui"][0], rad=-0.1, lpos=0.62, loff=(-1, 0))


# ================================================================ LANE 3 — HYBRID RAG
lane(2, 52, 189, 29.5, "3  Multi-Stage Hybrid RAG  |  LangChain retrievers -> zero-hallucination extractive answer", "rag")
# funnel backdrop
ax.add_patch(Polygon([(58, 77.6), (153.5, 72.5), (153.5, 59.5), (58, 54.0)], closed=True,
                     fc=C["rag"][1], ec="none", alpha=0.75, zorder=1.5))

box(4, 55, 24, 21.5, "Corpus", "synthetic SOPs\n(data/sops/*.md)\n+ saved reports\n(metadata: ref_id,\n type, batch, status)\nLangChain Document", "rag",
    body_size=8.2)
box(32, 55, 22, 21.5, "Chunking", "RecursiveCharacter-\nTextSplitter\n.from_huggingface_\n tokenizer\n512-token chunks\n64-token overlap", "rag",
    body_size=8.2)
arrow((28, 65.75), (32, 65.75), color=C["rag"][0])

box(59, 67, 28, 10.5, "Stage 1  BM25 sparse", "BM25Retriever (rank-bm25)\nk1 = 1.3  b = 0.75  -> top-50\nexact LOT-88392 / codes", "rag",
    body_size=8.0)
box(59, 54, 28, 11.5, "Stage 2  Bi-Encoder dense", "HuggingFaceEmbeddings\nbge-small-en-v1.5 + FAISS\ncosine (normalised) -> top-50\n'difficulty breathing'~dyspnea", "rag",
    body_size=7.9)
badge(59.6, 77.1, "S1", "rag", r=1.6, size=8)
badge(59.6, 65.1, "S2", "rag", r=1.6, size=8)
arrow((54, 68), (59, 72), color=C["rag"][0])
arrow((54, 63), (59, 59.5), color=C["rag"][0])

box(93, 56, 26, 19, "Stage 3  RRF fusion", "score(d) = sum 1/(k + rank_i)\nk = 60, rank-only:\nno score normalisation,\nno outlier dominance\ndedupe by chunk_id", "rag",
    body_size=8.1)
badge(93.6, 74.6, "S3", "rag", r=1.6, size=8)
arrow((87, 72), (93, 68.5), "50", color=C["rag"][0], loff=(-0.6, 1.4), lsize=8)
arrow((87, 60), (93, 63), "50", color=C["rag"][0], loff=(-0.6, -1.5), lsize=8)

box(124, 57, 28.5, 17, "Stage 4  Cross-Encoder", "ms-marco-MiniLM-L-6-v2\njoint attention (query, chunk)\nsigmoid score >= 0.40\nkeep Top-3 .. Top-5", "rag",
    body_size=8.1)
badge(124.6, 73.6, "S4", "rag", r=1.6, size=8)
arrow((119, 65.5), (124, 65.5), "<=100", color=C["rag"][0], loff=(0, 1.3), lsize=7.6)

box(157.5, 55, 26.5, 21.5, "Extractive Composer", "quotes chunks verbatim\nwith citations\n[REF-2026-0001] [SOP-03]\n+ fixed non-clinical\n disclaimer\n0 chunks >= 0.40\n -> ABSTAIN", "life",
    body_size=8.1)
arrow((152.5, 65.5), (157.5, 65.5), "3-5", color=C["rag"][0], loff=(0, 1.3), lsize=7.6)

arrow((74, 85), (73, 77.6), "query", color=C["rag"][0], loff=(3.2, 0.3), lsize=8)

# ================================================================ LANE 4 — PERSISTENCE
lane(2, 31, 189, 19.3, "4  Persistence  |  SQLite (WAL) long-term memory + local retrieval index", "db",
     "written only through the tool layer")
cyl = [
    ("reports", "REF-YYYY-XXXX PK\ncore fields, status"),
    ("ae_details", "event description\nonset date (no PII)"),
    ("ref_counters", "per-year sequence\nBEGIN IMMEDIATE"),
    ("RAG index", "FAISS vectors +\nBM25 corpus"),
    ("status_transitions", "from -> to, actor,\ntimestamp"),
    ("approvals", "PENDING / APPROVED /\nREJECTED, reviewer"),
    ("audit_log", "append-only triggers\nSHA-256 hash chain"),
]
cx = 5.0
for t, b in cyl:
    cylinder(cx, 32.2, 23.3, 13.2, t, b, "rag" if t == "RAG index" else "db")
    cx += 25.6
arrow((16, 45.6), (16, 55), "re-index", color=C["db"][0], ls=(0, (4, 3)), loff=(3.6, 0), lsize=7.6)
arrow((80, 54), (93.5, 45.6), "", color=C["rag"][0], ls=(0, (4, 3)), rad=0.0, lw=1.1)
ax.text(100.5, 51.0, "embeddings persisted", fontsize=7.6, color=C["rag"][0], ha="center", zorder=9,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
arrow((190, 98.5), (190, 50.3), "", color=C["db"][0], lw=1.6)
ax.text(189.9, 80, "writes  /  audit reads", fontsize=7.6, color=C["db"][0], rotation=90, ha="center", va="center", zorder=9,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))

# ================================================================ RIGHT COLUMN — LIFECYCLE
lane(194, 98, 44, 41.5, "Status Lifecycle", "life")
states = [(129.5, "New"), (119.0, "In Review"), (100.8, "Closed")]
for sy, s in states:
    ax.add_patch(FancyBboxPatch((197, sy), 18, 5.4, boxstyle="round,pad=0,rounding_size=2.6",
                                fc=C["life"][1], ec=C["life"][0], lw=1.6, zorder=4))
    ax.text(206, sy + 2.7, s, fontsize=10.5, weight="bold", color=C["life"][0], ha="center", va="center", zorder=6)
ax.add_patch(RegularPolygon((206, 111.6), numVertices=4, radius=4.0, fc=C["guard"][1], ec=C["guard"][0],
                            lw=1.6, zorder=4))
ax.text(206, 111.6, "HITL", fontsize=9, weight="bold", color=C["guard"][0], ha="center", va="center", zorder=6)
arrow((206, 129.5), (206, 124.4), color=C["life"][0])
arrow((206, 119.0), (206, 115.6), color=C["life"][0])
arrow((206, 107.6), (206, 106.2), color=C["life"][0])
ax.text(196.5, 109.2, "approve", fontsize=7.2, color=C["life"][0], ha="left", va="center", zorder=6)
ax.text(217.5, 134.0, "Illegal (raise\nIllegalTransitionError):", fontsize=8, weight="bold", color=C["guard"][0],
        ha="left", va="top", zorder=6)
ax.text(217.5, 127.8, "X  New -> Closed (skip)\nX  In Review -> New\nX  Closed -> anything\nX  same-state no-op",
        fontsize=7.9, color=C["guard"][0], ha="left", va="top", linespacing=1.5, zorder=6)
ax.text(217.5, 114.5, "Defense in depth:\nrepository refuses\nClosed unless an\nAPPROVED approval\nrow exists; reviewer\n!= requester (SoD)",
        fontsize=7.7, color=INK, ha="left", va="top", linespacing=1.35, zorder=6)

# ================================================================ RIGHT COLUMN — DUAL MEMORY
lane(194, 52, 44, 44.5, "Dual-Memory Engine", "cp")
badge(234.5, 94.0, "2")
box(196, 72.5, 40, 19, "Short-term (volatile)", "LangGraph InMemorySaver per thread_id\nAgentState: route, tool_call, breaker,\nretrieval stages, response\nReAct trace (rule-explained):", "cp",
    body_size=7.9)
for i, (lbl, xx) in enumerate([("Thought", 200.5), ("Action", 214.0), ("Observation", 228.0)]):
    ax.text(xx, 79.0, lbl, fontsize=7.8, weight="bold", color=C["cp"][0], ha="center", va="center", zorder=9,
            bbox=dict(boxstyle="round,pad=0.3", fc=C["cp"][1], ec=C["cp"][0], lw=1))
arrow((204.6, 79.0), (209.6, 79.0), color=C["cp"][0], lw=1.1)
arrow((218.3, 79.0), (221.4, 79.0), color=C["cp"][0], lw=1.1)
box(196, 54, 40, 16, "Long-term (durable)", "SQLite: reports, ae_details,\nstatus_transitions, approvals,\naudit_log (survives restart;\npending HITL re-listed from DB)", "db",
    body_size=7.9)

# ================================================================ RIGHT COLUMN — LEGEND
lane(194, 31, 44, 19.3, "Legend", "gov")
legend = [("ui", "Presentation (Streamlit)"), ("cp", "Control plane (LangGraph)"),
          ("guard", "Guardrails / HITL / breaker"), ("rag", "Hybrid RAG (LangChain)"),
          ("db", "Persistence (SQLite)"), ("life", "Lifecycle / safe output")]
for i, (k, t) in enumerate(legend):
    col, row = i % 2, i // 2
    lx, ly = 196 + col * 21, 43.5 - row * 4.6
    ax.add_patch(FancyBboxPatch((lx, ly - 1.1), 2.6, 2.2, boxstyle="round,pad=0,rounding_size=0.5",
                                fc=C[k][1], ec=C[k][0], lw=1.4, zorder=4))
    ax.text(lx + 3.4, ly, t, fontsize=7.6, color=INK, va="center", zorder=6)

# ================================================================ GOVERNANCE STRIP
lane(2, 8.5, 236, 21, "5  AI Engineering Governance  |  Claude Code phases I - V  +  verification", "gov")
gov = [
    ("I", "CLAUDE.md", "persistent contract: scope\nlimits, non-clinical rule,\narchitecture invariants,\ncoding + test conventions,\nfictional-data handling"),
    ("II", "Plan Mode", "this blueprint, reviewed\n& approved before code;\nsurfaced edge cases (AE\nconditional fields, 0.40\nsigmoid, 512-tok encoder)"),
    ("III", "Incremental Build", "A  Skeleton setup\nB  Intake form & schemas\nC  Validation & persistence\nD  Dashboard & lifecycle\nE  Hybrid RAG + agent"),
    ("IV", "Review Skill", ".claude/skills/\n pharma-intake-review/\nchecklists: data minim.,\nerror handling, audit-\nability, test coverage"),
    ("V", "PostToolUse Hook", "matcher Edit|Write|...\n-> logs/claude_edit_\n   audit.jsonl\nts, tool, path, hash only\nNO content / descriptions"),
    ("T", "Automated Tests", "pytest unit + integration:\nschemas & regex, storage\nintegrity, audit triggers,\nbreaker (2 ok / 3rd trips),\nHITL, RRF math, retrieval"),
]
gx = 4.5
for num, t, b in gov:
    box(gx, 9.6, 36.5, 15.6, t, b, "gov", title_size=10.5, body_size=8.0)
    badge(gx + 2.0, 23.7, num, "gov", r=1.55, size=8.5 if len(num) > 1 else 9.5)
    gx += 39.0
for i in range(5):
    x0 = 4.5 + 36.5 + i * 39.0
    arrow((x0 + 0.2, 17.4), (x0 + 2.3, 17.4), color=C["gov"][0], lw=1.3)

# ================================================================ FOOTER
ax.text(120, 4.6,
        "Stack: Python 3.12  |  Streamlit  |  Pydantic v2  |  LangGraph (StateGraph, interrupt, Command, InMemorySaver)  |  "
        "LangChain (BM25Retriever, HuggingFaceEmbeddings, FAISS, HuggingFaceCrossEncoder, text splitters)  |  "
        "sentence-transformers  |  SQLite  |  pytest",
        fontsize=9, color=MUTED, ha="center", va="center")
ax.text(120, 1.9,
        "Training prototype - fictional data only. The system never assesses causality, recommends treatment, "
        "determines reportability or makes clinical / regulatory decisions.",
        fontsize=8.6, color=C["guard"][0], ha="center", va="center", style="italic")

OUT_DIR.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT_DIR / "architecture.png", dpi=200, facecolor="white")
fig.savefig(OUT_DIR / "architecture.svg", facecolor="white")
print(f"wrote {OUT_DIR / 'architecture.png'} and .svg")
