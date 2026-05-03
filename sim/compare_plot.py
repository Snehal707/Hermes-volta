"""Generate explanatory input/output comparison plots for Hermes Volta designs."""

import argparse
import math
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any

_REPO_BOOT = Path(__file__).resolve().parents[1]
if str(_REPO_BOOT) not in sys.path:
    sys.path.insert(0, str(_REPO_BOOT))

from sim.volta_paths import prepend_sim_import_helpers, project_root_path  # noqa: E402

prepend_sim_import_helpers()
PROJECT_ROOT = project_root_path()


OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SUPPORTED_CIRCUITS = ("RC_LOWPASS", "RC_HIGHPASS", "RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS")


def _style_axis(ax: Any) -> None:
    ax.set_facecolor("#06110b")
    ax.grid(True, color="#1f8f4f", alpha=0.26, linewidth=0.75)
    for spine in ax.spines.values():
        spine.set_color("#66ff99")
        spine.set_alpha(0.45)
    ax.tick_params(colors="#b7ffd0")
    ax.xaxis.label.set_color("#b7ffd0")
    ax.yaxis.label.set_color("#b7ffd0")
    ax.title.set_color("#b7ffd0")
    ax.title.set_fontsize(15)


def _transient_response(
    circuit_type: str,
    R: float,
    C: float,
    supply_v: float,
    transient_frequency_hz: float,
    transient_end_s: float | None = None,
    transient_step_s: float | None = None,
    L: float | None = None,
) -> tuple[Any, Any]:
    from sim import simulate

    normalized = circuit_type.upper().replace("-", "_")
    inductance_h = L if L is not None else (10e-3 if normalized in {"RLC_BANDPASS", "RLC_NOTCH", "RL_LOWPASS"} else None)
    spec = simulate.SimulationSpec(
        topology=simulate._normalize_topology(normalized),
        resistance_ohm=R,
        capacitance_f=C,
        inductance_h=inductance_h,
        source_amplitude_v=supply_v,
        transient_frequency_hz=transient_frequency_hz,
    )
    circuit, output_node = simulate.build_circuit(spec)
    if transient_end_s is None:
        transient = simulate.run_transient(circuit, output_node)
    else:
        _Circuit, _u_F, _u_H, _u_Hz, _u_V, u_s, _u_ohm = simulate._load_pyspice()
        step_s = transient_step_s or 20e-6
        analysis = simulate._simulator(circuit).transient(
            step_time=step_s @ u_s,
            end_time=transient_end_s @ u_s,
        )
        transient = {
            "time_s": simulate._to_real_array(analysis.time),
            "waveform_v": simulate._to_real_array(analysis[output_node]),
        }
    return transient["time_s"], transient["waveform_v"]


def _simulate_response_from_vin(
    circuit_type: str,
    R: float,
    C: float,
    time_s: Any,
    vin_v: Any,
    transient_step_s: float,
    transient_end_s: float,
    L: float | None = None,
) -> Any:
    """Return VOUT from a real Ngspice transient run driven by displayed VIN."""
    from sim import simulate

    Circuit, u_F, u_H, _u_Hz, _u_V, u_s, u_ohm = simulate._load_pyspice()

    normalized = _normalize_circuit_type(circuit_type)
    circuit = Circuit(f"Hermes Volta {normalized} compare plot")
    circuit.PieceWiseLinearVoltageSource(
        "input",
        "vin",
        circuit.gnd,
        values=[(float(t), float(v)) for t, v in zip(time_s, vin_v)],
        dc=float(vin_v[0]),
    )

    if normalized == "RC_LOWPASS":
        circuit.R(1, "vin", "out", float(R) @ u_ohm)
        circuit.C(1, "out", circuit.gnd, float(C) @ u_F)
    elif normalized == "RC_HIGHPASS":
        circuit.C(1, "vin", "out", float(C) @ u_F)
        circuit.R(1, "out", circuit.gnd, float(R) @ u_ohm)
    elif normalized == "RLC_NOTCH":
        inductance_h = float(L) if L is not None else 10e-3
        circuit.R(1, "vin", "out", float(R) @ u_ohm)
        circuit.L(1, "out", "n_lc", inductance_h @ u_H)
        circuit.C(1, "n_lc", circuit.gnd, float(C) @ u_F)
    else:  # pragma: no cover - guarded by caller
        raise ValueError(f"unsupported compare topology {circuit_type!r}")

    analysis = simulate._simulator(circuit).transient(
        step_time=transient_step_s @ u_s,
        end_time=transient_end_s @ u_s,
    )
    return simulate._to_real_array(analysis["out"])


