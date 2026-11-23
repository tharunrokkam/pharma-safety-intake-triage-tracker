"""Append-only, SHA-256 hash-chained audit trail.

Payloads contain IDs, enums, field names and outcomes only - never report free text.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from ..domain.errors import AuditPayloadError
from .db import utc_now

GENESIS_HASH = "0" * 64
MAX_DETAIL_STR = 80  # safety net: long strings are almost certainly free text


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _check_details(details: dict[str, Any]) -> None:
    def walk(v: Any, path: str) -> None:
        if isinstance(v, str) and len(v) > MAX_DETAIL_STR:
            raise AuditPayloadError(f"Audit detail '{path}' looks like free text; refusing to log it.")
        if isinstance(v, dict):
            for k, sub in v.items():
                walk(sub, f"{path}.{k}")
        elif isinstance(v, (list, tuple)):
            for i, sub in enumerate(v):
                walk(sub, f"{path}[{i}]")

    walk(details, "details")


def compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical(payload)).encode("utf-8")).hexdigest()


def append(
    conn: sqlite3.Connection,
    *,
    actor_id: str,
    action: str,
    ref_id: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    """Append one audit row. Call inside an open transaction so it commits with the change it records."""
    details = details or {}
    _check_details(details)
    row = conn.execute("SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = row["row_hash"] if row else GENESIS_HASH
    payload = {
        "ts_utc": utc_now(),
        "actor_id": actor_id,
        "action": str(action),
        "ref_id": ref_id,
        "from_status": from_status,
        "to_status": to_status,
        "details": details,
    }
    row_hash = compute_hash(prev_hash, payload)
    cur = conn.execute(
        "INSERT INTO audit_log (ts_utc, actor_id, action, ref_id, from_status, to_status, details_json,"
        " prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?,?)",
        (payload["ts_utc"], actor_id, payload["action"], ref_id, from_status, to_status,
         canonical(details), prev_hash, row_hash),
    )
    return int(cur.lastrowid)


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    checked: int
    first_bad_id: int | None = None
    reason: str = ""


def verify_chain(conn: sqlite3.Connection) -> ChainReport:
    prev = GENESIS_HASH
    n = 0
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        n += 1
        if r["prev_hash"] != prev:
            return ChainReport(False, n, r["id"], "prev_hash does not match previous row_hash")
        payload = {
            "ts_utc": r["ts_utc"],
            "actor_id": r["actor_id"],
            "action": r["action"],
            "ref_id": r["ref_id"],
            "from_status": r["from_status"],
            "to_status": r["to_status"],
            "details": json.loads(r["details_json"]),
        }
        if compute_hash(prev, payload) != r["row_hash"]:
            return ChainReport(False, n, r["id"], "row content does not match its hash")
        prev = r["row_hash"]
    return ChainReport(True, n)
