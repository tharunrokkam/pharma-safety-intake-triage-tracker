"""Deterministic guardrails: PII shield and non-clinical scope filter.

Both return category NAMES only - matched text is never echoed or stored.
"""
from __future__ import annotations

import re

_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "national ID / SSN-like number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "date of birth": re.compile(r"\b(d\.?o\.?b\.?|date of birth|born on|birth ?date)\b", re.I),
    "patient name": re.compile(r"\b(patient|subject)(?:'s)?\s+(full\s+)?name\b", re.I),
    "personal name with title": re.compile(r"\b(Mr|Mrs|Ms|Miss|Mx)\.?\s+[A-Z][a-z]+"),
    "medical record number": re.compile(r"\b(mrn|medical record( number)?|nhs number|patient id)\b", re.I),
    "street address": re.compile(r"\b\d{1,5}\s+\w+(\s\w+)?\s+(street|st\.|avenue|ave\.|road|rd\.|lane)\b", re.I),
}
_PHONE_CANDIDATE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")


def find_pii(text: str | None) -> list[str]:
    """Return the PII categories detected in ``text`` (empty list when clean)."""
    if not text:
        return []
    hits = [name for name, pat in _PII_PATTERNS.items() if pat.search(text)]
    for m in _PHONE_CANDIDATE.finditer(text):
        if sum(ch.isdigit() for ch in m.group()) >= 10:
            hits.append("phone number")
            break
    return hits


_CLINICAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("causality assessment", re.compile(
        r"\b(caus(e|ed|es|ing|al|ality)|related to (the )?(drug|product|medication|medicine)|"
        r"due to (the )?(drug|product|medication|medicine)|attribut\w+ to)\b", re.I)),
    ("treatment or dosing advice", re.compile(
        r"\b(treat|treatment|therapy|antidote|dose|dosage|dosing|prescri\w*|diagnos\w*|"
        r"stop (taking|the (drug|medication|product))|medical advice|"
        r"should (i|we|he|she|they|the patient) (take|stop|continue|use))\b", re.I)),
    ("regulatory reportability decision", re.compile(
        r"\b(reportab\w*|expedited|15[- ]day|report(ed|ing)? (it )?to (the )?"
        r"(fda|ema|mhra|regulator\w*|authorit\w*|health authorit\w*))\b", re.I)),
]


def find_clinical_scope_violation(text: str | None) -> str | None:
    """Return the out-of-scope category for clinical/regulatory decision requests, else None."""
    if not text:
        return None
    for name, pat in _CLINICAL_PATTERNS:
        if pat.search(text):
            return name
    return None


REFUSAL_TEMPLATE = (
    "I can't help with {category}. This training tool only captures, tracks and retrieves fictional "
    "intake records. It never assesses causality, recommends treatment, determines regulatory "
    "reportability or makes clinical/regulatory decisions. Please route this question to a qualified "
    "pharmacovigilance professional through your enterprise PV system."
)

PII_BLOCK_TEMPLATE = (
    "Your message appears to contain personal identifiers ({categories}). This system accepts "
    "synthetic data only - please remove personal details and try again."
)