def _normalize_circuit_type(circuit_type: str) -> str:
    return circuit_type.upper().replace("-", "_")


def _transient_frequency(circuit_type: str, fc: float) -> float:
    normalized = _normalize_circuit_type(circuit_type)
    if normalized == "RC_LOWPASS":
        return fc * 0.1 if fc > 0 else 100.0
    if normalized == "RC_HIGHPASS":
        return fc * 10.0 if fc > 0 else 1_000.0
    if normalized == "RLC_BANDPASS":
        return max(fc, 20.0) if fc > 0 else 1_000.0
    if normalized == "RLC_NOTCH":
        return max(fc, 1.0) if fc > 0 else 1_000.0
    return 1_000.0


def _transient_window(circuit_type: str) -> tuple[float | None, float | None]:
    normalized = _normalize_circuit_type(circuit_type)
    if normalized == "RC_LOWPASS":
        return 100e-3, 20e-6
    if normalized == "RC_HIGHPASS":
        return 5e-3, 1e-6
    if normalized == "RLC_NOTCH":
        return 100e-3, 20e-6
    return None, None


def _format_story_frequency(frequency_hz: float) -> str:
    if frequency_hz >= 1_000.0:
        value_khz = frequency_hz / 1_000.0
        if value_khz >= 9.95:
            return f"{value_khz:.0f}kHz"
        return f"{value_khz:.1f}kHz"
    return f"{frequency_hz:.0f}Hz"


def _lowpass_noise_frequency(fc: float, signal_frequency_hz: float) -> float:
    return fc * 3.0 if fc > 0 else signal_frequency_hz * 30.0


def _demo_signals(
    circuit_type: str,
    time_s: Any,
    amplitude: float,
    signal_frequency_hz: float,
    fc: float,
) -> tuple[Any, Any, str, str]:
    import numpy as np

    normalized = _normalize_circuit_type(circuit_type)
    clean = amplitude * np.sin(2.0 * math.pi * signal_frequency_hz * time_s)

    if normalized == "RC_LOWPASS":
        noise_frequency_hz = _lowpass_noise_frequency(fc, signal_frequency_hz)
        high_noise = 0.34 * amplitude * np.sin(2.0 * math.pi * noise_frequency_hz * time_s)
        high_noise += 0.16 * amplitude * np.sign(np.sin(2.0 * math.pi * noise_frequency_hz * time_s))
        spike_train = np.maximum(0.0, np.sin(2.0 * math.pi * noise_frequency_hz * time_s)) ** 16
        noisy = clean + high_noise + 0.24 * amplitude * spike_train
        return (
            clean,
            noisy,
            "high frequency noise removed, slow signal preserved",
            "VIN noisy: slow sine + high-frequency noise spikes",
        )

    if normalized == "RC_HIGHPASS":
        drift_frequency_hz = fc * 0.01 if fc > 0 else max(signal_frequency_hz / 1_000.0, 0.1)
        drift = 0.45 * amplitude
        drift += 0.32 * amplitude * np.sin(2.0 * math.pi * drift_frequency_hz * time_s + 0.4)
        noisy = clean + drift
        return (
            clean,
            noisy,
            "slow drift and DC offset removed, fast signal preserved",
            "VIN noisy: fast sine + DC offset and slow baseline drift",
        )

    if normalized == "RLC_BANDPASS":
        low_component = 0.45 * amplitude * np.sin(2.0 * math.pi * max(signal_frequency_hz / 6.0, 1.0) * time_s + 0.5)
        high_component = 0.28 * amplitude * np.sin(2.0 * math.pi * signal_frequency_hz * 7.0 * time_s)
        noisy = clean + low_component + high_component
        return (
            clean,
            noisy,
            "only center frequency preserved",
            "VIN noisy: center signal plus low and high frequency components",
        )

    if normalized == "RLC_NOTCH":
        low_component = 0.45 * amplitude * np.sin(2.0 * math.pi * max(signal_frequency_hz / 4.0, 1.0) * time_s + 0.4)
        high_component = 0.34 * amplitude * np.sin(2.0 * math.pi * signal_frequency_hz * 4.0 * time_s + 0.8)
        noisy = clean + low_component + high_component
        return (
            clean,
            noisy,
            "center frequency rejected, off-notch content preserved",
            "VIN mixed: notch frequency plus lower and higher components",
        )

    noise = 0.18 * amplitude * np.sin(2.0 * math.pi * signal_frequency_hz * 17.0 * time_s)
    noise += 0.08 * amplitude * np.sin(2.0 * math.pi * signal_frequency_hz * 31.0 * time_s + 0.9)
    return clean, clean + noise, "filter removes the rejected band", "VIN noisy: clean signal plus out-of-band content"


