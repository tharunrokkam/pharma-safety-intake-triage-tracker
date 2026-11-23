"""Build the capstone presentation deck (PPTX with speaker notes) from measured artefacts.

Inputs (all generated earlier):
  docs/presentation/screenshots/*.png      scripts/capture_screenshots.py
  docs/presentation/load_test_results.json scripts/load_test.py
  docs/presentation/test_output.txt        pytest run
  docs/presentation/token_usage.json       Claude Code transcript usage snapshot
Output: docs/presentation/Pharma_Safety_Intake_Capstone.pptx
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "docs" / "presentation"
SHOTS = P / "screenshots"
CROPS = P / "crops"
CROPS.mkdir(parents=True, exist_ok=True)

NAVY = RGBColor(0x0B, 0x1F, 0x44)
INK = RGBColor(0x0F, 0x17, 0x2A)
MUTED = RGBColor(0x47, 0x55, 0x69)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C = {
    "ui": (RGBColor(0x1D, 0x4E, 0xD8), RGBColor(0xDB, 0xEA, 0xFE)),
    "cp": (RGBColor(0x6D, 0x28, 0xD9), RGBColor(0xED, 0xE9, 0xFE)),
    "rag": (RGBColor(0x0F, 0x76, 0x6E), RGBColor(0xCC, 0xFB, 0xF1)),
    "db": (RGBColor(0xB4, 0x53, 0x09), RGBColor(0xFE, 0xF3, 0xC7)),
    "guard": (RGBColor(0xB9, 0x1C, 0x1C), RGBColor(0xFE, 0xE2, 0xE2)),
    "life": (RGBColor(0x15, 0x80, 0x3D), RGBColor(0xDC, 0xFC, 0xE7)),
    "gov": (RGBColor(0x33, 0x41, 0x55), RGBColor(0xE2, 0xE8, 0xF0)),
}

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = 13.333, 7.5


# ============================================================ image prep
def crop(name: str, box: tuple[int, int, int, int], out: str) -> Path:
    img = Image.open(SHOTS / f"{name}.png")
    w, h = img.size
    x0, y0, x1, y1 = box
    img.crop((x0, y0, min(x1, w), min(y1, h))).save(CROPS / f"{out}.png")
    return CROPS / f"{out}.png"


def render_terminal(text: str, out: Path, title: str) -> Path:
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 17)
    bold = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 17)
    lines = text.rstrip().splitlines()
    lh, pad = 24, 22
    width = max(900, max(int(font.getlength(ln)) for ln in lines) + 2 * pad)
    height = len(lines) * lh + 2 * pad + 36
    img = Image.new("RGB", (width, height), (15, 23, 42))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, 34], fill=(30, 41, 59))
    for i, col in enumerate([(239, 68, 68), (234, 179, 8), (34, 197, 94)]):
        d.ellipse([14 + i * 22, 11, 26 + i * 22, 23], fill=col)
    d.text((90, 8), title, font=font, fill=(148, 163, 184))
    for i, ln in enumerate(lines):
        col = (226, 232, 240)
        f = font
        if "passed" in ln or "TOTAL" in ln:
            col, f = (74, 222, 128), bold
        elif ln.startswith("$"):
            col = (125, 211, 252)
        elif "100%" in ln:
            col = (134, 239, 172)
        d.text((pad, 36 + pad + i * lh), ln, font=f, fill=col)
    img.save(out)
    return out


# ============================================================ slide helpers
def add_slide(title: str, subtitle: str = "", section: str = "", timing: str = ""):
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.95))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    tb = s.shapes.add_textbox(Inches(0.45), Inches(0.12), Inches(10.6), Inches(0.75))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size, p.font.bold, p.font.color.rgb = Pt(26), True, WHITE
    if section:
        t2 = s.shapes.add_textbox(Inches(10.6), Inches(0.18), Inches(2.5), Inches(0.6))
        q = t2.text_frame.paragraphs[0]
        q.text = section
        q.alignment = PP_ALIGN.RIGHT
        q.font.size, q.font.color.rgb = Pt(11), RGBColor(0xBF, 0xDB, 0xFE)
        if timing:
            q2 = t2.text_frame.add_paragraph()
            q2.text = timing
            q2.alignment = PP_ALIGN.RIGHT
            q2.font.size, q2.font.color.rgb, q2.font.bold = Pt(10), RGBColor(0xFD, 0xE6, 0x8A), True
    if subtitle:
        st = s.shapes.add_textbox(Inches(0.45), Inches(1.02), Inches(12.4), Inches(0.45))
        sp = st.text_frame.paragraphs[0]
        sp.text = subtitle
        sp.font.size, sp.font.italic, sp.font.color.rgb = Pt(14), True, MUTED
    foot = s.shapes.add_textbox(Inches(0.45), Inches(7.08), Inches(12.4), Inches(0.3))
    fp = foot.text_frame.paragraphs[0]
    fp.text = ("Pharma Safety Intake & Triage Tracker  |  Fictional data only - non-clinical training prototype"
               f"  |  {len(prs.slides)}")
    fp.font.size, fp.font.color.rgb = Pt(9), MUTED
    return s


def notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def bullets(slide, items, x, y, w, h, size=15, color=INK, gap=4):
    """items: str or (str, level) or ("**bold** rest", level)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for it in items:
        text, lvl = (it, 0) if isinstance(it, str) else it
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.level = lvl
        p.space_after = Pt(gap)
        prefix = "•  " if lvl == 0 else "–  "
        parts = text.split("**")
        r0 = p.add_run()
        r0.text = prefix
        r0.font.size, r0.font.color.rgb = Pt(size - 2 * lvl), color
        for i, part in enumerate(parts):
            if not part:
                continue
            r = p.add_run()
            r.text = part
            r.font.size = Pt(size - 2 * lvl)
            r.font.color.rgb = color
            r.font.bold = i % 2 == 1
    return tb


def card(slide, x, y, w, h, title, body, layer="cp", title_size=14, body_size=11.5):
    edge, fill = C[layer]
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = 0.08
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = edge
    shp.line.width = Pt(1.5)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = Inches(0.08)
    p = tf.paragraphs[0]
    p.text = title
    p.font.size, p.font.bold, p.font.color.rgb = Pt(title_size), True, edge
    for line in body.split("\n") if body else []:
        q = tf.add_paragraph()
        q.text = line
        q.font.size, q.font.color.rgb = Pt(body_size), INK
        q.space_before = Pt(2)
    return shp


def arrow(slide, x1, y1, x2, y2, color=INK):
    con = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    con.line.color.rgb = color
    con.line.width = Pt(2)
    ln = con.line._get_or_add_ln()
    from lxml import etree
    tail = etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd")
    tail.set("type", "triangle")
    return con


