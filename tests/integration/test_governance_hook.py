"""Governance hook: deterministic, metadata-only JSONL record; settings registration present."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "audit_file_edit.py"


def run_hook(payload: dict, project: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
                          capture_output=True, env=env, timeout=30)


def test_settings_registers_post_tool_use_hook():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entry = settings["hooks"]["PostToolUse"][0]
    assert "Edit" in entry["matcher"] and "Write" in entry["matcher"]
    assert "audit_file_edit.py" in entry["hooks"][0]["command"]


def test_hook_logs_metadata_only(tmp_path):
    target = tmp_path / "src" / "x.py"
    target.parent.mkdir()
    target.write_text("print('hello')", encoding="utf-8")
    secret = "Reporter described difficulty breathing SECRET-DESCRIPTION"
    proc = run_hook({"session_id": "s1", "hook_event_name": "PostToolUse", "tool_name": "Edit",
                     "tool_input": {"file_path": str(target), "old_string": secret, "new_string": secret,
                                    "content": secret}}, tmp_path)
    assert proc.returncode == 0
    log = (tmp_path / "logs" / "claude_edit_audit.jsonl").read_text(encoding="utf-8")
    rec = json.loads(log.strip())
    assert rec["file_path"] == "src/x.py" and rec["tool_name"] == "Edit" and rec["event"] == "file_edit"
    assert len(rec["file_sha256_after"]) == 64
    assert "SECRET" not in log and "breathing" not in log and "s1" != rec["session_id_sha256"]
    assert set(rec) == {"ts_utc", "event", "hook", "tool_name", "file_path", "session_id_sha256", "file_sha256_after"}


def test_hook_ignores_non_edit_tools_and_bad_input(tmp_path):
    assert run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}, tmp_path).returncode == 0
    assert not (tmp_path / "logs").exists()
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    proc = subprocess.run([sys.executable, str(HOOK)], input="not json", text=True, capture_output=True, env=env)
    assert proc.returncode == 0  # never blocks the session
