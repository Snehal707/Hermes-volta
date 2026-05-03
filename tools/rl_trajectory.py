"""Generate ShareGPT-format RL trajectories for Hermes Volta designs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_BOOT = Path(__file__).resolve().parents[1]
if str(_REPO_BOOT) not in sys.path:
    sys.path.insert(0, str(_REPO_BOOT))

from sim.volta_paths import project_root_path

PROJECT_ROOT = project_root_path()
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TRAJECTORY_DIR = OUTPUTS_DIR / "trajectories"


def _session_id(output_dir: str | Path | None = None, explicit: str | None = None) -> str:
    if explicit:
        return _safe_name(explicit)
    for key in ("HERMES_SESSION_ID", "HERMES_SESSION_KEY", "HERMES_TASK_ID"):
        value = os.getenv(key)
        if value:
            return _safe_name(value)
    if output_dir:
        return _safe_name(Path(output_dir).name)
    return f"volta_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_") or "volta_session"


def _eng(value: Any, unit: str = "") -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    prefixes = (
        (1e6, "M"),
        (1e3, "k"),
        (1.0, ""),
        (1e-3, "m"),
        (1e-6, "u"),
        (1e-9, "n"),
        (1e-12, "p"),
    )
    magnitude = abs(numeric)
    for scale, prefix in prefixes:
        if magnitude >= scale or scale == 1e-12:
            return f"{numeric / scale:.6g}{prefix}{unit}"
    return f"{numeric:.6g}{unit}"


def _number(value: Any, default: float = 0.0) -> float:
    if value in {None, ""}:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*([GMkmunp]?)(?:ohm|Ω|F|H|V)?", text, re.IGNORECASE)
    if not match:
        return default
    scale = {
        "G": 1e9,
        "M": 1e6,
        "k": 1e3,
        "m": 1e-3,
        "u": 1e-6,
        "n": 1e-9,
        "p": 1e-12,
        "": 1.0,
    }[match.group(2)]
    return float(match.group(1)) * scale


def _prompt_from_params(params: dict[str, Any]) -> str:
    circuit_type = str(params.get("circuit_type", "filter")).replace("_", " ").lower()
    fc = _number(params.get("fc"), 0.0)
    supply_v = _number(params.get("supply_v"), 5.0)
    description = str(params.get("description") or "").strip()
    if description:
        return description
    return f"design a {fc:.6g}Hz {circuit_type} at {supply_v:.6g}V"


def _tools_used(result: dict[str, Any], explicit: list[str] | None = None) -> list[str]:
    if explicit:
        return explicit
    tools = ["execute_code"]
    if result.get("netlist"):
        tools.append("terminal")
    if result.get("report"):
        tools.append("memory")
    if result.get("pcb_png") or result.get("gerbers"):
        tools.append("send_message")
    return tools


def _conversation(params: dict[str, Any], result: dict[str, Any], prompt: str) -> list[dict[str, str]]:
    circuit_type = str(params.get("circuit_type", "UNKNOWN")).upper().replace("-", "_")
    r = _number(params.get("R"), 0.0)
    c = _number(params.get("C"), 0.0)
    l = params.get("L")
    target_fc = _number(params.get("fc"), 0.0)
    actual_fc = _number(result.get("actual_fc"), 0.0)
    error_pct = _number(result.get("error_pct"), 0.0)
    components = f"R={_eng(r, 'ohm')} C={_eng(c, 'F')}"
    if l not in {None, "", 0, 0.0}:
        components += f" L={_eng(_number(l), 'H')}"
    status = "PASS" if error_pct <= 5.0 else "FAIL"
    return [
        {"from": "human", "value": prompt},
        {
            "from": "gpt",
            "value": (
                f"Computing {circuit_type}: fc=1/(2*pi*R*C) where applicable. "
                f"Selected {components} for target fc={target_fc:.6g}Hz."
            ),
        },
        {"from": "tool", "value": f"PySpice simulation result: actual_fc={actual_fc:.6g}Hz error={error_pct:.3f}%"},
        {"from": "gpt", "value": f"Verified {status}. Saving to memory. Patching skill if this creates a reusable recipe."},
    ]


def generate_trajectory(
    params: dict[str, Any],
    result: dict[str, Any],
    *,
    session_id: str | None = None,
    user_prompt: str | None = None,
    tools_used: list[str] | None = None,
    output_dir: str | Path | None = None,
) -> str:
    """Write a ShareGPT trajectory JSON file and return its path."""
    design_output_dir = Path(output_dir or result.get("output_dir") or OUTPUTS_DIR)
    sid = _session_id(design_output_dir, session_id)
    prompt = user_prompt or _prompt_from_params(params)
    actual_fc = _number(result.get("actual_fc"), 0.0)
    target_fc = _number(params.get("fc"), 0.0)
    error_pct = _number(result.get("error_pct"), 0.0)
    trajectory = {
        "conversations": _conversation(params, result, prompt),
        "metadata": {
            "circuit_type": str(params.get("circuit_type", "UNKNOWN")).upper().replace("-", "_"),
            "fc_target": target_fc,
            "fc_actual": actual_fc,
            "error_pct": error_pct,
            "tools_used": _tools_used(result, tools_used),
            "skill": "volta",
            "timestamp": datetime.now().date().isoformat(),
            "session_id": sid,
            "output_dir": str(design_output_dir),
        },
    }
    TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = TRAJECTORY_DIR / f"{sid}.json"
    path.write_text(json.dumps(trajectory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def _parse_report(report_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    text = report_path.read_text(encoding="utf-8", errors="replace")

    def extract(pattern: str, default: str = "") -> str:
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1).strip() if match else default

    params = {
        "circuit_type": extract(r"^Circuit type:\s*(.+)$", "UNKNOWN"),
        "R": extract(r"^\s*R:\s*(.+)$", ""),
        "C": extract(r"^\s*C:\s*(.+)$", ""),
        "L": extract(r"^\s*L:\s*(.+)$", ""),
        "supply_v": extract(r"^\s*Supply:\s*(.+?)\s*V$", "5"),
        "fc": float(extract(r"^\s*Target fc:\s*(.+?)\s*Hz$", "0") or 0),
        "description": extract(r"^Description:\s*(.*)$", ""),
    }
    result = {
        "actual_fc": float(extract(r"^\s*Actual fc:\s*(.+?)\s*Hz$", "0") or 0),
        "error_pct": float(extract(r"^\s*Error:\s*(.+?)%$", "0") or 0),
        "report": str(report_path),
        "output_dir": str(report_path.parent),
    }
    return params, result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ShareGPT RL trajectory data for a Volta design.")
    parser.add_argument("--report", type=Path, help="Path to cutoff_report.txt. Defaults to outputs/cutoff_report.txt.")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--prompt", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report_path = args.report or (OUTPUTS_DIR / "cutoff_report.txt")
    params, result = _parse_report(report_path)
    path = generate_trajectory(params, result, session_id=args.session_id, user_prompt=args.prompt, output_dir=report_path.parent)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