def table(slide, rows, x, y, w, col_w=None, size=11, header_layer="cp", row_h=0.32):
    nrows, ncols = len(rows), len(rows[0])
    shp = slide.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(row_h * nrows))
    t = shp.table
    if col_w:
        for i, cw in enumerate(col_w):
            t.columns[i].width = Inches(cw)
    edge, fill = C[header_layer]
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.text = str(val)
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            para = cell.text_frame.paragraphs[0]
            para.font.size = Pt(size)
            if r == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = edge
                para.font.bold, para.font.color.rgb = True, WHITE
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if r % 2 else fill
                para.font.color.rgb = INK
    return shp


def image(slide, path: Path, x, y, w, h, border=True):
    """Fit image inside box (inches) preserving aspect, centred."""
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    pic = slide.shapes.add_picture(str(path), Inches(x + (w - dw) / 2), Inches(y + (h - dh) / 2),
                                   Inches(dw), Inches(dh))
    if border:
        pic.line.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
        pic.line.width = Pt(1)
    return pic


def caption(slide, text, x, y, w, size=11, color=MUTED, bold=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.4))
    tb.text_frame.word_wrap = True
    p = tb.text_frame.paragraphs[0]
    p.text = text
    p.font.size, p.font.color.rgb, p.font.bold = Pt(size), color, bold
    return tb


def metric(slide, x, y, w, value, label, layer="life"):
    edge, fill = C[layer]
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(1.05))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = edge
    tf = shp.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = value
    p.alignment = PP_ALIGN.CENTER
    p.font.size, p.font.bold, p.font.color.rgb = Pt(26), True, edge
    q = tf.add_paragraph()
    q.text = label
    q.alignment = PP_ALIGN.CENTER
    q.font.size, q.font.color.rgb = Pt(11), INK


# ============================================================ data
lt = json.loads((P / "load_test_results.json").read_text(encoding="utf-8"))
tok = json.loads((P / "token_usage.json").read_text(encoding="utf-8"))
test_txt = (P / "test_output.txt").read_text(encoding="utf-8")
passed_line = [ln for ln in test_txt.splitlines() if " passed" in ln][-1].strip("= ")
total_line = [ln for ln in test_txt.splitlines() if ln.startswith("TOTAL")][-1]
coverage = total_line.split()[-1]
n_passed = passed_line.split(" passed")[0].split()[-1]
hook_events = sum(1 for _ in (ROOT / "logs" / "claude_edit_audit.jsonl").open(encoding="utf-8"))
rag = json.loads((ROOT / "docs" / "demo" / "rag_query_result.json").read_text(encoding="utf-8"))

# crops (main content area, sidebar removed)
img_intake_err = crop("02_intake_validation_errors", (370, 100, 1530, 1170), "intake_errors")
img_intake_ok = crop("03_intake_success", (370, 100, 1530, 900), "intake_ok")
img_dash = crop("05_dashboard_detail_in_review", (370, 100, 1530, 1110), "dashboard")
img_dash_req = crop("06_dashboard_closure_requested", (370, 100, 1530, 1000), "dashboard_req")
img_triage = crop("07_triage_pending", (370, 100, 1530, 980), "triage_pending")
img_triage_ok = crop("08_triage_approved", (370, 100, 1530, 890), "triage_ok")
img_rag_ans = crop("09_rag_answer_and_inspector", (370, 230, 1530, 1120), "rag_answer")
img_rag_insp = crop("09_rag_answer_and_inspector", (430, 1130, 1530, 2140), "rag_inspector")
img_guard = crop("10_guardrails_refusal_abstain_breaker", (370, 270, 1530, 1830), "guardrails")
img_audit = crop("11_audit_trail_and_hook_log", (370, 100, 1530, 1360), "audit")
img_home = crop("01_home", (370, 60, 1600, 1000), "home")
img_tests = render_terminal(test_txt, CROPS / "pytest_output.png", "pytest -q --cov=pharma_tracker")

# ============================================================ 1 Title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = NAVY
bg.line.fill.background()
caption(s, "ADVANCED ENTERPRISE CAPSTONE", 0.8, 1.3, 11, 14, RGBColor(0xFD, 0xE6, 0x8A), True)
tb = s.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.5), Inches(1.6))
tb.text_frame.word_wrap = True
p = tb.text_frame.paragraphs[0]
p.text = "Pharma Safety Intake & Triage Tracker"
p.font.size, p.font.bold, p.font.color.rgb = Pt(44), True, WHITE
q = tb.text_frame.add_paragraph()
q.text = "Multi-stage hybrid RAG & deterministic agentic workflow orchestration with LangGraph + LangChain"
q.font.size, q.font.color.rgb = Pt(20), RGBColor(0xBF, 0xDB, 0xFE)
caption(s, "Presenter: <your name>   |   Capstone defense   |   15 minutes", 0.8, 3.75, 11, 16, WHITE)
for i, (t, layer) in enumerate([("Synthetic data only", "db"), ("Non-clinical", "guard"),
                                ("Strictly local - no cloud / no LLM", "life")]):
    chip = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8 + i * 3.3), Inches(4.6), Inches(3.0),
                              Inches(0.5))
    chip.fill.solid()
    chip.fill.fore_color.rgb = C[layer][0]
    chip.line.fill.background()
    cp = chip.text_frame.paragraphs[0]
    cp.text = t
    cp.alignment = PP_ALIGN.CENTER
    cp.font.size, cp.font.bold, cp.font.color.rgb = Pt(13), True, WHITE
caption(s, "Python 3.12 · Streamlit · Pydantic v2 · LangGraph · LangChain · FAISS · rank-bm25 · "
           "sentence-transformers · SQLite · pytest · Claude Code (CLAUDE.md, Plan Mode, Skills, Hooks)",
        0.8, 6.3, 11.8, 12, RGBColor(0x94, 0xA3, 0xB8))
notes(s, "Open with the one-line pitch: a local, auditable intake and triage tracker for fictional pharmacovigilance "
         "reports, with a deterministic agent that can search history and SOPs without ever hallucinating. "
         "Stress the three boundaries on the chips - they shaped every design decision.")

# ============================================================ 2 Agenda
s = add_slide("Agenda & time plan", "15-minute capstone evaluation")
table(s, [["Segment", "Duration", "Slides / content"],
          ["Project overview & architecture", "2 min", "Business problem, solution, process flow, architecture"],
          ["Live solution demonstration", "6 min", "Intake -> dashboard -> HITL closure -> Knowledge Agent RAG -> guardrails -> audit"],
          ["Technical highlights, challenges & outcomes", "2 min", "Governance, evaluation, load test, tokens, lessons"],
          ["Panel Q&A", "5 min", "Backup slides: production readiness, likely questions"],
          ["Total", "15 min", ""]],
      0.6, 1.7, 12.1, col_w=[3.6, 1.4, 7.1], size=14, row_h=0.55)
