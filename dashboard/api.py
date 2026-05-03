"""FastAPI control panel for Hermes Volta."""

from __future__ import annotations

import asyncio
import json
import math
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_BOOT = Path(__file__).resolve().parents[1]
if str(_REPO_BOOT) not in sys.path:
    sys.path.insert(0, str(_REPO_BOOT))

from sim.volta_paths import preferred_python_exe, prepend_sim_import_helpers, project_root_path

prepend_sim_import_helpers()
PROJECT_ROOT = project_root_path()
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
PROJECT_MEMORY = PROJECT_ROOT / "MEMORY.md"
GLOBAL_MEMORY = Path.home() / ".hermes" / "memories" / "MEMORY.md"
REPORT_PATH = OUTPUTS_DIR / "cutoff_report.txt"
AUDIT_LOG_PATH = OUTPUTS_DIR / "volta_audit.log"
VENV_PYTHON = preferred_python_exe(PROJECT_ROOT)

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


VERSION = "1.0.0"


app = FastAPI(title="Hermes Volta Control Panel", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR), name="dashboard")


class DesignRequest(BaseModel):
    prompt: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "volta-1.0"
    messages: list[ChatMessage]
    temperature: float | None = None
    stream: bool = False


def _read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def _memory_path() -> Path:
    return PROJECT_MEMORY if PROJECT_MEMORY.exists() else GLOBAL_MEMORY


def _memory_entries() -> list[str]:
    text = _read_text(_memory_path())
    if not text.strip():
        return []
    if "§" in text:
        return [entry.strip() for entry in text.split("§") if entry.strip()]
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("|")]


def _file_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "size": stat.st_size,
        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def _safe_output_file(filename: str) -> Path:
    requested = Path(filename)
    if requested.is_absolute() or any(part in {"", ".", ".."} for part in requested.parts):
        raise HTTPException(status_code=400, detail="Invalid output filename")
    path = (OUTPUTS_DIR / requested).resolve()
    outputs_root = OUTPUTS_DIR.resolve()
    if outputs_root not in path.parents and path != outputs_root:
        raise HTTPException(status_code=400, detail="Invalid output path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Output not found: {filename}")
    return path


def _last_design() -> dict[str, Any] | None:
    if not REPORT_PATH.exists():
        return None
    return {
        "report": str(REPORT_PATH.relative_to(PROJECT_ROOT)),
        "modified_time": datetime.fromtimestamp(REPORT_PATH.stat().st_mtime).isoformat(timespec="seconds"),
        "preview": "\n".join(_read_text(REPORT_PATH).splitlines()[:12]),
    }


