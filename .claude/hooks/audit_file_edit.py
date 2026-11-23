"""PostToolUse governance hook: record file-edit events to a local JSONL audit log.

Deterministic, stdlib-only, never blocks (always exits 0).
Logs METADATA ONLY: timestamp, tool name, repo-relative path, hashed session id, SHA-256 of the file
after the edit. It deliberately never records tool_input content / old_string / new_string or any
report description text.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def build_record(payload: dict, project_dir: Path) -> dict | None:
    tool = payload.get("tool_name", "")
    if tool not in EDIT_TOOLS:
        return None
    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    path = Path(raw_path)
    try:
        rel = path.resolve().relative_to(project_dir.resolve()).as_posix()
    except (ValueError, OSError):
        rel = "<outside-project>"
    session = str(payload.get("session_id", ""))
    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": "file_edit",
        "hook": payload.get("hook_event_name", "PostToolUse"),
        "tool_name": tool,
        "file_path": rel,
        "session_id_sha256": hashlib.sha256(session.encode()).hexdigest()[:12],
        "file_sha256_after": _sha256_file(path) if rel != "<outside-project>" else None,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path.cwd())
        record = build_record(payload, project_dir)
        if record is None:
            return 0
        log = project_dir / "logs" / "claude_edit_audit.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:  # noqa: BLE001 - a governance logger must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