bullets(s, ["Backup slides cover every guideline topic in depth (MCP, token usage, deployment, load testing), "
            "so the live segment can stay focused on the demo.",
            "All screenshots, metrics and logs in this deck were produced by scripts in the repository "
            "(capture_screenshots.py, load_test.py, seed_demo.py, pytest)."],
        0.6, 5.3, 12.1, 1.5, size=13, color=MUTED)
notes(s, "Set expectations: 2 minutes of context, 6 minutes of live demo, 2 minutes of highlights, 5 of Q&A.")

# ============================================================ 3 Business problem
s = add_slide("Business problem", "Manual, spreadsheet-based safety intake is slow, incomplete and hard to audit",
              "Overview", "≈ 2 min block")
card(s, 0.6, 1.7, 3.9, 2.4, "Today", "Complaints & suspected adverse events arrive by email and phone\n"
     "Operators type them into scattered spreadsheets\nNo shared view of what is new, in review or closed", "guard")
card(s, 4.72, 1.7, 3.9, 2.4, "Pain points", "Missing mandatory fields (lot, onset date)\nInconsistent formats "
     "(\"lot 88392\" vs LOT-88392)\nOpaque review hand-offs\nNo immutable audit log\nPersonal data creeps into free text",
     "db")
card(s, 8.84, 1.7, 3.9, 2.4, "Consequences", "Re-work and follow-up calls\nSlow historical look-ups "
     "(\"have we seen this lot before?\")\nInspection / compliance risk\nPrivacy exposure", "gov")
bullets(s, ["**Goal:** a secure, lightweight local tool that enforces validation, tracks a controlled review "
            "workflow, keeps an immutable audit trail, and lets staff query past reports and SOPs.",
            "**Hard boundary:** it must NEVER assess causality, recommend treatment, decide reportability or make "
            "any clinical / regulatory decision - those stay with qualified PV professionals.",
            "**Constraint:** fictional data only, local execution only (no cloud, no external APIs, no remote DB)."],
        0.6, 4.4, 12.1, 2.5, size=15)
notes(s, "Frame the pain in operational terms: incomplete records cause re-work; no audit trail is an inspection "
         "finding; ad-hoc text fields leak personal data. The tool is deliberately an intake/triage tracker, not a "
         "decision system.")

# ============================================================ 4 Solution overview
s = add_slide("Solution overview", "Objectives and key capabilities", "Overview")
caps = [
    ("Validated intake", "REF-YYYY-NNNN auto ids, AE vs PQC, conditional AE fields, LOT-\\d{5} regex, context-sensitive errors, PII shield", "ui"),
    ("Tracker dashboard", "Filter by status / type, row detail, status history, only legal actions offered", "ui"),
    ("Controlled lifecycle", "New -> In Review -> Closed; close needs HITL approval by a different reviewer", "life"),
    ("Immutable audit", "Append-only SQLite triggers + SHA-256 hash chain; IDs/enums only, no free text", "db"),
    ("Knowledge Agent", "Deterministic LangGraph agent: router, tools, ReAct trace, refusal of clinical questions", "cp"),
    ("4-stage hybrid RAG", "BM25 + bi-encoder -> RRF (k=60) -> cross-encoder >= 0.40 -> cited extractive answer or abstain", "rag"),
]
for i, (t, b, layer) in enumerate(caps):
    col, row = i % 3, i // 3
    card(s, 0.6 + col * 4.12, 1.65 + row * 1.75, 3.9, 1.55, t, b, layer, 15, 12)
bullets(s, ["**Objectives:** complete records first time · transparent workflow state · audit-ready by design · "
            "fast, trustworthy historical look-up · zero hallucination · zero personal data.",
            "**Design choice:** no LLM at all - every routing, validation and answer step is rule-based or "
            "extractive, so the same input always gives the same, explainable output."],
        0.6, 5.3, 12.1, 1.6, size=14)
notes(s, "Six capabilities map one-to-one to the specification. Explain the key decision: the spec demands "
         "deterministic, zero-hallucination processing and strictly local execution, so the agent is built with "
         "LangGraph for orchestration and LangChain for retrieval, but without a generative model.")

# ============================================================ 5 Process flow
s = add_slide("End-to-end process flow", "From a phone call to a closed, audited record - and back as searchable history",
              "Overview")
steps = [("1 Intake", "Form or chat\nkey=value", "ui"), ("2 Guard & route", "PII shield\nclinical filter\nrules R0-R6", "guard"),
         ("3 Validate", "auto-repair\nPydantic strict\nregex", "cp"), ("4 Persist", "REF id\nSQLite txn\n+ audit row", "db"),
         ("5 Review", "New ->\nIn Review", "life"), ("6 HITL close", "interrupt()\nreviewer\nApprove/Reject", "guard"),
         ("7 Closed", "terminal\naudit chain\nverified", "life")]
for i, (t, b, layer) in enumerate(steps):
    x = 0.45 + i * 1.83
    card(s, x, 1.75, 1.6, 1.75, t, b, layer, 13, 11)
    if i < len(steps) - 1:
        arrow(s, x + 1.6, 2.62, x + 1.83, 2.62)
card(s, 0.45, 4.05, 5.9, 1.55, "Invalid call path", "structured field errors -> user corrects\n"
     "same invalid call > 2 consecutive times -> circuit breaker OPEN -> halt", "guard", 13, 11.5)
card(s, 6.6, 4.05, 6.25, 1.55, "Knowledge path (historical / SOP question)", "BM25 top-50 ∥ bi-encoder top-50 -> RRF k=60 "
     "-> cross-encoder >= 0.40 -> top 3-5 -> extractive cited answer or abstain", "rag", 13, 11.5)
bullets(s, ["Every new report is indexed incrementally, so it is immediately retrievable as history.",
            "Every step appends to the ReAct trace (short-term memory) and every state change to the audit log "
            "(long-term memory)."], 0.45, 5.85, 12.4, 1.2, size=13, color=MUTED)
notes(s, "Walk left to right. Emphasise that the form, dashboard buttons and chat all enter the same LangGraph graph, "
         "so validation, breaker and audit can never be bypassed. Point out the two side paths: invalid input and "
         "knowledge queries.")

# ============================================================ 6 Architecture diagram
s = add_slide("Agent architecture", "Plan Mode output - generated before any code was written", "Architecture")
image(s, ROOT / "docs" / "architecture.png", 0.35, 1.5, 12.65, 5.5, border=False)
notes(s, "This diagram was the Plan Mode deliverable. Five lanes: Streamlit UI, LangGraph control plane with the "
         "five numbered control-plane steps, the hybrid RAG pipeline, SQLite persistence, and the governance strip. "
         "Right column: lifecycle and dual memory.")

# ============================================================ 7 Agents & responsibilities
s = add_slide("Agents (LangGraph nodes), responsibilities & interactions",
              "One StateGraph(AgentState) - each node is a single-responsibility deterministic agent step",
              "Architecture")
