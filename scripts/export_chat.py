"""Export a Claude Code session transcript (JSONL) to a readable Markdown file.

Usage: python scripts/export_chat.py [transcript.jsonl] [out.md]
Defaults: newest transcript for this project -> docs/chat_history.md

Included: every user message, every assistant reply, every tool call (with full input) and tool result.
Long tool inputs/results are kept in full but folded inside <details> blocks. Images are shown as placeholders.
Not included: the model's private reasoning blocks and harness <system-reminder> boilerplate.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path.home() / ".claude" / "projects" / "c--Users-vmadmin-Downloads-pharmaCapstone"
SYS_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
IDE_RE = re.compile(r"<ide_opened_file>.*?</ide_opened_file>|<ide_selection>.*?</ide_selection>", re.S)
REJECT_RE = re.compile(r"The user provided the following reason for the rejection:\s*(.*)", re.S)
HARNESS_PREFIXES = ("[Image:", "<task-notification>", "Base directory for this skill")
FOLD_AT = 1500


def fence(text: str, lang: str = "") -> str:
    ticks = "````" if "```" in text else "```"
    return f"{ticks}{lang}\n{text.rstrip()}\n{ticks}"


def folded(summary: str, body: str, lang: str = "") -> str:
    if len(body) <= FOLD_AT:
        return f"**{summary}**\n\n{fence(body, lang)}\n"
    return f"<details><summary><b>{summary}</b> ({len(body):,} chars)</summary>\n\n{fence(body, lang)}\n\n</details>\n"


def ts(d: dict) -> str:
    t = d.get("timestamp")
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:  # noqa: BLE001
        return ""


def tool_input_text(name: str, inp: dict) -> tuple[str, str]:
    if name == "Bash":
        return inp.get("command", ""), "bash"
    if name == "Write":
        lang = Path(inp.get("file_path", "")).suffix.lstrip(".")
        return f"# file: {inp.get('file_path')}\n{inp.get('content', '')}", {"py": "python", "md": "markdown"}.get(lang, lang)
    if name == "Edit":
        return (f"# file: {inp.get('file_path')}\n# --- old\n{inp.get('old_string', '')}\n# --- new\n"
                f"{inp.get('new_string', '')}"), ""
    return json.dumps(inp, indent=2, ensure_ascii=False), "json"


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for c in content or []:
        if isinstance(c, dict):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif c.get("type") == "image":
                parts.append("[image]")
    return "\n".join(parts)


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else max(PROJECT_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "chat_history.md"
    entries = []
    for line in src.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    md = [f"# Claude Code session history - Pharma Safety Intake & Triage Tracker\n",
          f"- Source transcript: `{src.name}`",
          f"- Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          "- Contents: all user messages, assistant replies, tool calls and tool results (long ones folded).",
          "- Omitted: model-internal reasoning blocks and harness `<system-reminder>` boilerplate; images shown as `[image]`.\n",
          "---\n"]
    seen_parts: set[str] = set()
    turn = 0
    for d in entries:
        kind = d.get("type")
        msg = d.get("message") or {}
        content = msg.get("content")
        if kind == "user":
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            for c in content or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text":
                    text = IDE_RE.sub("", SYS_RE.sub("", c.get("text", ""))).strip()
                    if not text or text.startswith("<command-") or text.startswith("Caveat:"):
                        continue
                    if text.startswith(HARNESS_PREFIXES):
                        md.append(folded("⚙️ Harness / system note (not typed by the user)", text))
                        continue
                    turn += 1
                    md.append(f"## 👤 User - message {turn}  \n<sub>{ts(d)}</sub>\n")
                    md.append(text + "\n")
                elif c.get("type") == "tool_result":
                    body = SYS_RE.sub("", result_text(c.get("content"))).strip() or "(no output)"
                    if body.startswith("Your questions have been answered"):
                        md.append(f"## 👤 User - answer to Claude's question  \n<sub>{ts(d)}</sub>\n")
                        md.append(body.split("You can now continue")[0].strip() + "\n")
                        continue
                    m = REJECT_RE.search(body)
                    if m:
                        turn += 1
                        md.append(f"## 👤 User - message {turn} (feedback given when rejecting the plan)  \n"
                                  f"<sub>{ts(d)}</sub>\n")
                        md.append(m.group(1).strip() + "\n")
                        continue
                    label = "Tool result (error)" if c.get("is_error") else "Tool result"
                    md.append(folded(label, body))
        elif kind == "assistant":
            for c in content or []:
                if not isinstance(c, dict):
                    continue
                key = f"{msg.get('id')}:{c.get('type')}:{c.get('id', '')}:{hash(c.get('text', ''))}"
                if key in seen_parts:
                    continue
                seen_parts.add(key)
                if c.get("type") == "text" and c.get("text", "").strip():
                    md.append(f"### 🤖 Claude  \n<sub>{ts(d)}</sub>\n")
                    md.append(c["text"].strip() + "\n")
                elif c.get("type") == "tool_use":
                    name = c.get("name", "?")
                    inp = c.get("input") or {}
                    desc = inp.get("description") or inp.get("file_path") or inp.get("pattern") or ""
                    body, lang = tool_input_text(name, inp)
                    md.append(folded(f"🔧 {name}" + (f" - {desc}" if desc else ""), body, lang))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB, {turn} user messages)")


if __name__ == "__main__":
    main()
