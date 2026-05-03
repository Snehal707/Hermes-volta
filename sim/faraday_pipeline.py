"""Main execute_code entry point for Hermes Volta."""

import os
import sys
import warnings
import importlib.util
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message=".*fp-lib-table.*")
warnings.filterwarnings("ignore", message=".*KICAD.*SYMBOL.*")
warnings.filterwarnings("ignore", message=".*symbol libraries.*")

_REPO_BOOT = Path(__file__).resolve().parents[1]
if str(_REPO_BOOT) not in sys.path:
    sys.path.insert(0, str(_REPO_BOOT))

from sim.volta_paths import preferred_python_exe, prepend_sim_import_helpers, project_root_path

prepend_sim_import_helpers()
PROJECT_ROOT_PATH = project_root_path()
HERMES_VENV_PYTHON = preferred_python_exe(PROJECT_ROOT_PATH)

KICAD_SYMBOL_DIR = "/usr/share/kicad/symbols"
for _symbol_env in (
    "KICAD_SYMBOL_DIR",
    "KICAD5_SYMBOL_DIR",
    "KICAD6_SYMBOL_DIR",
    "KICAD7_SYMBOL_DIR",
    "KICAD8_SYMBOL_DIR",
    "KICAD9_SYMBOL_DIR",
):
    os.environ.setdefault(_symbol_env, KICAD_SYMBOL_DIR)


def _ensure_venv_python_for_terminal() -> None:
    """Re-run direct terminal invocations with Hermes' package-complete venv."""
    if __name__ != "__main__":
        return
    if not HERMES_VENV_PYTHON.exists():
        return
    current = Path(sys.executable).resolve()
    expected = HERMES_VENV_PYTHON.resolve()
    if current == expected:
        return
    os.execv(str(expected), [str(expected), str(Path(__file__).resolve()), *sys.argv[1:]])


_ensure_venv_python_for_terminal()

try:
    from sim import netlist, pcb_export, report, simulate
except ImportError:  # pragma: no cover - direct execution from sim/
    import netlist
    import pcb_export
    import report
    import simulate


OUTPUT_ROOT = PROJECT_ROOT_PATH / "outputs"
LATEST_FILES = {
    "bode_path": "frequency_response.png",
    "wave_path": "waveform.png",
    "compare_plot": "compare_plot.png",
    "netlist": "circuit.net",
    "pcb_png": "pcb_view.png",
    "gerbers": "gerbers.zip",
    "report": "cutoff_report.txt",
}


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _format_fc(fc: float) -> str:
    if fc and float(fc).is_integer():
        return str(int(fc))
    return f"{fc:.6g}".replace(".", "p")


def _design_output_dir(circuit_type: str, fc: float) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = f"{_slug(circuit_type)}_{_format_fc(float(fc))}Hz_{timestamp}"
    output_dir = OUTPUT_ROOT / folder
    suffix = 1
    while output_dir.exists():
        output_dir = OUTPUT_ROOT / f"{folder}_{suffix}"
        suffix += 1
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _copy_latest(result: dict[str, Any]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for key, latest_name in LATEST_FILES.items():
        value = result.get(key)
        if not value:
            continue
        source = Path(str(value))
        if not source.is_file():
            continue
        shutil.copy2(source, OUTPUT_ROOT / latest_name)


def _write_rl_trajectory(params: dict[str, Any], result: dict[str, Any]) -> str | None:
    module_path = PROJECT_ROOT_PATH / "tools" / "rl_trajectory.py"
    if not module_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("volta_rl_trajectory", module_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.generate_trajectory(params, result, output_dir=result.get("output_dir"))
    except Exception as exc:
        print(f"[Volta] Warning: RL trajectory generation skipped: {exc}")
        return None


def run(
    circuit_type: str,
    R: float,
    C: float,
    supply_v: float = 1.0,
    L: float | None = None,
    fc: float = 0.0,
    description: str = "",
) -> dict[str, Any]:
    """Run simulation, netlist/PCB export, and report generation in one turn."""
    normalized = circuit_type.strip().upper().replace("-", "_")
    _TOPO_ALIAS = {
        "LOWPASS": "RC_LOWPASS",
        "HIGHPASS": "RC_HIGHPASS",
        "BANDPASS": "RLC_BANDPASS",
        "NOTCH": "RLC_NOTCH",
    }
    normalized = _TOPO_ALIAS.get(normalized, normalized)
    params = {
        "circuit_type": normalized,
        "R": float(R),
        "C": float(C),
        "L": None if normalized in {"RC_LOWPASS", "RC_HIGHPASS"} or L is None else float(L),
        "supply_v": float(supply_v),
        "fc": float(fc),
        "description": description,
    }
    design_output_dir = _design_output_dir(normalized, params["fc"])

    print(f"[Volta] Starting {normalized}: {description}")
    print(f"[Volta] Output directory: {design_output_dir}")
    print("[Volta] Running PySpice/Ngspice simulation...")
    sim_results = simulate.run_simulation(
        topology=normalized,
        resistance_ohm=params["R"],
        capacitance_f=params["C"],
        inductance_h=params["L"],
        source_amplitude_v=params["supply_v"],
        output_dir=design_output_dir,
    )

    actual_fc = float(sim_results.get("actual_fc", 0.0))
    error_pct = abs((actual_fc - params["fc"]) / params["fc"] * 100.0) if params["fc"] else 0.0
    print(f"[Volta] Simulation actual_fc={actual_fc:.6g} Hz, error={error_pct:.3f}%")

    print("[Volta] Generating KiCad netlist...")
    netlist_path = netlist.generate_netlist(
        circuit_type=normalized,
        R=params["R"],
        C=params["C"],
        L=params["L"],
        supply_v=params["supply_v"],
        output_dir=design_output_dir,
    )

    print("[Volta] Exporting PCB artifacts with kicad-cli...")
    pcb_files = pcb_export.run_pcb_export(netlist_path, output_dir=design_output_dir, actual_fc=actual_fc)
    pcb_png = pcb_files.get("pcb_png") if pcb_files else None
    gerbers = pcb_files.get("gerbers") if pcb_files else None

    result = {
        "actual_fc": actual_fc,
        "error_pct": error_pct,
        "bode_path": sim_results.get("bode_path"),
        "wave_path": sim_results.get("wave_path"),
        "netlist": netlist_path,
        "pcb_png": pcb_png,
        "gerbers": gerbers,
        "output_dir": str(design_output_dir),
    }

    print("[Volta] Writing cutoff report...")
    report_path = report.write_report(params, result, output_dir=design_output_dir)
    result["report"] = report_path

    try:
        from sim.compare_plot import generate_compare_plot

        compare_path = generate_compare_plot(
            output_dir=str(design_output_dir),
            circuit_type=params["circuit_type"],
            R=params["R"],
            C=params["C"],
            L=params["L"],
            fc=sim_results.get("actual_fc", params["fc"]),
            supply_v=params["supply_v"],
        )
        result["compare_plot"] = str(compare_path)
    except Exception as e:
        print(f"[Volta] compare_plot skipped: {e}")
        result["compare_plot"] = None

    trajectory_path = _write_rl_trajectory(params, result)
    if trajectory_path:
        result["trajectory"] = trajectory_path
        print(f"[Volta] RL trajectory saved: {trajectory_path}")
    _copy_latest(result)

    print("[Volta] Done.")
    return result


if __name__ == "__main__":
    print(run("RC_LOWPASS", R=1_000.0, C=100e-9, supply_v=1.0, L=10e-3, fc=1591.55))
