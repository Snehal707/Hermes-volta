"""Plain-text design report writer for Hermes Volta."""

import sys
import os

# Add venv site-packages to path so execute_code can find packages
VENV_SITE_PACKAGES = "/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/lib/python3.11/site-packages"
if VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

# Also add project root
PROJECT_ROOT = "/mnt/c/Users/ASUS/HermesVolta"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import math
from datetime import datetime
from pathlib import Path
from typing import Any


OUTPUT_DIR = Path("outputs")
REPORT_PATH = OUTPUT_DIR / "cutoff_report.txt"
PASS_ERROR_PCT = 5.0


def _eng(value: float, unit: str) -> str:
    prefixes = [
        (1e6, "M"),
        (1e3, "k"),
        (1.0, ""),
        (1e-3, "m"),
        (1e-6, "u"),
        (1e-9, "n"),
        (1e-12, "p"),
    ]
    magnitude = abs(value)
    for scale, prefix in prefixes:
        if magnitude >= scale or scale == 1e-12:
            return f"{value / scale:.6g} {prefix}{unit}".strip()
    return f"{value:.6g} {unit}".strip()


def _theory_fc(circuit_type: str, params: dict[str, Any]) -> float:
    r = float(params.get("R", params.get("resistance_ohm", 1_000.0)))
    c = float(params.get("C", params.get("capacitance_f", 100e-9)))
    normalized = circuit_type.upper().replace("-", "_")
    if normalized in {"RC_LOWPASS", "RC_HIGHPASS"}:
        return 1.0 / (2.0 * math.pi * r * c)
    l = float(params.get("L", params.get("inductance_h", 10e-3)))
    if normalized in {"RLC_BANDPASS", "RLC_NOTCH"}:
        return 1.0 / (2.0 * math.pi * math.sqrt(l * c))
    if normalized == "RL_LOWPASS":
        return r / (2.0 * math.pi * l)
    return float("nan")


def _jlc_search(ref: str, value: str, footprint: str) -> str:
    if ref.startswith("R"):
        return f"JLCPCB {value} 0402 resistor"
    if ref.startswith("C"):
        return f"JLCPCB {value} 0402 capacitor"
    if ref.startswith("L"):
        return f"JLCPCB {value} 0402 inductor"
    return f"JLCPCB {value} {footprint}"


def _bom(params: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    r = _eng(float(params.get("R", 1_000.0)), "ohm")
    c = _eng(float(params.get("C", 100e-9)), "F")
    rows = [
        ("R1", r, "Resistor_SMD:R_0402", _jlc_search("R1", r, "Resistor_SMD:R_0402")),
        ("C1", c, "Capacitor_SMD:C_0402", _jlc_search("C1", c, "Capacitor_SMD:C_0402")),
    ]
    if str(params.get("circuit_type", "")).upper().replace("-", "_").startswith("RLC"):
        l = _eng(float(params.get("L", 10e-3)), "H")
        rows.append(("L1", l, "Inductor_SMD:L_0402", _jlc_search("L1", l, "Inductor_SMD:L_0402")))
    return rows


def _output_files(sim_results: dict[str, Any]) -> list[str]:
    files = []
    for key in ("bode_path", "wave_path", "netlist", "pcb_png", "gerbers"):
        value = sim_results.get(key)
        if value:
            files.append(str(value))
    files.append(str(sim_results.get("report") or REPORT_PATH))
    return files


def write_report(
    params: dict[str, Any],
    sim_results: dict[str, Any],
    output_dir: str | Path = OUTPUT_DIR,
) -> str:
    """Write ``outputs/cutoff_report.txt``, print it, and return its path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "cutoff_report.txt"

    circuit_type = str(params.get("circuit_type", "UNKNOWN")).upper().replace("-", "_")
    target_fc = float(params.get("fc", params.get("target_fc", 0.0)) or 0.0)
    theory_fc = float(params.get("theory_fc") or _theory_fc(circuit_type, params))
    actual_fc = float(sim_results.get("actual_fc", float("nan")))
    error_pct = abs((actual_fc - target_fc) / target_fc * 100.0) if target_fc and math.isfinite(actual_fc) else float("nan")
    passed = math.isfinite(error_pct) and error_pct <= PASS_ERROR_PCT
    status = "PASS" if passed else "FAIL"
    frequency_label = "f0" if circuit_type in {"RLC_BANDPASS", "RLC_NOTCH"} else "fc"
    memory_entry = (
        f"Hermes Volta saved {circuit_type}: R={params.get('R')}, C={params.get('C')}, "
        f"L={params.get('L')}, target_{frequency_label}={target_fc:.6g} Hz, "
        f"actual_{frequency_label}={actual_fc:.6g} Hz, status={status}."
    )
    show_inductance = circuit_type in {"RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS"}

    report_title = (
        "Hermes Volta Notch Report"
        if circuit_type == "RLC_NOTCH"
        else "Hermes Volta Bandpass Report"
        if circuit_type == "RLC_BANDPASS"
        else "Hermes Volta Cutoff Report"
    )

    lines = [
        report_title,
        "=" * 28,
        f"Circuit type: {circuit_type}",
        f"Date: {datetime.now().isoformat(timespec='seconds')}",
        f"Description: {params.get('description', '')}",
        "",
        "Component Values",
        f"  R: {_eng(float(params.get('R', 1_000.0)), 'ohm')}",
        f"  C: {_eng(float(params.get('C', 100e-9)), 'F')}",
    ]
    if show_inductance:
        lines.append(f"  L: {_eng(float(params.get('L', 10e-3)), 'H')}")
    lines.extend([
        f"  Supply: {float(params.get('supply_v', 1.0)):.6g} V",
        "",
        (
            "Notch Center Frequency"
            if circuit_type == "RLC_NOTCH"
            else "Bandpass Center Frequency"
            if circuit_type == "RLC_BANDPASS"
            else "Cutoff Frequency"
        ),
        f"  Target {frequency_label}: {target_fc:.6g} Hz",
        f"  Theory {frequency_label}: {theory_fc:.6g} Hz",
        f"  Actual {frequency_label}: {actual_fc:.6g} Hz",
        f"  Error: {error_pct:.3f}%",
        f"  Result: {status}",
        "",
        "BOM / JLCPCB Search Strings",
        "  Ref | Value | Footprint | Search",
    ])
    for ref, value, footprint, search in _bom({"circuit_type": circuit_type, **params}):
        lines.append(f"  {ref} | {value} | {footprint} | {search}")

    lines.extend(["", "Output Files"])
    for file_path in _output_files({**sim_results, "report": str(report_path)}):
        lines.append(f"  {file_path}")

    lines.extend(["", "Hermes Memory Entry", f"  {memory_entry}", ""])
    text = "\n".join(lines)
    report_path.write_text(text, encoding="utf-8")
    print(text)
    return str(report_path)


if __name__ == "__main__":
    write_report(
        {"circuit_type": "RC_LOWPASS", "R": 1_000.0, "C": 100e-9, "L": 10e-3, "fc": 1591.55},
        {"actual_fc": 1590.0, "bode_path": "outputs/frequency_response.png", "wave_path": "outputs/waveform.png"},
    )
