"""PySpice + Ngspice headless simulation engine for Hermes Volta.

The public entry point is :func:`run_simulation`. It builds one of Volta's
canonical filter circuits, runs an AC sweep and transient simulation, writes
dark-theme plots to ``./outputs/``, and returns the key artifact paths.
"""

import sys

# Add venv site-packages to path so execute_code can find packages
VENV_SITE_PACKAGES = "/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/lib/python3.11/site-packages"
if VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

# Also add project root
PROJECT_ROOT = "/mnt/c/Users/ASUS/HermesVolta"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import argparse  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import math  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Literal  # noqa: E402

Topology = Literal["RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS"]

OUTPUT_DIR = Path("outputs")
AC_POINTS_PER_DECADE = 100
AC_START_HZ = 1.0
AC_STOP_HZ = 1_000_000.0
TRANSIENT_STEP_S = 1e-6
TRANSIENT_END_S = 5e-3
TEMPERATURE_C = 25


class _KnownGoodNgspiceWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith("Unsupported Ngspice version ")


logging.getLogger("PySpice.Spice.NgSpice.Shared.NgSpiceShared").addFilter(_KnownGoodNgspiceWarningFilter())


def _load_pyspice() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    try:
        from PySpice.Spice.Netlist import Circuit
        from PySpice.Unit import u_F, u_H, u_Hz, u_V, u_s, u_Ω
    except ImportError as exc:  # pragma: no cover - depends on local simulator install
        raise ImportError(
            "sim/simulate.py requires PySpice and Ngspice. Install PySpice with pip "
            "and make sure libngspice is available on the system path."
        ) from exc
    return Circuit, u_F, u_H, u_Hz, u_V, u_s, u_Ω


def _load_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on local simulator install
        raise ImportError("sim/simulate.py requires NumPy for PySpice result processing.") from exc
    return np


def _load_pyplot() -> Any:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on local simulator install
        raise ImportError("sim/simulate.py requires Matplotlib for headless plot generation.") from exc
    return plt


@dataclass(frozen=True)
class SimulationSpec:
    """Canonical component values for a Volta filter simulation."""

    topology: Topology
    resistance_ohm: float = 1_000.0
    capacitance_f: float = 100e-9
    inductance_h: float | None = 10e-3
    source_amplitude_v: float = 1.0
    transient_frequency_hz: float = 1_000.0


def _normalize_topology(topology: str) -> Topology:
    normalized = topology.strip().upper().replace("-", "_")
    supported = {"RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS"}
    if normalized not in supported:
        raise ValueError(f"unsupported topology {topology!r}; choose one of {', '.join(sorted(supported))}")
    return normalized  # type: ignore[return-value]


def _validate_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def _source_line(spec: SimulationSpec) -> str:
    return (
        "Vin vin 0 "
        "DC 0 AC 1 "
        f"SIN(0 {spec.source_amplitude_v / 2:g} {spec.transient_frequency_hz:g})\n"
    )


def build_circuit(spec: SimulationSpec) -> tuple[Any, str]:
    """Build a PySpice circuit and return it with the measured output node."""
    Circuit, u_F, u_H, _u_Hz, _u_V, _u_s, u_Ω = _load_pyspice()
    _validate_positive("resistance_ohm", spec.resistance_ohm)
    _validate_positive("capacitance_f", spec.capacitance_f)
    if spec.topology in {"RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS"}:
        if spec.inductance_h is None:
            raise ValueError(f"inductance_h is required for {spec.topology}")
        _validate_positive("inductance_h", spec.inductance_h)
    _validate_positive("source_amplitude_v", spec.source_amplitude_v)
    _validate_positive("transient_frequency_hz", spec.transient_frequency_hz)

    circuit = Circuit(f"Hermes Volta {spec.topology}")
    circuit.raw_spice += _source_line(spec)
    output_node = "out"

    if spec.topology == "RC_LOWPASS":
        circuit.R(1, "vin", "out", spec.resistance_ohm @ u_Ω)
        circuit.C(1, "out", circuit.gnd, spec.capacitance_f @ u_F)
    elif spec.topology == "RC_HIGHPASS":
        circuit.C(1, "vin", "out", spec.capacitance_f @ u_F)
        circuit.R(1, "out", circuit.gnd, spec.resistance_ohm @ u_Ω)
    elif spec.topology == "RLC_BANDPASS":
        circuit.L(1, "vin", "n_lc", spec.inductance_h @ u_H)
        circuit.C(1, "n_lc", "out", spec.capacitance_f @ u_F)
        circuit.R(1, "out", circuit.gnd, spec.resistance_ohm @ u_Ω)
    elif spec.topology == "RLC_NOTCH":
        circuit.R(1, "vin", "out", spec.resistance_ohm @ u_Ω)
        circuit.L(1, "out", "n_lc", spec.inductance_h @ u_H)
        circuit.C(1, "n_lc", circuit.gnd, spec.capacitance_f @ u_F)
    elif spec.topology == "RL_LOWPASS":
        circuit.L(1, "vin", "out", spec.inductance_h @ u_H)
        circuit.R(1, "out", circuit.gnd, spec.resistance_ohm @ u_Ω)
    else:  # pragma: no cover - guarded by normalization
        raise AssertionError(spec.topology)

    return circuit, output_node


