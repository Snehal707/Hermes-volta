"""RC cutoff tolerance Monte Carlo simulation for Hermes Volta.

Used by Hermes Volta subagent C via delegate_task.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
from dataclasses import dataclass


R_TOLERANCE_3SIGMA = 0.05
C_TOLERANCE_3SIGMA = 0.10
DEFAULT_ITERATIONS = 1000
DEFAULT_SEED = 42


@dataclass(frozen=True)
class MonteCarloSummary:
    mean_hz: float
    std_hz: float
    min_hz: float
    max_hz: float
    within_5pct: float


def cutoff_hz(resistance_ohm: float, capacitance_f: float) -> float:
    if resistance_ohm <= 0:
        raise ValueError("R must be positive")
    if capacitance_f <= 0:
        raise ValueError("C must be positive")
    return 1.0 / (2.0 * math.pi * resistance_ohm * capacitance_f)


def run_monte_carlo(
    resistance_ohm: float,
    capacitance_f: float,
    target_fc_hz: float,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int = DEFAULT_SEED,
) -> MonteCarloSummary:
    if target_fc_hz <= 0:
        raise ValueError("--fc must be positive")
    if iterations <= 0:
        raise ValueError("--n must be positive")

    rng = random.Random(seed)
    r_sigma = R_TOLERANCE_3SIGMA / 3.0
    c_sigma = C_TOLERANCE_3SIGMA / 3.0
    values: list[float] = []

    for _ in range(iterations):
        varied_r = resistance_ohm * (1.0 + rng.gauss(0.0, r_sigma))
        varied_c = capacitance_f * (1.0 + rng.gauss(0.0, c_sigma))
        if varied_r <= 0 or varied_c <= 0:
            continue
        values.append(cutoff_hz(varied_r, varied_c))

    lower = target_fc_hz * 0.95
    upper = target_fc_hz * 1.05
    within = sum(1 for value in values if lower <= value <= upper)

    return MonteCarloSummary(
        mean_hz=statistics.fmean(values),
        std_hz=statistics.stdev(values) if len(values) > 1 else 0.0,
        min_hz=min(values),
        max_hz=max(values),
        within_5pct=(within / len(values)) * 100.0,
    )


def print_summary(summary: MonteCarloSummary, iterations: int) -> None:
    print(f"Monte Carlo iterations: {iterations}")
    print(f"Mean fc: {summary.mean_hz:.6g} Hz")
    print(f"Std fc: {summary.std_hz:.6g} Hz")
    print(f"Min fc: {summary.min_hz:.6g} Hz")
    print(f"Max fc: {summary.max_hz:.6g} Hz")
    print(f"Within ±5% of target: {summary.within_5pct:.2f}%")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run RC cutoff Monte Carlo tolerance simulation.")
    parser.add_argument("--R", type=float, required=True, help="nominal resistance in ohms")
    parser.add_argument("--C", type=float, required=True, help="nominal capacitance in farads")
    parser.add_argument("--fc", type=float, required=True, help="target cutoff frequency in Hz")
    parser.add_argument("--n", type=int, default=DEFAULT_ITERATIONS, help="iteration count")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_monte_carlo(args.R, args.C, args.fc, args.n)
    print_summary(summary, args.n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