def _panel_copy(circuit_type: str) -> tuple[str, str, str, str, str]:
    normalized = _normalize_circuit_type(circuit_type)
    if normalized == "RC_LOWPASS":
        return (
            "VIN: Noisy Input",
            "VIN noisy — high-freq noise present",
            "VOUT: Filtered Output (real simulation)",
            "VOUT filtered — simulated from displayed VIN",
            "High-frequency content blocked by filter",
        )
    if normalized == "RC_HIGHPASS":
        return (
            "VIN: Input With Slow Drift",
            "VIN noisy — slow drift present",
            "VOUT: Filtered Output (real simulation)",
            "VOUT filtered — simulated from displayed VIN",
            "Difference signal: VIN minus VOUT",
        )
    if normalized == "RLC_NOTCH":
        return (
            "VIN: Mixed Input With f0 Component",
            "VIN mixed — f0 plus off-notch components",
            "VOUT: Notch Filter Output (real simulation)",
            "VOUT filtered — f0 removed",
            "Rejected notch frequency content",
        )
    return (
        "VIN: Noisy Input",
        "VIN noisy — unwanted content present",
        "VOUT: Filtered Output (real simulation)",
        "VOUT filtered",
        "Rejected content blocked by filter",
    )


def generate_compare_plot(
    output_dir: str,
    circuit_type: str,
    R: float,
    C: float,
    fc: float,
    supply_v: float,
    L: float | None = None,
) -> Path:
    """Save ``compare_plot.png`` in ``output_dir`` and return its path."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "compare_plot.png"
    normalized = _normalize_circuit_type(circuit_type)
    transient_frequency_hz = _transient_frequency(normalized, fc)
    transient_end_s, transient_step_s = _transient_window(normalized)

    amplitude = supply_v / 2.0
    if normalized in {"RC_LOWPASS", "RC_HIGHPASS", "RLC_NOTCH"} and transient_end_s is not None:
        step_s = transient_step_s or 1e-6
        time_s = np.arange(0.0, transient_end_s + step_s / 2.0, step_s, dtype=float)
        vin_clean, vin_noisy, story, noisy_label = _demo_signals(
            normalized,
            time_s,
            amplitude,
            transient_frequency_hz,
            fc,
        )
        vout = _simulate_response_from_vin(normalized, R, C, time_s, vin_noisy, step_s, transient_end_s, L=L)
        vout = np.asarray(vout, dtype=float)
        if len(vout) != len(time_s):
            sample_count = min(len(vout), len(time_s))
            time_s = time_s[:sample_count]
            vin_clean = vin_clean[:sample_count]
            vin_noisy = vin_noisy[:sample_count]
            vout = vout[:sample_count]
    else:
        time_s, vout = _transient_response(
            normalized,
            R,
            C,
            supply_v,
            transient_frequency_hz,
            transient_end_s=transient_end_s,
            transient_step_s=transient_step_s,
            L=L,
        )
        time_s = np.asarray(time_s, dtype=float)
        vout = np.asarray(vout, dtype=float)
        vin_clean, vin_noisy, story, noisy_label = _demo_signals(
            normalized,
            time_s,
            amplitude,
            transient_frequency_hz,
            fc,
        )

    fig, axes = plt.subplots(
        nrows=3,
        ncols=1,
        sharex=normalized != "RC_LOWPASS",
        figsize=(13.5, 8.0),
        facecolor="#020403",
        gridspec_kw={"height_ratios": (1.0, 1.0, 0.78), "hspace": 0.16},
    )
    fig.subplots_adjust(left=0.075, right=0.97, top=0.9, bottom=0.14)
    for axis in axes:
        _style_axis(axis)

    time_ms = time_s * 1e3
    removed = vin_noisy - vout
    if normalized == "RLC_NOTCH":
        removed = vin_clean
    vin_title, vin_label, vout_title, vout_label, removed_label = _panel_copy(normalized)

    axes[0].plot(time_ms, vin_noisy, color="#ff6600", linewidth=1.2, label=vin_label)
    axes[0].set_title(vin_title)
    axes[0].set_ylabel("VIN (V)")
    axes[0].legend(loc="upper right", frameon=True, facecolor="#06110b", edgecolor="#66ff99", labelcolor="#d1fae5")

    axes[1].plot(time_ms, vout, color="#00ff88", linewidth=2.1, label=vout_label)
    axes[1].set_title(vout_title)
    axes[1].set_ylabel("VOUT (V)")
    axes[1].legend(loc="upper right", frameon=True, facecolor="#06110b", edgecolor="#66ff99", labelcolor="#d1fae5")

    noise_linewidth = 1.0 if normalized == "RC_LOWPASS" else 0.8
    axes[2].plot(time_ms, removed, color="#ff3333", linewidth=noise_linewidth, label=removed_label)
    if normalized == "RC_LOWPASS":
        axes[0].set_xlim(0.0, 100.0)
        axes[1].set_xlim(0.0, 100.0)
        axes[2].set_xlim(0.0, 10.0)
        axes[2].set_xlabel("Time (ms) — zoomed to show noise detail")
    elif normalized == "RLC_NOTCH":
        axes[0].set_xlim(0.0, 100.0)
        axes[1].set_xlim(0.0, 100.0)
        axes[2].set_xlim(0.0, 100.0)
        axes[2].set_xlabel("Time (ms)")
    else:
        axes[2].set_xlabel("Time (ms)")
    if normalized == "RC_LOWPASS":
        axes[2].set_title("High-Frequency Content Blocked")
    elif normalized == "RC_HIGHPASS":
        axes[2].set_title("Difference Signal: VIN Minus VOUT")
    elif normalized == "RLC_NOTCH":
        axes[2].set_title("Rejected Notch Frequency Content")
    else:
        axes[2].set_title("Rejected Content Blocked")
    axes[2].set_ylabel("Difference (V)" if normalized == "RC_HIGHPASS" else "Blocked (V)")
    axes[2].legend(loc="upper right", frameon=True, facecolor="#06110b", edgecolor="#66ff99", labelcolor="#d1fae5")

    axes[0].tick_params(labelbottom=False)
    axes[1].tick_params(labelbottom=False)
    for axis in axes:
        axis.margins(x=0.025, y=0.12)

    frequency_label = "f0" if normalized in {"RLC_BANDPASS", "RLC_NOTCH"} else "fc"
    fig.suptitle(
        f"{normalized} Filter Effect — {frequency_label}={fc:.0f}Hz",
        color="#f7ff9a",
        fontsize=16,
        fontweight="bold",
    )

    footer_text = (
        "VOUT is the real PySpice/Ngspice response to the displayed VIN waveform"
        if normalized in {"RC_LOWPASS", "RC_HIGHPASS", "RLC_NOTCH"}
        else "VOUT is from real PySpice/Ngspice simulation"
    )
    fig.text(
        0.075,
        0.055,
        textwrap.fill(footer_text, width=120),
        color="#b7ffd0",
        fontsize=10,
        family="monospace",
        va="bottom",
        bbox={"facecolor": "#020403", "edgecolor": "#1f8f4f", "alpha": 0.82, "pad": 6},
    )
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    canonical_output_path = OUTPUTS_DIR / "compare_plot.png"
    if path.resolve() != canonical_output_path.resolve():
        shutil.copy2(path, canonical_output_path)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Hermes Volta VIN vs VOUT comparison plot.")
    parser.add_argument("--output_dir", "--output-dir", required=True, help="Directory that receives compare_plot.png.")
    parser.add_argument("--circuit_type", "--circuit-type", required=True, choices=SUPPORTED_CIRCUITS)
    parser.add_argument("--R", type=float, required=True, help="Resistance in ohms.")
    parser.add_argument("--C", type=float, required=True, help="Capacitance in farads.")
    parser.add_argument("--L", type=float, default=None, help="Inductance in henries for RLC filters.")
    parser.add_argument("--fc", type=float, required=True, help="Cutoff frequency, or f0 center frequency for RLC filters, in Hz.")
    parser.add_argument("--supply_v", "--supply-v", type=float, default=5.0, help="Supply voltage.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = generate_compare_plot(
        output_dir=args.output_dir,
        circuit_type=args.circuit_type,
        R=args.R,
        C=args.C,
        L=args.L,
        fc=args.fc,
        supply_v=args.supply_v,
    )
    print(f"compare_plot: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