def _simulator(circuit: Any):
    return circuit.simulator(temperature=TEMPERATURE_C, nominal_temperature=TEMPERATURE_C)


def _to_real_array(values: Any) -> Any:
    np = _load_numpy()
    return np.asarray(values, dtype=float)


def _to_complex_array(values: Any) -> Any:
    np = _load_numpy()
    return np.asarray(values, dtype=complex)


def run_ac(circuit: Any, output_node: str) -> dict[str, Any]:
    """Run ``.ac dec 100 1Hz 1MEGhz`` at 25 C."""
    np = _load_numpy()
    _Circuit, _u_F, _u_H, u_Hz, _u_V, _u_s, _u_Ω = _load_pyspice()
    analysis = _simulator(circuit).ac(
        variation="dec",
        number_of_points=AC_POINTS_PER_DECADE,
        start_frequency=AC_START_HZ @ u_Hz,
        stop_frequency=AC_STOP_HZ @ u_Hz,
    )
    frequency = _to_real_array(analysis.frequency)
    response = _to_complex_array(analysis[output_node])
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), 1e-30))
    phase_deg = np.unwrap(np.angle(response)) * 180.0 / math.pi
    return {
        "frequency_hz": frequency,
        "response": response,
        "magnitude_db": magnitude_db,
        "phase_deg": phase_deg,
    }


def normalize_magnitude(topology: Topology, ac: dict[str, Any]) -> dict[str, Any]:
    """Normalize Bode magnitude so each passive filter passband is 0 dB."""
    np = _load_numpy()
    magnitude_db = np.asarray(ac["magnitude_db"], dtype=float)
    if len(magnitude_db) == 0:
        return ac

    if topology in {"RC_LOWPASS", "RL_LOWPASS"}:
        reference_db = float(magnitude_db[0])
    elif topology == "RC_HIGHPASS":
        reference_db = float(magnitude_db[-1])
    elif topology == "RLC_BANDPASS":
        reference_db = float(np.max(magnitude_db))
    elif topology == "RLC_NOTCH":
        reference_db = float(max(magnitude_db[0], magnitude_db[-1]))
    else:  # pragma: no cover - guarded by topology type
        reference_db = 0.0

    return {**ac, "magnitude_db": magnitude_db - reference_db}


def run_transient(circuit: Any, output_node: str) -> dict[str, Any]:
    """Run transient analysis with 1 us step and 5 ms end time."""
    _Circuit, _u_F, _u_H, _u_Hz, _u_V, u_s, _u_Ω = _load_pyspice()
    analysis = _simulator(circuit).transient(
        step_time=TRANSIENT_STEP_S @ u_s,
        end_time=TRANSIENT_END_S @ u_s,
    )
    return {
        "time_s": _to_real_array(analysis.time),
        "waveform_v": _to_real_array(analysis[output_node]),
    }