def _parse_design_folder(path: Path) -> dict[str, Any] | None:
    match = re.match(r"^(?P<circuit_type>.+)_(?P<fc>[^_]+)Hz_(?P<stamp>\d{8}_\d{6})$", path.name)
    if not match:
        return None

    stamp = match.group("stamp")
    try:
        date = datetime.strptime(stamp, "%Y%m%d_%H%M%S").isoformat(timespec="seconds")
    except ValueError:
        date = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")

    return {
        "folder": path.name,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "circuit_type": match.group("circuit_type"),
        "fc": match.group("fc"),
        "date": date,
        "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }


def _extract_report_value(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else default


def _extract_bom_value(ref: str, text: str) -> str:
    match = re.search(rf"^\s*{re.escape(ref)}\s+\|\s*([^|]+)\|", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _design_folder_path(folder_name: str) -> Path:
    clean_name = Path(folder_name).name
    if clean_name != folder_name or clean_name in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid design folder")
    path = (OUTPUTS_DIR / clean_name).resolve()
    outputs_root = OUTPUTS_DIR.resolve()
    if outputs_root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid design path")
    if not path.is_dir():
        raise HTTPException(status_code=404, detail=f"Design not found: {folder_name}")
    return path


def _design_detail(path: Path) -> dict[str, Any]:
    parsed = _parse_design_folder(path) or {
        "folder": path.name,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "circuit_type": "",
        "fc": "",
        "date": "",
        "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }
    report_path = path / "cutoff_report.txt"
    report_text = _read_text(report_path)
    files = [_file_info(file_path) for file_path in sorted(path.iterdir()) if file_path.is_file()]
    return {
        **parsed,
        "circuit_type": _extract_report_value(r"^Circuit type:\s*(.+)$", report_text, parsed.get("circuit_type", "")),
        "R": _extract_bom_value("R1", report_text),
        "C": _extract_bom_value("C1", report_text),
        "fc": _extract_report_value(r"^\s*Target fc:\s*(.+?)\s*Hz$", report_text, parsed.get("fc", "")),
        "actual_fc": _extract_report_value(r"^\s*Actual fc:\s*(.+?)\s*Hz$", report_text),
        "error": _extract_report_value(r"^\s*Error:\s*(.+?)%$", report_text),
        "status": _extract_report_value(r"^\s*Result:\s*(.+)$", report_text),
        "files": files,
        "report": report_text,
    }


E24_BASE = (10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91)


def _nearest_e24_resistor(target_ohm: float) -> float:
    candidates: list[float] = []
    for decade in range(0, 8):
        scale = 10 ** decade
        candidates.extend(base * scale for base in E24_BASE)
    practical = [value for value in candidates if 10 <= value <= 10_000_000]
    return min(practical, key=lambda value: abs(value - target_ohm))


def _parse_frequency_hz(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(mhz|meg|khz|hz)\b", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit in {"mhz", "meg"}:
        return value * 1_000_000
    if unit == "khz":
        return value * 1_000
    return value


def _parse_supply_v(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*v\b", text, re.IGNORECASE)
    return float(match.group(1)) if match else 5.0


def _detect_topology(text: str) -> str | None:
    lower = text.lower()
    if any(token in lower for token in ("low-pass", "low pass", "lowpass")):
        return "RC_LOWPASS"
    if any(token in lower for token in ("high-pass", "high pass", "highpass")):
        return "RC_HIGHPASS"
    if any(token in lower for token in ("band-pass", "band pass", "bandpass")):
        return "RLC_BANDPASS"
    if "notch" in lower:
        return "RLC_NOTCH"
    if "filter" in lower or "circuit" in lower or "design" in lower:
        return "RC_LOWPASS"
    return None


def _design_intent(prompt: str) -> dict[str, Any] | None:
    topology = _detect_topology(prompt)
    fc = _parse_frequency_hz(prompt)
    if not topology or not fc:
        return None
    capacitance = 100e-9
    resistance = _nearest_e24_resistor(1.0 / (2.0 * math.pi * fc * capacitance))
    inductance = None if topology in {"RC_LOWPASS", "RC_HIGHPASS"} else 10e-3
    return {
        "circuit_type": topology,
        "R": resistance,
        "C": capacitance,
        "L": inductance,
        "fc": fc,
        "supply_v": _parse_supply_v(prompt),
        "description": prompt,
    }


def _format_design_response(result: dict[str, Any]) -> str:
    return "\n".join([
        "Hermes Volta design complete.",
        f"actual_fc: {float(result.get('actual_fc', 0.0)):.6g} Hz",
        f"error_pct: {float(result.get('error_pct', 0.0)):.3f}%",
        f"output_dir: {result.get('output_dir')}",
        f"bode_path: {result.get('bode_path')}",
        f"wave_path: {result.get('wave_path')}",
        f"pcb_png: {result.get('pcb_png')}",
        f"gerbers: {result.get('gerbers')}",
        f"report: {result.get('report')}",
    ])


def _run_faraday_subprocess(design_params: dict[str, Any]) -> dict[str, Any]:
    params_json = json.dumps(design_params)
    code = f"""
from sim.faraday_pipeline import run
import json
params = json.loads({json.dumps(params_json)})
result = run(
    params["circuit_type"],
    R=params["R"],
    C=params["C"],
    supply_v=params["supply_v"],
    L=params["L"],
    fc=params["fc"],
    description=params["description"],
)
print("VOLTA_RESULT_JSON_START")
print(json.dumps(result))
"""
    proc = subprocess.run(
        [str(VENV_PYTHON), "-c", code],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=240,
    )
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode != 0:
        raise RuntimeError(combined.strip() or f"faraday_pipeline exited with {proc.returncode}")
    marker = "VOLTA_RESULT_JSON_START"
    if marker not in proc.stdout:
        raise RuntimeError(f"missing result marker in pipeline output: {combined[-2000:]}")
    payload = proc.stdout.split(marker, 1)[1].strip().splitlines()[0]
    return json.loads(payload)


def _openai_response(content: str, model: str = "volta-1.0") -> dict[str, Any]:
    return {
        "id": f"chatcmpl-volta-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard/index.html")


@app.get("/status")
def status() -> dict[str, Any]:
    return {
        "project": "Hermes Volta",
        "project_root": str(PROJECT_ROOT),
        "status": "ready",
        "last_design": _last_design(),
        "memory_path": str(_memory_path()),
        "memory_entries": _memory_entries(),
    }


@app.get("/outputs")
def outputs() -> dict[str, Any]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    files = [_file_info(path) for path in sorted(OUTPUTS_DIR.iterdir()) if path.is_file()]
    return {"outputs_dir": str(OUTPUTS_DIR), "files": files}


@app.get("/designs")
def designs() -> dict[str, Any]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    design_rows = []
    for path in sorted(OUTPUTS_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        parsed = _parse_design_folder(path)
        if parsed:
            design_rows.append(parsed)
    return {"outputs_dir": str(OUTPUTS_DIR), "designs": design_rows}


@app.get("/designs/{folder_name}")
def design_detail(folder_name: str) -> dict[str, Any]:
    return _design_detail(_design_folder_path(folder_name))


@app.get("/v1/models")
def openai_models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": "volta-1.0", "object": "model"}]}


@app.post("/v1/chat/completions")
def openai_chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
    if request.stream:
        raise HTTPException(status_code=400, detail="Streaming is not supported by this endpoint yet.")
    user_messages = [message.content for message in request.messages if message.role == "user"]
    prompt = user_messages[-1].strip() if user_messages else ""
    if not prompt:
        raise HTTPException(status_code=400, detail="At least one user message is required.")

    design_params = _design_intent(prompt)
    if not design_params:
        return _openai_response(
            "Hermes Volta is ready. Ask me to design a filter, for example: design a 1kHz RC low-pass filter at 5V.",
            request.model,
        )

    try:
        result = _run_faraday_subprocess(design_params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Volta design failed: {type(exc).__name__}: {exc}") from exc

    return _openai_response(_format_design_response(result), request.model)


@app.get("/outputs/{filename:path}")
def output_file(filename: str) -> FileResponse:
    return FileResponse(_safe_output_file(filename))


@app.get("/memory", response_class=PlainTextResponse)
def memory() -> str:
    return _read_text(_memory_path(), "No MEMORY.md found.\n")


@app.get("/audit", response_class=PlainTextResponse)
def audit() -> str:
    return _read_text(AUDIT_LOG_PATH, "No Volta audit log found yet.\n")


@app.get("/report", response_class=PlainTextResponse)
def report() -> str:
    return _read_text(REPORT_PATH, "No cutoff report found yet.\n")


async def _stream_command(prompt: str):
    design_params = _design_intent(prompt)
    if not design_params:
        yield (
            "Could not parse a Volta design from this prompt.\n"
            "Try: design a 1kHz low-pass filter at 5V\n"
        ).encode("utf-8")
        return

    yield f"[Dashboard] Parsed request: {design_params['circuit_type']} at {design_params['fc']:.6g} Hz\n".encode("utf-8")
    yield f"[Dashboard] R={design_params['R']:.6g} ohm, C={design_params['C']:.6g} F, supply={design_params['supply_v']:.6g} V\n".encode("utf-8")

    params_json = json.dumps(design_params)
    code = f"""
from sim.faraday_pipeline import run
import json
params = json.loads({json.dumps(params_json)})
result = run(
    params["circuit_type"],
    R=params["R"],
    C=params["C"],
    supply_v=params["supply_v"],
    L=params["L"],
    fc=params["fc"],
    description=params["description"],
)
print("VOLTA_RESULT_JSON_START")
print(json.dumps(result))
"""
    process = await asyncio.create_subprocess_exec(
        str(VENV_PYTHON),
        "-u",
        "-c",
        code,
        cwd=str(PROJECT_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None
    result_json = ""
    capture_json = False
    while True:
        chunk = await process.stdout.readline()
        if not chunk:
            break
        line = chunk.decode("utf-8", errors="replace")
        if capture_json:
            result_json = line.strip()
            capture_json = False
            continue
        if line.strip() == "VOLTA_RESULT_JSON_START":
            capture_json = True
            continue
        yield chunk
    code = await process.wait()
    if code != 0:
        yield f"\n[Dashboard] Volta pipeline exited with code {code}\n".encode("utf-8")
        return
    if result_json:
        try:
            result = json.loads(result_json)
            yield b"\n[Dashboard] Design complete.\n"
            yield _format_design_response(result).encode("utf-8")
            yield b"\n"
        except json.JSONDecodeError:
            yield f"\n[Dashboard] Design complete, but result JSON could not be parsed: {result_json}\n".encode("utf-8")
    else:
        yield b"\n[Dashboard] Design complete, but no result JSON was emitted.\n"


@app.post("/design")
async def design(request: DesignRequest) -> StreamingResponse:
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    return StreamingResponse(_stream_command(prompt), media_type="text/plain")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)
