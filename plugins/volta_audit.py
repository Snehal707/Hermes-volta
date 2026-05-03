"""Hermes Volta audit plugin.

This plugin is intentionally lightweight and fail-open: it observes Hermes
tool-call hooks, writes a local audit log, and never blocks a tool call.

Hermes directory plugin install layout:
  ~/.hermes/plugins/volta_audit/plugin.yaml
  ~/.hermes/plugins/volta_audit/__init__.py
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _detect_audit_project_root() -> Path:
    for key in ("VOLTA_PROJECT_ROOT", "HERMES_VOLTA_ROOT"):
        raw = os.environ.get(key)
        if raw:
            return Path(raw).expanduser().resolve()
    here = Path(__file__).resolve()
    candidate = here.parent.parent
    if (candidate / "sim" / "faraday_pipeline.py").is_file():
        return candidate
    return Path.cwd().resolve()


PROJECT_ROOT = _detect_audit_project_root()
OUTPUT_DIR = PROJECT_ROOT / "outputs"
AUDIT_LOG = OUTPUT_DIR / "volta_audit.log"
_LOCK = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}
_CIRCUIT_RE = re.compile(r"\b(RC_LOWPASS|RC_HIGHPASS|RLC_BANDPASS|RLC_NOTCH|RL_LOWPASS)\b", re.IGNORECASE)
_FREQ_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mhz|meg|khz|hz)\b", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _session_key(session_id: str = "", task_id: str = "") -> str:
    return session_id or task_id or os.getenv("HERMES_SESSION_ID") or os.getenv("HERMES_SESSION_KEY") or "unknown"


def _safe_json(value: Any, max_chars: int = 900) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        text = repr(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars] + f"... [truncated {len(text) - max_chars} chars]"
    return text


def _iter_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_iter_strings(item))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for item in value:
            strings.extend(_iter_strings(item))
        return strings
    return [str(value)]


def _detect_circuit(value: Any) -> tuple[str, str]:
    joined = " ".join(_iter_strings(value))
    circuit_match = _CIRCUIT_RE.search(joined)
    freq_match = _FREQ_RE.search(joined)
    circuit_type = circuit_match.group(1).upper() if circuit_match else ""
    frequency = ""
    if freq_match:
        frequency = f"{freq_match.group(1)}{freq_match.group(2)}"
    return circuit_type, frequency


def _state_for(session_key: str) -> dict[str, Any]:
    state = _SESSIONS.get(session_key)
    if state is None:
        state = {
            "started_at": time.monotonic(),
            "tool_calls": 0,
            "circuit_type": "",
            "frequency": "",
            "last_seen": time.monotonic(),
        }
        _SESSIONS[session_key] = state
    return state


def _append_line(line: str) -> None:
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(line.rstrip() + "\n")
    except Exception:
        # Audit logging must never break Hermes tool execution.
        return


def _log_record(record: dict[str, Any]) -> None:
    _append_line(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))


def _format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _write_summary(session_key: str, state: dict[str, Any]) -> None:
    circuit = state.get("circuit_type") or "UNKNOWN"
    frequency = state.get("frequency") or ""
    calls = int(state.get("tool_calls") or 0)
    duration = _format_duration(time.monotonic() - float(state.get("started_at") or time.monotonic()))
    if calls <= 0:
        return
    designed = f"{circuit} {frequency}".strip()
    _append_line(f"Session {session_key}: designed {designed}, {calls} tool calls, {duration}")


def on_pre_tool_call(
    *,
    tool_name: str = "",
    args: Any = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    **_: Any,
) -> None:
    session_key = _session_key(session_id=session_id, task_id=task_id)
    circuit_type, frequency = _detect_circuit(args)
    with _LOCK:
        state = _state_for(session_key)
        state["tool_calls"] += 1
        state["last_seen"] = time.monotonic()
        if circuit_type:
            state["circuit_type"] = circuit_type
        if frequency:
            state["frequency"] = frequency
        record = {
            "timestamp": _now_iso(),
            "event": "tool_call",
            "session_id": session_key,
            "task_id": task_id,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "tool_input_summary": _safe_json(args),
            "circuit_type": state.get("circuit_type") or circuit_type,
            "frequency": state.get("frequency") or frequency,
            "tool_call_count": state["tool_calls"],
        }
    _log_record(record)


def on_post_tool_call(
    *,
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    duration_ms: int | None = None,
    **_: Any,
) -> None:
    session_key = _session_key(session_id=session_id, task_id=task_id)
    circuit_type, frequency = _detect_circuit(result)
    with _LOCK:
        state = _state_for(session_key)
        if circuit_type:
            state["circuit_type"] = circuit_type
        if frequency:
            state["frequency"] = frequency
        state["last_seen"] = time.monotonic()
        if tool_name in {"execute_code", "terminal", "shell", "run_command"}:
            _log_record({
                "timestamp": _now_iso(),
                "event": "tool_result",
                "session_id": session_key,
                "tool_name": tool_name,
                "duration_ms": duration_ms,
                "circuit_type": state.get("circuit_type") or "",
                "frequency": state.get("frequency") or "",
                "result_summary": _safe_json(result, max_chars=500),
            })


def on_session_finalize(*, session_id: str = "", platform: str = "", **_: Any) -> None:
    session_key = _session_key(session_id=session_id)
    with _LOCK:
        state = _SESSIONS.pop(session_key, None)
    if state is not None:
        _write_summary(session_key, state)


def audit_command(_raw_args: str = "") -> str:
    try:
        if not AUDIT_LOG.exists():
            return f"No audit log yet at {AUDIT_LOG}"
        lines = AUDIT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-80:])
    except Exception as exc:
        return f"Could not read audit log: {exc}"


def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("on_session_finalize", on_session_finalize)
    ctx.register_command("audit", audit_command, description="Show recent Hermes Volta audit log entries")