def run_transient_window(circuit: Any, output_node: str, step_s: float, end_s: float) -> dict[str, Any]:
    """Run transient analysis with caller-selected step and end time."""
    _Circuit, _u_F, _u_H, _u_Hz, _u_V, u_s, _u_Ω = _load_pyspice()
    analysis = _simulator(circuit).transient(
        step_time=step_s @ u_s,
        end_time=end_s @ u_s,
    )
    return {
        "time_s": _to_real_array(analysis.time),
        "waveform_v": _to_real_array(analysis[output_node]),
    }


def _interpolated_crossing(x: Any, y: Any, target: float) -> float | None:
    for left in range(len(y) - 1):
        y0 = y[left] - target
        y1 = y[left + 1] - target
        if y0 == 0:
            return float(x[left])
        if y0 * y1 <= 0:
            f0 = float(x[left])
            f1 = float(x[left + 1])
            if f0 <= 0 or f1 <= 0:
                return f1
            ratio = abs(y0) / (abs(y0) + abs(y1))
            return float(10 ** (math.log10(f0) + ratio * (math.log10(f1) - math.log10(f0))))
    return None


def actual_frequency(topology: Topology, frequency_hz: Any, magnitude_db: Any) -> float:
    """Extract the simulated characteristic frequency from the Bode magnitude."""
    np = _load_numpy()
    if topology in {"RLC_BANDPASS"}:
        return float(frequency_hz[int(np.argmax(magnitude_db))])
    if topology in {"RLC_NOTCH"}:
        return float(frequency_hz[int(np.argmin(magnitude_db))])

    if topology in {"RC_LOWPASS", "RL_LOWPASS"}:
        passband_db = float(magnitude_db[0])
        crossing = _interpolated_crossing(frequency_hz, magnitude_db, passband_db - 3.0103)
    elif topology == "RC_HIGHPASS":
        passband_db = float(magnitude_db[-1])
        crossing = _interpolated_crossing(frequency_hz, magnitude_db, passband_db - 3.0103)
    else:  # pragma: no cover - guarded by topology type
        crossing = None

    if crossing is not None:
        return crossing
    return float("nan")


def _style_dark_axes(ax: Any) -> None:
    ax.set_facecolor("#0f1117")
    ax.grid(True, which="both", color="#2b3340", alpha=0.75, linewidth=0.7)
    ax.tick_params(colors="#d8dee9")
    for spine in ax.spines.values():
        spine.set_color("#4c566a")
    ax.xaxis.label.set_color("#e5e9f0")
    ax.yaxis.label.set_color("#e5e9f0")
    ax.title.set_color("#eceff4")


def _compact_value(value: float, unit: str) -> str:
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
            return f"{value / scale:.4g}{prefix}{unit}"
    return f"{value:.4g}{unit}"


def _bode_title(topology: Topology, spec: SimulationSpec, actual_fc: float) -> str:
    fc_text = "nanHz" if not math.isfinite(actual_fc) else f"{actual_fc:.4g}Hz"
    frequency_label = "f0" if topology in {"RLC_BANDPASS", "RLC_NOTCH"} else "fc"
    parts = [
        f"{topology} Frequency Response",
        f"{frequency_label}={fc_text}",
        f"R={_compact_value(spec.resistance_ohm, 'Ω')}",
    ]
    if topology in {"RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH"}:
        parts.append(f"C={_compact_value(spec.capacitance_f, 'F')}")
    if topology in {"RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS"}:
        parts.append(f"L={_compact_value(spec.inductance_h, 'H')}")
    return f"{parts[0]} — {' '.join(parts[1:])}"


def _draw_fc_marker(ax: Any, actual_fc: float, frequency: Any, magnitude_db: Any, label: str = "fc") -> None:
    if not math.isfinite(actual_fc) or len(frequency) == 0:
        return
    if actual_fc < float(frequency[0]) or actual_fc > float(frequency[-1]):
        return
    ax.axvline(actual_fc, color="#facc15", linestyle="--", linewidth=1.5, alpha=0.95)
    y_max = float(max(magnitude_db))
    y_min = float(min(magnitude_db))
    y_text = y_max - 0.08 * (y_max - y_min or 1.0)
    ax.text(
        actual_fc,
        y_text,
        f"{label}={actual_fc:.4g} Hz",
        color="#facc15",
        fontsize=9,
        fontweight="bold",
        family="monospace",
        rotation=90,
        va="top",
        ha="right",
        bbox={"facecolor": "#0b0d12", "edgecolor": "#facc15", "alpha": 0.85, "pad": 3},
    )


