"""Reference identifier format REF-YYYY-NNNN (sequence allocation lives in persistence/repository.py)."""
from __future__ import annotations

import re

from .errors import RefIdOverflowError

REF_PATTERN = r"^REF-\d{4}-\d{4}$"
MAX_SEQ = 9999
_REF_RE = re.compile(r"^REF-(\d{4})-(\d{4})$")


def format_ref(year: int, seq: int) -> str:
    if not 1 <= seq <= MAX_SEQ:
        raise RefIdOverflowError(f"Reference sequence for {year} exhausted (max {MAX_SEQ}).")
    return f"REF-{year:04d}-{seq:04d}"


def parse_ref(ref_id: str) -> tuple[int, int]:
    m = _REF_RE.match(ref_id)
    if not m:
        raise ValueError(f"Not a reference id: {ref_id!r}")
    return int(m.group(1)), int(m.group(2))