table(s, [["Node", "Control-plane step", "Responsibility", "Next"],
          ["input_guard", "Guardrail", "PII shield, clinical-scope filter, breaker-open check, audit refusals", "router"],
          ["router", "3 Semantic router", "Ordered regex rules R0-R6 -> DIRECT / RAG / INTAKE / STATUS / TOOL", "branch"],
          ["intake_tool / status_mgr", "Tool selection", "Extract arguments from chat (key=value, REF id + verb)", "tool_validator"],
          ["tool_validator", "1 Type-safe validation", "Auto-repair + strict Pydantic schema; failures -> breaker", "execute / breaker"],
          ["execute_tool", "Tool execution", "LangChain StructuredTool -> repository; detects HITL requirement", "hitl / respond"],
          ["circuit_breaker", "5 Circuit breaker", "Structured errors; > 2 identical invalid calls -> HALT", "finalize"],
          ["hitl_gate", "4 HITL gate", "interrupt() freezes state; Command(resume) -> decide_approval", "self / finalize"],
          ["rag_retrieve / rag_compose", "Hybrid RAG", "search_knowledge tool -> 4 stages -> extractive answer + audit", "finalize"],
          ["finalize", "2 Dual memory", "Append assistant message; state checkpointed (InMemorySaver)", "END"]],
      0.45, 1.6, 12.45, col_w=[2.6, 2.2, 5.85, 1.8], size=11, row_h=0.42)
caption(s, "Interactions: UI pages -> AgentService -> graph.invoke(thread_id) · Triage page -> Command(resume) on the frozen "
           "thread · tools -> Repository (only SQL writer) · new report -> incremental RAG index.", 0.45, 6.05, 12.4, 12)
notes(s, "There is one graph rather than several LLM agents: each node is a narrow agent step with one job. "
         "Short-term memory is the checkpointed AgentState per thread; long-term memory is SQLite.")

# ============================================================ 8 Hybrid RAG
s = add_slide("Multi-stage hybrid RAG - measured on the demo query",
              "\"any history of difficulty breathing with LOT-88392?\"  (real encoders, 36-chunk corpus)", "Architecture")
stages = [("S1 BM25", "BM25Retriever\nk1=1.3, b=0.75\nLOT-88392 kept whole\ntop-50", "rag"),
          ("S2 Bi-encoder", "bge-small-en-v1.5\n512/64-token chunks\nFAISS cosine\ntop-50", "rag"),
          ("S3 RRF", "Σ 1/(60 + rank)\nrank-only fusion\nno score scaling", "rag"),
          ("S4 Cross-encoder", "ms-marco-MiniLM-L-6\nsigmoid(logit)\nkeep >= 0.40, max 5", "rag"),
          ("Composer", "verbatim quotes\n+ citations\nor ABSTAIN", "life")]
for i, (t, b, layer) in enumerate(stages):
    x = 0.45 + i * 2.55
    card(s, x, 1.65, 2.3, 1.75, t, b, layer, 14, 11)
    if i < 4:
        arrow(s, x + 2.3, 2.5, x + 2.55, 2.5)
rows = [["Stage", "Candidates", "Top results (citation: score)"]]
for name, key in (("1 BM25", "bm25"), ("2 Bi-encoder (cosine)", "dense"), ("3 RRF k=60", "fused"),
                  ("4 Cross-encoder (sigmoid)", "reranked"), ("Final (>= 0.40, max 5)", "final")):
    rows.append([name, len(rag[key]), ",  ".join(f"{h['citation']}: {h['score']:.3f}" for h in rag[key][:3])])
table(s, rows, 0.45, 3.7, 12.45, col_w=[2.8, 1.4, 8.25], size=12, header_layer="rag", row_h=0.4)
caption(s, "BM25 found the exact lot; the bi-encoder surfaced REF-2026-0001 (\"shortness of breath\" - no shared keyword); "
           "the cross-encoder cut 36 candidates to 3. An off-topic query scores 0.00 everywhere -> abstain.",
        0.45, 6.25, 12.4, 12)
notes(s, "Explain why each stage exists: BM25 for identifiers, bi-encoder for synonyms, RRF to merge incomparable score "
         "scales, cross-encoder for precision plus an abstention threshold. Implementation detail worth mentioning: the "
         "cross-encoder returns raw logits (-11.3 for an unrelated pair), so a sigmoid was required for 0.40 to mean "
         "anything.")

# ============================================================ 9 Skills, subagents, hooks
s = add_slide("Skills, subagents & hooks", "How Claude Code governance features were used to build the system",
              "Technical highlights", "≈ 2 min block")
card(s, 0.45, 1.6, 4.05, 3.65, "Skill: pharma-intake-review",
     ".claude/skills/pharma-intake-review/SKILL.md\n4 checklists: data minimisation, error handling,\n"
     "auditability, test coverage\nFixed report format + severity rubric\n\nUsed twice:\n"
     "• Milestone D/E review -> 2 MAJOR + 1 MINOR fixed\n• Presentation phase (native Skill invocation)\n"
     "  -> 4 MINOR fixed\nEvidence: docs/reviews/*.md", "cp", 15, 11.5)
card(s, 4.65, 1.6, 4.05, 3.65, "Hook: PostToolUse audit",
     ".claude/settings.json -> matcher Edit|Write|...\n.claude/hooks/audit_file_edit.py (stdlib only)\n"
     "Logs ts, tool, repo path, hashed session,\nfile SHA-256 - never file content\nAlways exits 0 (never blocks)\n\n"
     f"{hook_events} real edit events recorded during the build\nlogs/claude_edit_audit.jsonl\n"
     "Tested: tests/integration/test_governance_hook.py", "gov", 15, 11.5)
card(s, 8.85, 1.6, 4.05, 3.65, "Subagents",
     "Development: no Claude Code subagents were spawned.\nThe workspace was empty (nothing to explore), and\n"
     "one agent with full context was cheaper and more\nconsistent than fanning out.\n\n"
     "Runtime: the 'agents' are LangGraph nodes - single-\nresponsibility steps (guard, router, validator,\n"
     "breaker, HITL gate, RAG) sharing one typed state.", "rag", 15, 11.5)
bullets(s, ["**CLAUDE.md** = always-on invariants (scope, architecture rules, conventions)  ·  **Skill** = on-demand "
            "procedure  ·  **Hook** = deterministic enforcement executed by the harness, not the model."],
        0.45, 5.5, 12.4, 1.2, size=14)
notes(s, "Be explicit and honest about subagents: none were used during development. The skill was created mid-session; "
         "the first review followed the SKILL.md procedure manually because the harness had not registered it yet; the "
         "second review used a native Skill invocation. The hook fired on every Edit/Write of the build.")

# ============================================================ 10 MCP & plugins
s = add_slide("MCP & plugin integration", "What is integrated - and why no MCP servers are used at runtime",
              "Technical highlights")