def plot_bode(ac: dict[str, Any], topology: Topology, output_dir: Path, spec: SimulationSpec, actual_fc: float) -> Path:
    plt = _load_pyplot()
    path = output_dir / "frequency_response.png"
    frequency = ac["frequency_hz"]
    magnitude_db = ac["magnitude_db"]
    phase_deg = ac["phase_deg"]

    fig, (mag_ax, phase_ax) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    fig.patch.set_facecolor("#0b0d12")

    mag_ax.semilogx(frequency, magnitude_db, color="#7dd3fc", linewidth=2.0)
    frequency_label = "f0" if topology in {"RLC_BANDPASS", "RLC_NOTCH"} else "fc"
    _draw_fc_marker(mag_ax, actual_fc, frequency, magnitude_db, label=frequency_label)
    mag_ax.set_title(_bode_title(topology, spec, actual_fc))
    mag_ax.set_ylabel("Magnitude (dB)")
    _style_dark_axes(mag_ax)

    phase_ax.semilogx(frequency, phase_deg, color="#fda4af", linewidth=2.0)
    if math.isfinite(actual_fc) and len(frequency) and float(frequency[0]) <= actual_fc <= float(frequency[-1]):
        phase_ax.axvline(actual_fc, color="#facc15", linestyle="--", linewidth=1.5, alpha=0.95)
    phase_ax.set_xlabel("Frequency (Hz)")
    phase_ax.set_ylabel("Phase (deg)")
    _style_dark_axes(phase_ax)

    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def _steady_amplitude(values: Any) -> float:
    np = _load_numpy()
    data = np.asarray(values, dtype=float)
    if len(data) == 0:
        return 0.0
    start = int(len(data) * 0.25)
    steady = data[start:] if start < len(data) else data
    return float((np.max(steady) - np.min(steady)) / 2.0)


def _format_frequency_label(frequency_hz: float) -> str:
    if abs(frequency_hz) >= 1_000.0:
        value_khz = frequency_hz / 1_000.0
        if abs(value_khz - round(value_khz)) < 0.1 or abs(value_khz) >= 10.0:
            return f"{value_khz:.0f} kHz"
        return f"{value_khz:.1f} kHz"
    return f"{frequency_hz:.0f} Hz"


def _validation_window(frequency_hz: float) -> tuple[float, float]:
    if frequency_hz <= 0 or not math.isfinite(frequency_hz):
        return 5e-3, 1e-6
    time_window_s = max(2e-3, min(0.1, 8.0 / frequency_hz))
    dt_s = 1.0 / (frequency_hz * 150.0)
    return time_window_s, dt_s


def _case(label: str, frequency_hz: float, note: str = "") -> dict[str, Any]:
    end_s, step_s = _validation_window(frequency_hz)
    return {"label": label, "frequency_hz": frequency_hz, "end_s": end_s, "step_s": step_s, "note": note}


def _validation_cases(topology: Topology, actual_fc: float) -> list[dict[str, Any]]:
    characteristic_hz = actual_fc if math.isfinite(actual_fc) and actual_fc > 0 else 1_000.0
    if topology == "RC_LOWPASS":
        pass_freq = 0.1 * characteristic_hz
        reject_freq = 10.0 * characteristic_hz
        return [
            _case(f"Pass test: {_format_frequency_label(pass_freq)} signal passes", pass_freq),
            _case(
                f"Reject test: {_format_frequency_label(reject_freq)} signal gets reduced",
                reject_freq,
                note="High frequency view, compressed time scale",
            ),
        ]
    if topology == "RC_HIGHPASS":
        reject_freq = 0.1 * characteristic_hz
        pass_freq = 10.0 * characteristic_hz
        return [
            _case(f"Reject test: {_format_frequency_label(reject_freq)} drift gets reduced", reject_freq),
            _case(f"Pass test: {_format_frequency_label(pass_freq)} signal passes", pass_freq),
        ]
    if topology == "RLC_BANDPASS":
        low_reject_freq = 0.1 * characteristic_hz
        pass_freq = characteristic_hz
        high_reject_freq = 10.0 * characteristic_hz
        return [
            _case(f"Reject test: {_format_frequency_label(low_reject_freq)} signal gets reduced", low_reject_freq),
            _case(f"Pass test: {_format_frequency_label(pass_freq)} center signal passes", pass_freq),
            _case(
                f"Reject test: {_format_frequency_label(high_reject_freq)} signal gets reduced",
                high_reject_freq,
                note="High frequency view, compressed time scale",
            ),
        ]
    if topology == "RLC_NOTCH":
        low_pass_freq = 0.1 * characteristic_hz
        reject_freq = characteristic_hz
        high_pass_freq = 10.0 * characteristic_hz
        return [
            _case(f"Pass test: {_format_frequency_label(low_pass_freq)} passes", low_pass_freq),
            _case(f"Reject test: {_format_frequency_label(reject_freq)} center gets notched", reject_freq),
            _case(f"Pass test: {_format_frequency_label(high_pass_freq)} passes", high_pass_freq),
        ]
    return []


