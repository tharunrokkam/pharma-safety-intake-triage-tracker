"""Repository: the only module that issues SQL against domain tables.

Every mutating method runs in one BEGIN IMMEDIATE transaction together with its audit row.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..domain import lifecycle
from ..domain.enums import ApprovalStatus, AuditAction, ReportType, Status
from ..domain.errors import (
    ApprovalRequiredError,
    ApprovalStateError,
    NotFoundError,
    SeparationOfDutiesError,
)
from ..domain.refgen import MAX_SEQ, format_ref
from ..domain.schemas import IntakeReportIn
from . import audit
from .db import connect, transaction, utc_now

_CORE_FIELDS = ["report_type", "product_name", "batch_id", "date_received", "reporter_type", "description"]


class Repository:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        connect(self.db_path).close()  # ensure schema exists

    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    # ------------------------------------------------------------------ reference ids
    @staticmethod
    def _next_ref_id(conn: sqlite3.Connection, year: int) -> str:
        row = conn.execute("SELECT last_seq FROM ref_counters WHERE year = ?", (year,)).fetchone()
        seq = (row["last_seq"] if row else 0) + 1
        ref = format_ref(year, seq)  # raises RefIdOverflowError beyond 9999
        conn.execute(
            "INSERT INTO ref_counters(year, last_seq) VALUES (?, ?) "
            "ON CONFLICT(year) DO UPDATE SET last_seq = excluded.last_seq",
            (year, seq),
        )
        return ref

    # ------------------------------------------------------------------ reports
    def create_report(self, report: IntakeReportIn, actor_id: str, *, year: int | None = None) -> str:
        year = year or datetime.now(timezone.utc).year
        now = utc_now()
        conn = self._conn()
        try:
            with transaction(conn):
                ref_id = self._next_ref_id(conn, year)
                conn.execute(
                    "INSERT INTO reports (ref_id, report_type, product_name, batch_id, date_received,"
                    " reporter_type, description, status, created_by, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (ref_id, str(report.report_type), report.product_name, report.batch_id,
                     report.date_received.isoformat(), str(report.reporter_type), report.description,
                     str(Status.NEW), actor_id, now, now),
                )
                captured = list(_CORE_FIELDS)
                if report.report_type == ReportType.SUSPECTED_ADVERSE_EVENT:
                    conn.execute(
                        "INSERT INTO ae_details (ref_id, event_description, event_onset_date) VALUES (?,?,?)",
                        (ref_id, report.event_description, report.event_onset_date.isoformat()),  # type: ignore[union-attr]
                    )
                    captured += ["event_description", "event_onset_date"]
                conn.execute(
                    "INSERT INTO status_transitions (ref_id, from_status, to_status, actor_id, ts_utc)"
                    " VALUES (?,?,?,?,?)",
                    (ref_id, None, str(Status.NEW), actor_id, now),
                )
                audit.append(
                    conn, actor_id=actor_id, action=AuditAction.REPORT_CREATED, ref_id=ref_id,
                    to_status=str(Status.NEW),
                    details={"report_type": str(report.report_type), "batch_id": report.batch_id,
                             "fields_captured": captured},
                )
            return ref_id
        finally:
            conn.close()

    def get_report(self, ref_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT r.*, a.event_description, a.event_onset_date FROM reports r"
                " LEFT JOIN ae_details a ON a.ref_id = r.ref_id WHERE r.ref_id = ?",
                (ref_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def require_report(self, ref_id: str) -> dict[str, Any]:
        rep = self.get_report(ref_id)
        if rep is None:
            raise NotFoundError(f"No report found with reference {ref_id}.")
        return rep

    def list_reports(
        self,
        statuses: Iterable[str] | None = None,
        report_types: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        sql = ("SELECT r.*, a.event_description, a.event_onset_date FROM reports r"
               " LEFT JOIN ae_details a ON a.ref_id = r.ref_id WHERE 1=1")
        params: list[Any] = []
        for col, values in (("r.status", statuses), ("r.report_type", report_types)):
            vals = [str(v) for v in values] if values else []
            if vals:
                sql += f" AND {col} IN ({','.join('?' * len(vals))})"
                params += vals
        sql += " ORDER BY r.ref_id"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params)]
        finally:
            conn.close()

    def count_by(self, column: str) -> dict[str, int]:
        if column not in ("status", "report_type"):
            raise ValueError(column)
        conn = self._conn()
        try:
            return {r[0]: r[1] for r in conn.execute(f"SELECT {column}, COUNT(*) FROM reports GROUP BY {column}")}
        finally:
            conn.close()

    # ------------------------------------------------------------------ lifecycle
    @staticmethod
    def _apply_transition(conn: sqlite3.Connection, ref_id: str, target: Status, actor_id: str,
                          approval_id: int | None) -> tuple[str, str]:
        row = conn.execute("SELECT status FROM reports WHERE ref_id = ?", (ref_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"No report found with reference {ref_id}.")
        current = Status(row["status"])
        lifecycle.validate_transition(current, target)
        if lifecycle.requires_hitl(current, target):
            # Defense in depth: closing requires an APPROVED approval for this report.
            ok = approval_id is not None and conn.execute(
                "SELECT 1 FROM approvals WHERE id = ? AND ref_id = ? AND status = 'APPROVED'",
                (approval_id, ref_id),
            ).fetchone()
            if not ok:
                raise ApprovalRequiredError(
                    f"Closing {ref_id} requires an approved human-in-the-loop compliance review."
                )
        now = utc_now()
        conn.execute("UPDATE reports SET status = ?, updated_at = ? WHERE ref_id = ?", (str(target), now, ref_id))
        conn.execute(
            "INSERT INTO status_transitions (ref_id, from_status, to_status, actor_id, approval_id, ts_utc)"
            " VALUES (?,?,?,?,?,?)",
            (ref_id, str(current), str(target), actor_id, approval_id, now),
        )
        audit.append(conn, actor_id=actor_id, action=AuditAction.STATUS_CHANGED, ref_id=ref_id,
                     from_status=str(current), to_status=str(target),
                     details={"approval_id": approval_id} if approval_id else {})
        return str(current), str(target)

    def transition_status(self, ref_id: str, target: Status | str, actor_id: str,
                          approval_id: int | None = None) -> dict[str, str]:
        conn = self._conn()
        try:
            with transaction(conn):
                prev, new = self._apply_transition(conn, ref_id, Status(target), actor_id, approval_id)
            return {"ref_id": ref_id, "from_status": prev, "status": new}
        finally:
            conn.close()

    def list_transitions(self, ref_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM status_transitions WHERE ref_id = ? ORDER BY id", (ref_id,))]
        finally:
            conn.close()

    # ------------------------------------------------------------------ HITL approvals
    def request_closure(self, ref_id: str, requested_by: str, thread_id: str | None = None) -> int:
        conn = self._conn()
        try:
            with transaction(conn):
                row = conn.execute("SELECT status FROM reports WHERE ref_id = ?", (ref_id,)).fetchone()
                if row is None:
                    raise NotFoundError(f"No report found with reference {ref_id}.")
                lifecycle.validate_transition(row["status"], Status.CLOSED)
                if conn.execute("SELECT 1 FROM approvals WHERE ref_id = ? AND status = 'PENDING'",
                                (ref_id,)).fetchone():
                    raise ApprovalStateError(f"A closure approval for {ref_id} is already pending.")
                cur = conn.execute(
                    "INSERT INTO approvals (ref_id, requested_by, requested_at, status, thread_id)"
                    " VALUES (?,?,?,?,?)",
                    (ref_id, requested_by, utc_now(), str(ApprovalStatus.PENDING), thread_id),
                )
                approval_id = int(cur.lastrowid)
                audit.append(conn, actor_id=requested_by, action=AuditAction.APPROVAL_REQUESTED, ref_id=ref_id,
                             from_status=str(Status.IN_REVIEW), to_status=str(Status.CLOSED),
                             details={"approval_id": approval_id, "gate": "HITL"})
            return approval_id
        finally:
            conn.close()

    def set_approval_thread(self, approval_id: int, thread_id: str) -> None:
        conn = self._conn()
        try:
            with transaction(conn):
                conn.execute("UPDATE approvals SET thread_id = ? WHERE id = ? AND status = 'PENDING'",
                             (thread_id, approval_id))
        finally:
            conn.close()

    def get_approval(self, approval_id: int) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = ("SELECT ap.*, r.report_type, r.product_name, r.batch_id FROM approvals ap"
               " JOIN reports r ON r.ref_id = ap.ref_id")
        params: list[Any] = []
        if status:
            sql += " WHERE ap.status = ?"
            params.append(str(status))
        sql += " ORDER BY ap.id"
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params)]
        finally:
            conn.close()

    def decide_approval(self, approval_id: int, reviewer_id: str, decision: str,
                        justification: str) -> dict[str, Any]:
        """Record the human decision; on approval commit In Review -> Closed atomically."""
        conn = self._conn()
        try:
            with transaction(conn):
                ap = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
                if ap is None:
                    raise NotFoundError(f"No approval request with id {approval_id}.")
                if ap["status"] != ApprovalStatus.PENDING:
                    raise ApprovalStateError(f"Approval {approval_id} was already decided ({ap['status']}).")
                if reviewer_id == ap["requested_by"]:
                    raise SeparationOfDutiesError(
                        "Separation of duties: the reviewer must be a different person from the requester."
                    )
                new_status = ApprovalStatus.APPROVED if decision == "approve" else ApprovalStatus.REJECTED
                conn.execute(
                    "UPDATE approvals SET status = ?, reviewer_id = ?, justification = ?, decided_at = ?"
                    " WHERE id = ?",
                    (str(new_status), reviewer_id, justification, utc_now(), approval_id),
                )
                action = (AuditAction.APPROVAL_GRANTED if new_status == ApprovalStatus.APPROVED
                          else AuditAction.APPROVAL_REJECTED)
                audit.append(conn, actor_id=reviewer_id, action=action, ref_id=ap["ref_id"],
                             details={"approval_id": approval_id, "requested_by": ap["requested_by"],
                                      "justification_recorded": True})
                if new_status == ApprovalStatus.APPROVED:
                    self._apply_transition(conn, ap["ref_id"], Status.CLOSED, reviewer_id, approval_id)
                status_row = conn.execute("SELECT status FROM reports WHERE ref_id = ?", (ap["ref_id"],)).fetchone()
            return {"approval_id": approval_id, "ref_id": ap["ref_id"], "decision": str(new_status),
                    "status": status_row["status"]}
        finally:
            conn.close()

    # ------------------------------------------------------------------ audit access
    def record_event(self, actor_id: str, action: AuditAction | str, *, ref_id: str | None = None,
                     details: dict[str, Any] | None = None) -> int:
        conn = self._conn()
        try:
            with transaction(conn):
                return audit.append(conn, actor_id=actor_id, action=action, ref_id=ref_id, details=details)
        finally:
            conn.close()

    def list_audit(self, ref_id: str | None = None, actions: Iterable[str] | None = None,
                   limit: int = 1000) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM audit_log WHERE 1=1", []
        if ref_id:
            sql += " AND ref_id = ?"
            params.append(ref_id)
        acts = [str(a) for a in actions] if actions else []
        if acts:
            sql += f" AND action IN ({','.join('?' * len(acts))})"
            params += acts
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params)]
        finally:
            conn.close()

    def verify_audit_chain(self) -> audit.ChainReport:
        conn = self._conn()
        try:
            return audit.verify_chain(conn)
        finally:
            conn.close()


__all__ = ["Repository", "MAX_SEQ"]