table(s, [["Integration", "Type", "Purpose", "Network at runtime?"],
          ["LangGraph (StateGraph, interrupt, Command, InMemorySaver)", "Library", "Agent orchestration, HITL, short-term memory", "No"],
          ["LangChain (BM25Retriever, StructuredTool, FAISS, HF embeddings & cross-encoder, splitters)", "Library", "Tools + retrieval", "No"],
          ["HuggingFace models (bge-small-en-v1.5, ms-marco-MiniLM-L-6-v2)", "Local model cache", "Dense retrieval, reranking", "No (one-time download, HF_HUB_OFFLINE=1)"],
          ["SQLite (WAL)", "Embedded DB", "Long-term memory, audit trail", "No"],
          ["Streamlit", "Local web server", "UI on localhost only (.streamlit/config.toml)", "No (telemetry off)"],
          ["Playwright + system Chrome", "Test tooling", "Automated screenshot evidence", "localhost only"],
          ["MCP servers", "-", "None used - spec requires strictly local, no external APIs", "-"]],
      0.45, 1.6, 12.45, col_w=[4.9, 1.7, 3.5, 2.35], size=11, header_layer="gov", row_h=0.5)
bullets(s, ["**Where MCP would fit next:** a read-only *audit-query MCP server* over SQLite (reviewers ask Claude about "
            "audit history without DB access); an *SOP-repository MCP server* to sync controlled documents into the "
            "RAG corpus; a connector to the enterprise PV system for case hand-off - all behind RBAC and audited."],
        0.45, 5.85, 12.4, 1.2, size=13)
notes(s, "Answer this directly: no MCP servers or plugins were used, by design - the specification forbids external "
         "APIs and cloud services. Integrations are local libraries and a local model cache. Then show where MCP adds "
         "value in a production version.")

# ============================================================ 11 Governance
s = add_slide("Governance framework", "Security, access control, guardrails - enforced in code, not by prompts",
              "Technical highlights")
gcards = [("Guardrails", "PII regex shield on every free-text field\nClinical-scope filter -> fixed refusal\n"
           "extra=\"forbid\" blocks unknown fields\nExtractive answers only; abstain < 0.40", "guard"),
          ("Access control", "Pseudonymous actors OP-xx / REV-xx\nOnly REV-xx may decide approvals\n"
           "Separation of duties: reviewer ≠ requester\nRepository refuses Closed without APPROVED", "cp"),
          ("Workflow control", "Lifecycle state machine (no skip/back)\nHITL interrupt freezes state\n"
           "One pending approval per report\nCircuit breaker > 2 identical invalid calls", "life"),
          ("Data & audit", "Audit = IDs/enums/field names only\nAppend-only triggers + SHA-256 chain\n"
           "Free-text detector refuses long audit strings\nRefusals logged as input hashes", "db"),
          ("Platform", "localhost binding, telemetry off\nHF_HUB_OFFLINE / local_files_only\n"
           "No secrets, no external calls\nSynthetic data only", "gov"),
          ("AI dev governance", "CLAUDE.md contract\nReview skill with BLOCKER rules\nPostToolUse hook audit log\n"
           "Plan Mode approval before code", "rag")]
for i, (t, b, layer) in enumerate(gcards):
    col, row = i % 3, i // 3
    card(s, 0.45 + col * 4.17, 1.6 + row * 2.6, 3.97, 2.4, t, b, layer, 15, 12)
notes(s, "Key message: every control is deterministic code with a test. Nothing relies on a model 'deciding' to behave. "
         "Mention the defense in depth on closure: graph interrupt + repository check + separation of duties.")

# ============================================================ 12 Observability
s = add_slide("Observability & traceability", "Every decision is explainable after the fact", "Technical highlights")
bullets(s, ["**Audit trail (SQLite):** REPORT_CREATED, STATUS_CHANGED, APPROVAL_REQUESTED / GRANTED / REJECTED, "
            "VALIDATION_FAILED, CIRCUIT_OPEN, RAG_QUERY, REQUEST_REFUSED - UTC, actor, ref, from->to, details.",
            "**Tamper evidence:** SHA-256 hash chain verified in the UI and by scripts/verify_audit_chain.py.",
            "**ReAct execution trace:** Thought -> Action -> Observation for every node of every turn (UI expander).",
            "**RAG pipeline inspector:** per-stage candidates, scores, threshold pass/fail and timings (ms).",
            "**Route explanations:** rule id + reason (e.g. R6_DEFAULT_RAG) shown with each answer.",
            "**Dev-time trace:** PostToolUse hook JSONL of every file edit with content hashes.",
            "**Debugging:** deterministic replay - same input, same route, same output; CSV export of audit."],
        0.45, 1.55, 6.3, 5.4, size=13, gap=6)
image(s, img_rag_ans, 6.95, 1.55, 6.0, 2.6)
image(s, img_audit, 6.95, 4.3, 6.0, 2.65)
notes(s, "Show that an auditor can reconstruct who did what and when, and an engineer can see why the agent routed a "
         "message the way it did, down to the stage scores of the retrieval.")

# ============================================================ 13 How to test
s = add_slide("How to test it", "Reproducible from a clean checkout", "Evaluation")
cmds = ("$ python -m venv .venv && .venv\\Scripts\\activate\n"
        "$ pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
        "$ pip install -r requirements.txt && pip install -e .\n"
        "$ python scripts/download_models.py      # one-time, then offline\n"
        "$ pytest -q --cov=pharma_tracker          # unit + integration + UI\n"
        "$ pytest -m models                        # real-encoder RAG tests\n"
        "$ python scripts/seed_demo.py --reset     # demo + docs/demo evidence\n"
        "$ python scripts/load_test.py             # performance results\n"
        "$ python scripts/verify_audit_chain.py    # 'chain OK'\n"
        "$ streamlit run app.py                    # http://localhost:8501")
tb = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.45), Inches(1.55), Inches(6.6), Inches(4.0))
tb.fill.solid()
tb.fill.fore_color.rgb = RGBColor(0x0F, 0x17, 0x2A)
tb.line.fill.background()
tf = tb.text_frame
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.TOP
for i, ln in enumerate(cmds.split("\n")):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.text = ln
    p.font.name, p.font.size, p.font.color.rgb = "Consolas", Pt(12), RGBColor(0x7D, 0xD3, 0xFC)
table(s, [["Layer", "What is verified"],
          ["Unit", "schemas & regex, PII/clinical guards, lifecycle, ref format, repair, breaker, router, RRF maths, tokenizer, threshold, composer"],
          ["Integration", "storage integrity & concurrency, append-only triggers, hash-chain tamper detection, HITL interrupt/resume, breaker halt, RAG end-to-end"],
          ["Real models", "synonym retrieval, exact-lot match, abstain, SOP question (@pytest.mark.models)"],
          ["UI (AppTest)", "all 6 pages render; form errors then success; agent query"],
          ["Governance", "hook registration, metadata-only log, never blocks"]],
      7.25, 1.55, 5.65, col_w=[1.35, 4.3], size=10.5, header_layer="life", row_h=0.62)