def _simulate_validation_case(spec: SimulationSpec, case: dict[str, Any]) -> dict[str, Any]:
    validation_spec = SimulationSpec(
        topology=spec.topology,
        resistance_ohm=spec.resistance_ohm,
        capacitance_f=spec.capacitance_f,
        inductance_h=spec.inductance_h,
        source_amplitude_v=spec.source_amplitude_v,
        transient_frequency_hz=float(case["frequency_hz"]),
    )
    circuit, output_node = build_circuit(validation_spec)
    transient = run_transient_window(
        circuit,
        output_node,
        step_s=float(case["step_s"]),
        end_s=float(case["end_s"]),
    )
    return {
        **case,
        "time_s": transient["time_s"],
        "waveform_v": transient["waveform_v"],
    }


def plot_transient_validation(topology: Topology, output_dir: Path, spec: SimulationSpec, actual_fc: float) -> Path:
    plt = _load_pyplot()
    np = _load_numpy()
    path = output_dir / "waveform.png"
    cases = [_simulate_validation_case(spec, case) for case in _validation_cases(topology, actual_fc)]

    fig_width = 16 if len(cases) == 3 else 12
    fig, axes = plt.subplots(1, len(cases), figsize=(fig_width, 4.8))
    if len(cases) == 1:
        axes = [axes]
    fig.patch.set_facecolor("#0b0d12")
    amplitude = spec.source_amplitude_v / 2.0

    for ax, case in zip(axes, cases):
        time_s = np.asarray(case["time_s"], dtype=float)
        time_ms = time_s * 1e3
        vout = np.asarray(case["waveform_v"], dtype=float)
        vin = amplitude * np.sin(2.0 * math.pi * float(case["frequency_hz"]) * time_s)
        attenuation = _steady_amplitude(vout) / (amplitude or 1.0)

        ax.plot(time_ms, vin, color="#94a3b8", linestyle="--", linewidth=1.5, alpha=0.8, label="VIN source")
        ax.plot(time_ms, vout, color="#a7f3d0", linewidth=2.2, label="VOUT real simulation")
        ax.set_title(str(case["label"]))
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Voltage (V)")
        ax.text(
            0.03,
            0.08,
            f"VOUT/VIN ≈ {attenuation:.2f}x",
            transform=ax.transAxes,
            color="#facc15",
            fontsize=10,
            family="monospace",
            bbox={"facecolor": "#0b0d12", "edgecolor": "#facc15", "alpha": 0.78, "pad": 4},
        )
        if case.get("note"):
            ax.text(
                0.03,
                0.20,
                str(case["note"]),
                transform=ax.transAxes,
                color="#cbd5e1",
                fontsize=7.5,
                family="monospace",
                va="bottom",
                bbox={"facecolor": "#0b0d12", "edgecolor": "#475569", "alpha": 0.72, "pad": 3},
            )
        _style_dark_axes(ax)
        ax.legend(loc="upper right", frameon=True, facecolor="#111827", edgecolor="#4c566a", labelcolor="#e5e9f0")

    frequency_label = "f0" if topology in {"RLC_BANDPASS", "RLC_NOTCH"} else "fc"
    frequency_text = "nan Hz" if not math.isfinite(actual_fc) else _format_frequency_label(actual_fc)
    fig.suptitle(
        f"{topology} Transient Validation - real simulation proof - {frequency_label}={frequency_text}",
        color="#eceff4",
        fontsize=15,
    )
    fig.text(
        0.02,
        0.02,
        "VOUT is the real PySpice/Ngspice response to the displayed VIN waveform",
        color="#cbd5e1",
        fontsize=9,
        family="monospace",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def plot_waveform(
    transient: dict[str, Any],
    topology: Topology,
    output_dir: Path,
    spec: SimulationSpec | None = None,
    actual_fc: float | None = None,
) -> Path:
    if spec is not None and topology in {"RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH"}:
        return plot_transient_validation(topology, output_dir, spec, actual_fc or float("nan"))

    plt = _load_pyplot()
    path = output_dir / "waveform.png"
    time_ms = transient["time_s"] * 1e3
    waveform_v = transient["waveform_v"]

    fig, ax = plt.subplots(figsize=(11, 4.8))
    fig.patch.set_facecolor("#0b0d12")
    ax.plot(time_ms, waveform_v, color="#a7f3d0", linewidth=2.0)
    ax.set_title(f"{topology} Transient Waveform")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Output (V)")
    _style_dark_axes(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def run_simulation(
    topology: str,
    resistance_ohm: float = 1_000.0,
    capacitance_f: float = 100e-9,
    inductance_h: float | None = 10e-3,
    source_amplitude_v: float = 1.0,
    transient_frequency_hz: float = 1_000.0,
    output_dir: str | Path = OUTPUT_DIR,
) -> dict[str, Any]:
    """Run AC + transient simulation and generate output plots.

    Returns:
        ``{"actual_fc": float, "bode_path": str, "wave_path": str}``
    """
    spec = SimulationSpec(
        topology=_normalize_topology(topology),
        resistance_ohm=resistance_ohm,
        capacitance_f=capacitance_f,
        inductance_h=inductance_h,
        source_amplitude_v=source_amplitude_v,
        transient_frequency_hz=transient_frequency_hz,
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    circuit, output_node = build_circuit(spec)
    ac = normalize_magnitude(spec.topology, run_ac(circuit, output_node))
    transient = run_transient(circuit, output_node)
    fc = actual_frequency(spec.topology, ac["frequency_hz"], ac["magnitude_db"])
    bode_path = plot_bode(ac, spec.topology, out, spec, fc)
    wave_path = plot_waveform(transient, spec.topology, out, spec, actual_fc=fc)

    return {
        "actual_fc": fc,
        "bode_path": str(bode_path),
        "wave_path": str(wave_path),
    }


def solve_operating_point(*_args: Any, **_kwargs: Any) -> dict[str, complex]:
    """Compatibility shim for the previous lightweight simulator API."""
    raise NotImplementedError("Use run_simulation(topology=...) with the PySpice/Ngspice engine.")


def dc_analysis(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Compatibility shim for the previous lightweight simulator API."""
    raise NotImplementedError("Use run_simulation(topology=...) with the PySpice/Ngspice engine.")


def ac_sweep(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Compatibility shim for the previous lightweight simulator API."""
    raise NotImplementedError("Use run_simulation(topology=...) with the PySpice/Ngspice engine.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Hermes Volta PySpice/Ngspice filter simulations.")
    parser.add_argument(
        "topology",
        choices=["RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS"],
    )
    parser.add_argument("--resistance-ohm", type=float, default=1_000.0)
    parser.add_argument("--capacitance-f", type=float, default=100e-9)
    parser.add_argument("--inductance-h", type=float, default=10e-3)
    parser.add_argument("--source-amplitude-v", type=float, default=1.0)
    parser.add_argument("--transient-frequency-hz", type=float, default=1_000.0)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_simulation(
        topology=args.topology,
        resistance_ohm=args.resistance_ohm,
        capacitance_f=args.capacitance_f,
        inductance_h=args.inductance_h,
        source_amplitude_v=args.source_amplitude_v,
        transient_frequency_hz=args.transient_frequency_hz,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
