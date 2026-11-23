"""Verify the SHA-256 hash chain of the audit log.  Exit code 1 if broken.

Usage: python scripts/verify_audit_chain.py [path/to/db]
"""
from __future__ import annotations

import sys
from pathlib import Path

from pharma_tracker.config import db_path
from pharma_tracker.persistence.repository import Repository


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else db_path()
    report = Repository(path).verify_audit_chain()
    if report.ok:
        print(f"chain OK - {report.checked} audit events verified ({path.name})")
        return 0
    print(f"chain BROKEN at row {report.first_bad_id}: {report.reason} (checked {report.checked})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
