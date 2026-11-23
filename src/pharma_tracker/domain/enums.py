from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """str-valued Enum (works on Python 3.10, where enum.StrEnum is unavailable)."""

    def __str__(self) -> str:
        return str(self.value)


class ReportType(StrEnum):
    SUSPECTED_ADVERSE_EVENT = "Suspected Adverse Event"
    PRODUCT_QUALITY_COMPLAINT = "Product Quality Complaint"


class Status(StrEnum):
    NEW = "New"
    IN_REVIEW = "In Review"
    CLOSED = "Closed"


class ReporterType(StrEnum):
    HEALTHCARE_PROFESSIONAL = "Healthcare Professional"
    PHARMACIST = "Pharmacist"
    CONSUMER = "Consumer"
    SALES_REPRESENTATIVE = "Sales Representative"
    OTHER = "Other"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AuditAction(StrEnum):
    REPORT_CREATED = "REPORT_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    RAG_QUERY = "RAG_QUERY"
    REQUEST_REFUSED = "REQUEST_REFUSED"