bullets(s, ["Manual walkthrough: submit an AE with a bad lot / no onset date -> fix -> move to In Review -> request "
            "closure (frozen) -> approve as REV-02 -> ask the Knowledge Agent -> check the Audit Trail."],
        0.45, 5.8, 12.4, 1.1, size=13)
notes(s, "Every test uses an isolated tmp_path database, never the demo DB. Fast tests use deterministic fake encoders; "
         "the @models tests use the real HuggingFace weights from the local cache.")

# ============================================================ 14 Evaluation results
s = add_slide("Evaluation results", "Testing methodology, metrics and outcomes", "Evaluation")
metric(s, 0.45, 1.55, 2.35, n_passed, "tests passed (0 failed)")
metric(s, 2.95, 1.55, 2.35, coverage, "line coverage")
metric(s, 5.45, 1.55, 2.35, "3 / 3", "real-encoder RAG tests")
metric(s, 7.95, 1.55, 2.35, "8 / 8", "UI page tests")
metric(s, 10.45, 1.55, 2.45, "OK", "audit chain after load", "db")
table(s, [["Capability (spec)", "Evaluation", "Result"],
          ["Mandatory-field validation", "Every core + AE field missing; 6 bad lot formats; future/onset dates", "Pass"],
          ["Circuit breaker", "2 invalid stay closed, 3rd trips; reset on success / new signature", "Pass"],
          ["HITL gate", "Frozen until decision; SoD; reject keeps In Review; restart path", "Pass"],
          ["Exact identifier recall", "LOT-88392 / LOT-10457 queries rank matching reports first", "Pass"],
          ["Semantic recall", "'trouble breathing' -> dyspnea report in dense top-5", "Pass"],
          ["Hallucination control", "Off-topic query abstains; quotes verbatim-checked", "Pass"],
          ["Clinical refusal", "6 causality / dosing / reportability phrasings refused", "Pass"]],
      0.45, 2.85, 7.6, col_w=[2.3, 4.5, 0.8], size=10.5, header_layer="life", row_h=0.5)
image(s, img_tests, 8.25, 2.85, 4.65, 4.1)
notes(s, "Methodology: specification-driven tests - every rule in the spec has at least one positive and one negative "
         "test. Retrieval quality is evaluated with targeted cases (identifier recall, synonym recall, abstention) "
         "rather than an LLM judge, which keeps the evaluation deterministic.")

# ============================================================ 15 Load testing
s = add_slide("Load testing results", f"scripts/load_test.py - {lt['environment']['cpu_count']} CPU cores, "
              f"{lt['environment']['rag_mode'].split('(')[0].strip()} encoders, isolated temp DB", "Evaluation")
image(s, P / "load_test_charts.png", 0.45, 1.45, 12.45, 3.3, border=False)
a = lt["A_sequential_intake"]
crag = lt["C_rag_sequential"]
rows = [["Scenario", "n", "p50 ms", "p95 ms", "throughput/s", "notes"],
        ["A  intake, sequential (full graph)", a["n"], a["p50_ms"], a["p95_ms"], a["throughput_per_s"], "includes audit + incremental indexing"]]
for b in lt["B_concurrent_intake"]:
    rows.append([f"B  intake, {b['threads']} threads", b["n"], b["p50_ms"], b["p95_ms"], b["throughput_per_s"],
                 f"errors {b['errors']}, unique refs {b['unique_refs']}"])
rows.append(["C  RAG query via agent", crag["n"], crag["p50_ms"], crag["p95_ms"], crag["throughput_per_s"],
             f"{crag['corpus_chunks']} chunks; rerank dominates"])
for d in lt["D_rag_concurrent"]:
    rows.append([f"D  RAG, {d['threads']} threads", d["n"], d["p50_ms"], d["p95_ms"], d["throughput_per_s"], "pipeline lock serialises"])
table(s, rows, 0.45, 4.85, 8.3, col_w=[2.75, 0.55, 0.85, 0.85, 1.1, 2.2], size=9, header_layer="ui", row_h=0.21)
e = lt["E_corpus_scaling"]
bullets(s, ["**Correctness under load:** 0 errors, all ref ids unique, audit chain intact.",
            "**Bottleneck:** cross-encoder rerank over the fused pool (CPU).",
            f"**Scaling:** {e[-1]['reports']} reports -> {e[-1]['chunks']} chunks, index build {e[-1]['index_build_s']} s, "
            f"query p50 {e[-1]['p50_ms']:.0f} ms.",
            "**Limits:** single-process SQLite writer; RAG lock serialises queries; volatile checkpointer.",
            "**Next:** cap/batch rerank pool, GPU or ONNX encoders, Postgres + persistent saver."],
        8.9, 4.8, 4.0, 2.2, size=10.5, gap=2)
notes(s, "Numbers come from the JSON written by the load test. Point out that concurrency does not raise intake "
         "throughput much because SQLite serialises writers (BEGIN IMMEDIATE) - which is exactly what guarantees unique "
         "reference ids and an unbroken hash chain. RAG latency is dominated by the cross-encoder.")

# ============================================================ 16 Deployment
s = add_slide("Deployment architecture", "Current: single-machine local deployment  ·  Target: hardened enterprise deployment",
              "Technical highlights")
card(s, 0.45, 1.55, 6.1, 4.0, "Current (capstone) - strictly local",
     "Windows / Python 3.12 virtualenv (.venv)\nstreamlit run app.py -> http://localhost:8501\n"
     ".streamlit/config.toml: address=localhost, telemetry off\nSQLite WAL file: data/db/pharma_tracker.db\n"
     "HF model cache (one-time download) + HF_HUB_OFFLINE=1\nIn-memory FAISS + BM25 index rebuilt at startup\n"
     "LangGraph InMemorySaver (volatile short-term memory)\n\nConfig via env vars:\n"
     "PHARMA_DB_PATH · PHARMA_RAG_MODE (auto|real|fallback)", "life", 16, 12.5)
card(s, 6.8, 1.55, 6.1, 4.0, "Target (production)",
     "Container image (pinned deps, model weights baked in, checksums)\nTLS reverse proxy + enterprise SSO / RBAC\n"
     "PostgreSQL (HA, backups) + LangGraph Postgres checkpointer\nWORM / externally anchored audit storage, SIEM feed\n"
     "Vector store service; GPU/ONNX inference for encoders\nSecrets manager, monitoring, alerting\n"
     "Validated release pipeline (CSV / IQ-OQ-PQ, change control)\nIntegration with the validated PV safety system", "gov", 16, 12.5)
bullets(s, ["Fallback mode keeps the app usable offline even without model weights (hash embeddings + keyword "
            "reranker) - visible in the sidebar as RAG mode."], 0.45, 5.8, 12.4, 1.0, size=13, color=MUTED)
