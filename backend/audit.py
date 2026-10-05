"""Append-only audit trail: output/audit_trail.json.

The file is one JSON array. Every agent loop step (prompt in, model response with tool
calls, tool results going back, final output) and every ticket start/end, delegation and
human decision is appended as one record, written to disk immediately, so a crash mid-run
still leaves the steps before it. Existing records are never removed. If the file is
unreadable it is moved aside (audit_trail.corrupt-<time>.json), never deleted.

No secrets go in: the API key is never part of a message, and tool arguments/results are
shop data from the working database (test data only).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from config import HW5_DIR

AUDIT_PATH = HW5_DIR / "output" / "audit_trail.json"
MAX_TEXT = 4000  # long tool results / prompts are cut here to keep the file readable

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + f"… [cut, {len(text)} chars]"


def append(record: dict) -> None:
    """Append one record to the audit array (thread-safe, atomic replace)."""
    record = {"time": _now(), **record}
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        records: list = []
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size:
            try:
                records = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                if not isinstance(records, list):
                    raise ValueError("audit trail is not a JSON array")
            except ValueError:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.corrupt-{stamp}.json"))
                records = []
        records.append(record)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(records, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(tmp, AUDIT_PATH)


def read_all() -> list:
    """All audit records (oldest first), for the dashboard's event feed."""
    with _lock:
        if not AUDIT_PATH.exists() or not AUDIT_PATH.stat().st_size:
            return []
        try:
            records = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        except ValueError:
            return []
    return records if isinstance(records, list) else []


def describe_request(msg: ModelRequest) -> dict:
    """What went INTO the model this step: the prompt, tool results, retry messages."""
    parts = []
    for p in msg.parts:
        if isinstance(p, UserPromptPart):
            parts.append({"type": "prompt", "content": _clip(p.content)})
        elif isinstance(p, ToolReturnPart):
            parts.append({"type": "tool_result", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                          "content": _clip(p.model_response_str())})
        elif isinstance(p, RetryPromptPart):
            parts.append({"type": "retry", "tool": p.tool_name, "content": _clip(p.model_response())})
    return {"parts": parts}


def describe_response(msg: ModelResponse) -> dict:
    """What came OUT of the model this step: text, tool calls (incl. the final-output call), usage."""
    parts = []
    for p in msg.parts:
        if isinstance(p, ToolCallPart):
            parts.append({"type": "tool_call", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                          "args": _clip(p.args_as_dict())})
        elif isinstance(p, TextPart):
            parts.append({"type": "text", "content": _clip(p.content)})
        elif isinstance(p, ThinkingPart):
            parts.append({"type": "thinking", "chars": len(p.content or "")})
    u = msg.usage
    return {
        "model": msg.model_name,
        "parts": parts,
        "usage": {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                  "cache_read_tokens": u.cache_read_tokens},
    }
