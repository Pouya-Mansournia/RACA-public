#!/usr/bin/env python3
"""Direct measurement of the ambiguity signal's distribution at each
geometry tested in the fleet-scale check (final pre-submission red-team
audit, Critical Audits 3 and 8: verify the 1000-robot "saturation"
hypothesis instead of leaving it speculative, and quantify the
station-density confound instead of leaving it qualitative).

For each geometry, samples a large number of independent (x, y, side)
robot positions uniformly over that geometry's spawn bounds (the same
bounds `run_scale_stress_test.py` and the calibration sweeps use), builds
the exact `RobotObservation` a real decision would use (all stations on
that side assumed free - an approximation of a lightly-loaded world, good
enough to characterize the GEOMETRY's contribution to the margin
distribution independent of any specific run's contention state), and
records `top_two_cost_margin` and `ambiguity` from the real
`DifficultyEstimator`, using each geometry's own SELECTED scale (0.04 at
2 robots, 0.05 at 100/200/1000 robots - not re-tuned here).

    python raca/tools/measure_ambiguity_distribution.py
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.contracts import RobotObservation, StationCandidate  # noqa: E402
from raca_core.difficulty import DifficultyEstimator  # noqa: E402
from raca_core.stations import build_station_table  # noqa: E402

N_SAMPLES = 2000

GEOMETRIES = [
    ("2_robots_original", 1.0, 0.04),
    ("100_robots_5x", 5.0, 0.05),
    ("200_robots_10x", 10.0, 0.05),
    ("1000_robots_50x", 50.0, 0.05),
]


def _station_spacing_stats(geom_scale: float) -> dict:
    _, stations_by_side = build_station_table(geom_scale)
    input_ys = sorted(s[3] for s in stations_by_side["input"])
    gaps = [b - a for a, b in zip(input_ys, input_ys[1:])]
    x_offset = abs(stations_by_side["input"][0][2])
    return {
        "n_stations_per_side": len(input_ys),
        "y_spacing": gaps[0] if gaps else None,
        "x_offset": x_offset,
        "aisle_width_m": 2 * x_offset,
    }


def measure(geom_scale: float, scale: float, seed: int = 0) -> dict:
    _, stations_by_side = build_station_table(geom_scale)
    estimator = DifficultyEstimator(ambiguity_margin_scale=scale)
    rng = random.Random(seed)
    x_bound = 6.5 * geom_scale
    y_bound = 8.5 * geom_scale

    margins = []
    ambiguities = []
    for _ in range(N_SAMPLES):
        side = rng.choice(["input", "output"])
        x = rng.uniform(-x_bound, x_bound)
        y = rng.uniform(-y_bound, y_bound)
        candidates = tuple(
            StationCandidate(name=c[0], side=c[1], x=c[2], y=c[3]) for c in stations_by_side[side]
        )
        observation = RobotObservation(
            robot_id="probe", x=x, y=y, battery_soc=1.0, degradation_risk=0.0,
            utilization=0.0, candidate_stations=candidates,
        )
        context = estimator.estimate(observation)
        if context.top_two_cost_margin is not None:
            margins.append(context.top_two_cost_margin)
        ambiguities.append(context.ambiguity)

    n = len(ambiguities)
    at_zero = sum(1 for a in ambiguities if a == 0.0) / n
    at_one = sum(1 for a in ambiguities if a == 1.0) / n
    strictly_between = 1.0 - at_zero - at_one

    return {
        "n": n,
        "margin_mean": statistics.mean(margins) if margins else None,
        "margin_median": statistics.median(margins) if margins else None,
        "margin_stdev": statistics.stdev(margins) if len(margins) > 1 else None,
        "ambiguity_mean": statistics.mean(ambiguities),
        "ambiguity_median": statistics.median(ambiguities),
        "ambiguity_stdev": statistics.stdev(ambiguities),
        "pct_ambiguity_0": at_zero * 100,
        "pct_ambiguity_1": at_one * 100,
        "pct_ambiguity_between": strictly_between * 100,
    }


def run() -> int:
    print(f"ambiguity/margin distribution measurement, N={N_SAMPLES} sampled decisions per geometry, "
          f"stations assumed all-free (approximates a lightly-loaded world)\n")

    header = "| Geometry | Scale | Stations/side | Aisle width (m) | Mean margin | Mean ambiguity | %amb=0 | %amb=1 | %amb in (0,1) |"
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    print(header)
    print(sep)
    for name, geom_scale, scale in GEOMETRIES:
        spacing = _station_spacing_stats(geom_scale)
        m = measure(geom_scale, scale)
        margin_str = f"{m['margin_mean']:.4f}" if m["margin_mean"] is not None else "n/a"
        print(
            f"| {name} | {scale} | {spacing['n_stations_per_side']} | {spacing['aisle_width_m']:.1f} | "
            f"{margin_str} | {m['ambiguity_mean']:.4f} | {m['pct_ambiguity_0']:.1f}% | "
            f"{m['pct_ambiguity_1']:.1f}% | {m['pct_ambiguity_between']:.1f}% |"
        )

    print()
    print("Interpretation guide: if the 1000-robot saturation hypothesis (Section 6.9/Discussion) is")
    print("correct, the 1000-robot row should show %amb=0 and %amb=1 summing to nearly 100% (almost no")
    print("mass strictly between 0 and 1), while smaller geometries should show substantial mass in (0,1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
