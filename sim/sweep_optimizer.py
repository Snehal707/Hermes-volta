"""E24 resistor sweep for minimum RC cutoff-frequency error.

Used by Hermes Volta subagent A via delegate_task.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass


E24_BASE = (
    10,
    11,
    12,
    13,
    15,
    16,
    18,
    20,
    22,
    24,
    27,
    30,
    33,
    36,
    39,
    43,
    47,
    51,
    56,
    62,
    68,
    75,
    82,
    91,
)


@dataclass(frozen=True)
class SweepResult:
    resistance_ohm: float
    actual_fc_hz: float
    error_pct: float


def e24_values(min_ohm: float = 100.0, max_ohm: float = 100_000.0) -> list[float]:
    """Return all E24 resistor values from 100 ohm through 100 kohm."""
    values: list[float] = []
    decade = 1.0
    while decade <= max_ohm * 10:
        for base in E24_BASE:
            value = base * decade
            if min_ohm <= value <= max_ohm:
                values.append(float(value))
        decade *= 10.0
    return sorted(set(values))


def cutoff_hz(resistance_ohm: float, capacitance_f: float) -> float:
    if resistance_ohm <= 0:
        raise ValueError("R must be positive")
    if capacitance_f <= 0:
        raise ValueError("C must be positive")
    return 1.0 / (2.0 * math.pi * resistance_ohm * capacitance_f)


def sweep_resistors(target_fc_hz: float, capacitance_f: float, limit: int = 5) -> list[SweepResult]:
    if target_fc_hz <= 0:
        raise ValueError("--fc must be positive")
    rows = []
    for resistance in e24_values():
        actual_fc = cutoff_hz(resistance, capacitance_f)
        error_pct = abs((actual_fc - target_fc_hz) / target_fc_hz) * 100.0
        rows.append(SweepResult(resistance, actual_fc, error_pct))
    rows.sort(key=lambda item: item.error_pct)
    return rows[:limit]


def find_best_e24_r(fc: float, C: float) -> float:
    """Return the E24 resistor value whose RC cutoff is closest to fc."""
    if fc <= 0:
        raise ValueError("fc must be positive")
    if C <= 0:
        raise ValueError("C must be positive")
    return min(e24_values(), key=lambda resistance: abs(cutoff_hz(resistance, C) - fc))


def _format_ohms(value: float) -> str:
    if value >= 1_000:
        return f"{value / 1_000:g} kΩ"
    return f"{value:g} Ω"


def print_results(results: list[SweepResult]) -> None:
    best = results[0]
    print(f"Best R: {_format_ohms(best.resistance_ohm)}")
    print(f"Actual fc: {best.actual_fc_hz:.6g} Hz")
    print(f"Error: {best.error_pct:.3f}%")
    print()
    print("Top 5 E24 candidates")
    print("Rank | R | actual fc (Hz) | error %")
    print("-----|---|----------------|--------")
    for rank, row in enumerate(results, start=1):
        print(f"{rank:>4} | {_format_ohms(row.resistance_ohm):>8} | {row.actual_fc_hz:>14.6g} | {row.error_pct:>7.3f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep E24 resistor values for minimum RC cutoff error.")
    parser.add_argument("--fc", type=float, required=True, help="target cutoff frequency in Hz")
    parser.add_argument("--C", type=float, required=True, help="capacitance in farads")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print_results(sweep_resistors(args.fc, args.C))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