notes(s, "The capstone deployment is intentionally a single local process. The right-hand side is the list of "
         "mandatory changes before production, which also answers defense question 5.")

# ============================================================ 17-22 Screenshots
s = add_slide("Results: validated intake", "Context-sensitive errors (left) -> auto-repaired successful submission (right)",
              "Live demo", "≈ 6 min block")
image(s, img_intake_err, 0.45, 1.5, 7.2, 5.5)
image(s, img_intake_ok, 7.85, 1.5, 5.05, 3.7)
bullets(s, ["Malformed lot, missing reporter, short description, AE fields missing - each explained in place.",
            "\"lot 55120\" auto-repaired to LOT-55120; REF id generated."], 7.85, 5.35, 5.05, 1.6, size=12)
notes(s, "Demo step 1 (about 1 min): submit an AE with LOT-883 and no onset date to show the inline errors, then switch "
         "to PQC and submit 'lot 55120' to show auto-repair and the generated reference id.")

s = add_slide("Results: dashboard & lifecycle", "Filterable tracker, status history, only legal actions offered", "Live demo")
image(s, img_dash, 0.45, 1.5, 7.3, 5.5)
image(s, img_dash_req, 7.95, 1.5, 4.95, 4.3)
bullets(s, ["New -> In Review recorded with actor + UTC time.", "Request closure -> HITL interrupt; record frozen."],
        7.95, 5.95, 4.95, 1.0, size=12)
notes(s, "Demo step 2 (about 1 min): select the new report, move it to In Review, then request closure and show that "
         "the dashboard now says the record is frozen pending approval.")

s = add_slide("Results: human-in-the-loop approval", "Paused LangGraph thread (hitl_gate) resumed by a different reviewer",
              "Live demo")
image(s, img_triage, 0.45, 1.5, 6.5, 5.5)
image(s, img_triage_ok, 7.1, 1.5, 5.8, 4.4)
bullets(s, ["Live interrupt vs. restart-safe direct path both shown.", "REV-02 approval -> Closed; decision history kept."],
        7.1, 6.0, 5.8, 1.0, size=12)
notes(s, "Demo step 3 (about 1 min): switch actor to REV-02, show the thread status line (paused at hitl_gate), enter a "
         "justification and approve. Mention that the requester cannot approve their own request.")

s = add_slide("Results: Knowledge Agent - hybrid RAG", "Cited extractive answer (left) and 4-stage pipeline inspector (right)",
              "Live demo")
image(s, img_rag_ans, 0.45, 1.5, 6.2, 5.5)
image(s, img_rag_insp, 6.8, 1.5, 6.1, 5.5)
notes(s, "Demo step 4 (about 1.5 min): ask the LOT-88392 breathing question, open the ReAct trace and the pipeline "
         "inspector, and walk through BM25 -> dense -> RRF -> rerank, highlighting which candidates passed 0.40.")

s = add_slide("Results: guardrails", "Clinical refusal · abstention · circuit breaker halt", "Live demo")
image(s, img_guard, 0.45, 1.5, 7.6, 5.5)
bullets(s, ["**Causality question** -> fixed refusal (R2_CLINICAL_SCOPE), audited as REQUEST_REFUSED.",
            "**Off-topic query** -> no candidate >= 0.40 -> abstain instead of guessing.",
            "**Same invalid command x3** -> attempts 1 and 2 return structured errors; the 3rd trips the circuit "
            "breaker and halts the session (CIRCUIT_OPEN audited).",
            "Reset session = new LangGraph thread."], 8.25, 1.6, 4.65, 5.3, size=13, gap=8)
notes(s, "Demo step 5 (about 1 min): run the three guardrail cases. This shows refusal, abstention and loop prevention.")

s = add_slide("Results: audit trail & governance log", "Hash chain verified, filterable events, hook log on the same page",
              "Live demo")
image(s, img_audit, 0.45, 1.5, 7.2, 5.5)
image(s, ROOT / "docs" / "presentation" / "crops" / "home.png", 7.85, 1.5, 5.05, 3.6)
bullets(s, ["Home: live metrics + chain status.", "CSV export for inspectors; `verify_audit_chain.py` -> chain OK.",
            f"{hook_events} PostToolUse edit events recorded."], 7.85, 5.25, 5.05, 1.7, size=12)
notes(s, "Demo step 6 (about 30 s): show the audit page - the events created during the demo appear at the top, the "
         "chain is intact, and the Claude Code hook log is listed below.")

# ============================================================ 23 Live demo script
s = add_slide("Live demo script (6 minutes)", "Run against a freshly seeded DB: python scripts/seed_demo.py --reset",
              "Live demo")
table(s, [["#", "Time", "Action", "What to point out"],
          ["1", "0:00-1:00", "New Report: AE with LOT-883, no onset -> errors; PQC 'lot 55120' -> submit", "context-sensitive errors, auto-repair, REF id"],
          ["2", "1:00-2:00", "Dashboard: filter, select row, Move to In Review, Request closure", "legal actions only, status history, frozen state"],
          ["3", "2:00-3:00", "Triage Approvals as REV-02: justification -> Approve", "interrupt/resume, separation of duties"],
          ["4", "3:00-4:30", "Knowledge Agent: 'any history of difficulty breathing with LOT-88392?'", "citations, ReAct trace, 4-stage inspector"],
          ["5", "4:30-5:30", "Ask causality question; off-topic query; invalid command x3", "refusal, abstention, circuit breaker"],
          ["6", "5:30-6:00", "Audit Trail page", "hash chain OK, all demo events, hook log"]],
      0.45, 1.6, 12.45, col_w=[0.45, 1.25, 6.0, 4.75], size=12, header_layer="ui", row_h=0.6)
bullets(s, ["Fallback plan: if anything fails live, the screenshots on slides 17-22 and docs/demo/walkthrough.md show "
            "the same flow end to end."], 0.45, 6.05, 12.4, 0.8, size=13, color=MUTED)
notes(s, "Keep a browser tab per page open in advance; act as OP-01 for steps 1-2 and 4-6, REV-02 for step 3.")

# ============================================================ 24 Business impact
s = add_slide("Business impact", "Expected value of moving intake from spreadsheets to a validated, audited workflow",
              "Technical highlights")
imp = [("Data quality", "Mandatory fields & formats enforced at entry -> no incomplete records reach review; "
        "fewer follow-up calls", "life"),
       ("Speed", f"Historical lot / symptom look-up in ~{crag['p50_ms'] / 1000:.1f} s instead of searching spreadsheets; "
        f"intake recorded in ~{a['p50_ms']:.0f} ms", "ui"),
       ("Compliance", "Tamper-evident audit trail, HITL closure with justification, separation of duties - "
        "inspection-ready evidence", "db"),
       ("Privacy", "PII shield and data minimisation by design; audit holds no free text", "guard"),
       ("Trust", "Zero hallucination: cited quotes or explicit 'nothing found'; clinical questions refused", "rag"),
       ("Cost", "No LLM runtime tokens, no cloud spend; runs on a standard laptop CPU", "gov")]
