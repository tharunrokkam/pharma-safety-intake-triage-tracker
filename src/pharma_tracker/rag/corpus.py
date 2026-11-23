"""Corpus loading: synthetic SOP markdown files + saved intake reports -> LangChain Documents."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

_H1 = re.compile(r"^#\s+(.+)$", re.M)
_SECTION = re.compile(r"^##\s+(.+)$", re.M)


def load_sop_documents(sop_dir: Path) -> list[Document]:
    """One Document per '##' section of each SOP file, so citations can point at sections."""
    docs: list[Document] = []
    for path in sorted(Path(sop_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        sop_id = path.stem.split("_")[0].upper()  # e.g. "sop-01_ae_intake.md" -> "SOP-01"
        title_m = _H1.search(text)
        title = title_m.group(1).strip() if title_m else path.stem
        parts = _SECTION.split(text)
        # parts = [preamble, sec1_title, sec1_body, sec2_title, sec2_body, ...]
        preamble = _H1.sub("", parts[0]).strip()
        if preamble:
            docs.append(Document(page_content=f"{title}\n{preamble}", metadata={
                "source": "sop", "doc_id": sop_id, "title": title, "section": "Overview",
                "citation": f"{sop_id} Overview"}))
        for i in range(1, len(parts), 2):
            sec_title, body = parts[i].strip(), parts[i + 1].strip()
            sec_no = sec_title.split(" ")[0].rstrip(".") if sec_title[:1].isdigit() else sec_title
            docs.append(Document(page_content=f"{title} - {sec_title}\n{body}", metadata={
                "source": "sop", "doc_id": sop_id, "title": title, "section": sec_title,
                "citation": f"{sop_id} §{sec_no}"}))
    return docs


def report_to_document(report: dict[str, Any]) -> Document:
    """Render a stored report as retrievable text. Status is kept in metadata only (it changes)."""
    lines = [
        f"Reference {report['ref_id']} - {report['report_type']}",
        f"Product: {report['product_name']} | Batch/Lot: {report['batch_id']} | "
        f"Received: {report['date_received']} | Reporter: {report['reporter_type']}",
        f"Description: {report['description']}",
    ]
    if report.get("event_description"):
        lines.append(f"Event: {report['event_description']} (onset {report.get('event_onset_date')})")
    return Document(page_content="\n".join(lines), metadata={
        "source": "report", "doc_id": report["ref_id"], "ref_id": report["ref_id"],
        "report_type": report["report_type"], "batch_id": report["batch_id"],
        "product_name": report["product_name"], "citation": report["ref_id"]})