for i, (t, b, layer) in enumerate(imp):
    col, row = i % 3, i // 3
    card(s, 0.45 + col * 4.17, 1.6 + row * 2.0, 3.97, 1.8, t, b, layer, 16, 12.5)
bullets(s, ["Impact figures are expected, not measured in production - the prototype uses fictional data. Latencies "
            "are measured by scripts/load_test.py."], 0.45, 5.75, 12.4, 1.0, size=12, color=MUTED)
notes(s, "Translate features into value: first-time-right records, faster look-ups, inspection readiness, privacy and "
         "trust. Be clear these are expected benefits from a training prototype.")

# ============================================================ 25 Tokens
s = add_slide("Token utilization & optimization", "Runtime: zero LLM tokens  ·  Development: measured from the Claude Code "
              "session transcript", "Technical highlights")
metric(s, 0.45, 1.55, 2.95, "0", "LLM tokens per user request (runtime)", "life")
metric(s, 3.55, 1.55, 2.95, f"{tok['api_calls']}", "Claude API calls (build session)", "ui")
metric(s, 6.65, 1.55, 2.95, f"{tok['output_tokens'] / 1000:.0f}K", "output tokens generated", "cp")
metric(s, 9.75, 1.55, 3.15, f"{tok['cache_hit_pct']:.1f}%", "of input tokens served from prompt cache", "rag")
table(s, [["Token category (build session)", "Tokens", "Share of input"],
          ["Cache read (re-used context)", f"{tok['cache_read_input_tokens']:,}", f"{tok['cache_hit_pct']:.1f}%"],
          ["Cache creation (new context)", f"{tok['cache_creation_input_tokens']:,}",
           f"{100 * tok['cache_creation_input_tokens'] / tok['total_input']:.1f}%"],
          ["Uncached input", f"{tok['input_tokens']:,}", f"{100 * tok['input_tokens'] / tok['total_input']:.2f}%"],
          ["Output", f"{tok['output_tokens']:,}", "-"]],
      0.45, 2.85, 6.2, col_w=[3.2, 1.6, 1.4], size=12, header_layer="cp", row_h=0.42)
caption(s, f"Snapshot {tok['snapshot_utc']} · model {tok['model']} · {tok['tool_calls']} tool calls", 0.45, 5.0, 6.2, 10)
bullets(s, ["**Runtime design:** deterministic router, extractive answers and local encoders -> no per-query token "
            "cost, no rate limits, predictable latency.",
            "**Lean persistent context:** CLAUDE.md holds only invariants; checklists live in a skill loaded on demand.",
            "**Prompt caching:** long stable prefix (system + CLAUDE.md + code read once) reused across turns.",
            "**Targeted reads:** grep / offset reads instead of re-reading whole files; batched parallel tool calls.",
            "**Generate, then verify:** scripts produce evidence (screenshots, load test, demo) instead of the model "
            "describing it.",
            "**If an LLM were added:** route only RAG synthesis to it, cap context to the top-5 reranked chunks, "
            "and keep the router and validators deterministic."],
        6.85, 2.8, 6.05, 4.2, size=11.5, gap=5)
notes(s, "Numbers are aggregated from the session transcript's usage fields at the snapshot time. The cache-hit share "
         "shows that most input was re-used context, which is the main cost lever for agentic coding sessions.")

# ============================================================ 26 Highlights & challenges
s = add_slide("Technical highlights, challenges & outcomes", "What was hard, how it was solved", "Technical highlights")
table(s, [["Challenge", "Resolution", "Outcome"],
          ["0.40 threshold on a logit-scale cross-encoder", "Probe calibration -> sigmoid", "Meaningful threshold; abstain works"],
          ["512-token chunks vs 256-token MiniLM limit", "bge-small (512) + its own tokenizer for splitting", "No silent truncation"],
          ["BM25 splitting LOT-88392", "Custom pharma_tokenize keeps identifiers whole", "Exact lot recall"],
          ["HITL across Streamlit reruns / restarts", "interrupt() + approvals table + direct fallback", "Gate never bypassed"],
          ["Conditional AE field errors", "Field validators reading report_type", "Errors attach to the right field"],
          ["Audit privacy", "IDs-only payloads + free-text detector + REF-pattern filter", "No text in audit log"],
          ["Network exposure", "Streamlit bound to localhost, telemetry off", "Strictly local"]],
      0.45, 1.55, 12.45, col_w=[4.0, 4.9, 3.55], size=12, header_layer="guard", row_h=0.5)
bullets(s, ["Review skill found 2 MAJOR + 5 MINOR issues across two runs - all fixed or explicitly accepted, with regression tests."],
        0.45, 5.75, 12.4, 1.0, size=13)
notes(s, "Pick two or three of these for the 2-minute highlights block; the cross-encoder calibration and the HITL "
         "design are the most interesting to a technical panel.")

# ============================================================ 27 Q&A backup
s = add_slide("Q&A preparation - defense questions", "Short answers (full text in docs/reflection.md)", "Panel Q&A",
              "5 min")
qa = [("1 CLAUDE.md vs skills?", "Invariants always loaded vs. procedures loaded on demand - lean context, repeatable reviews."),
      ("2 Plan Mode value?", "Surfaced AE conditionals, lot tokenisation, logit threshold, encoder window, HITL guard before code."),
      ("3 Why hooks are deterministic?", "Harness-executed code with a fixed schema; the model cannot skip or alter them."),
      ("4 How RAG avoids hallucination?", "Lexical + semantic recall, rank fusion, cross-encoder precision, threshold abstain, extractive output."),
      ("5 Production readiness?", "SSO/RBAC, Part 11 e-signatures, CSV validation, Postgres, WORM audit, DLP, PV integration, pen-test.")]
for i, (q, a_) in enumerate(qa):
    card(s, 0.45, 1.55 + i * 1.05, 12.45, 0.92, q, a_, "cp", 14, 12.5)
notes(s, "Backup slide for the Q&A segment.")

# ============================================================ 28 Thanks
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = NAVY
bg.line.fill.background()
caption(s, "Thank you - questions?", 0.8, 2.6, 11, 40, WHITE, True)
caption(s, "Repository artefacts: CLAUDE.md · docs/plan.md · docs/architecture.png · .claude/skills · .claude/settings.json · "
           "tests/ · docs/demo · docs/reviews · docs/reflection.md", 0.8, 3.7, 11.8, 14, RGBColor(0xBF, 0xDB, 0xFE))
notes(s, "Close and invite questions.")

out = P / "Pharma_Safety_Intake_Capstone.pptx"
prs.save(out)
print("saved", out, "slides:", len(prs.slides))
