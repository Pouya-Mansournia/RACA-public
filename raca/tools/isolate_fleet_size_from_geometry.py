#!/usr/bin/env python3
"""True fleet-size/geometry isolation experiment (final pre-submission
checklist item 3, the one thing not yet run: previous fleet-scale checks
always varied robot count and spatial scale TOGETHER at a fixed 1:1
ratio, so the two variables were perfectly confounded).

This script runs a small factorial grid: 3 geometry scales x 3 robot
counts, ALL NINE combinations, holding AMBIGUITY_MARGIN_SCALE fixed at
0.05 throughout (the value the recalibration sweep found valid at every
geometry tested so far) so the routing parameter itself isn't a second
confound. N=20 paired seeds per cell, MockBackend.

    python raca/tools/isolate_fleet_size_from_geometry.py
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.config import build_backend  # noqa: E402
from raca_core.stats import compute_metric_statistics  # noqa: E402
from raca_core.stations import build_station_table  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

N_SEEDS = 20
DURATION_SEC = 120.0
LLM_CONFIG = {"backend": "mock", "fixed_cost": 0.9}
SCALE = 0.05  # held fixed across the whole grid - see module docstring

GEOM_SCALES = [1.0, 5.0, 20.0]
ROBOT_COUNTS = [2, 20, 100]


def _start_positions(num_robots: int, geom_scale: float, seed: int) -> dict:
    rng = random.Random(seed * 7919)
    x_bound = 6.5 * geom_scale
    y_bound = 8.5 * geom_scale
    return {
        f"robot{i}": (rng.uniform(-x_bound, x_bound), rng.uniform(-y_bound, y_bound))
        for i in range(1, num_robots + 1)
    }


def run_one(router_name: str, num_robots: int, geom_scale: float, seed: int) -> dict:
    _, stations_by_side = build_station_table(geom_scale)
    robot_ids = [f"robot{i}" for i in range(1, num_robots + 1)]
    router_ref = []

    def factory():
        cfg = {"backend": router_name, "llm_config": LLM_CONFIG}
        if router_name == "adaptive_router":
            cfg["ambiguity_margin_scale"] = SCALE
        router = build_backend(cfg)
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=robot_ids, seed=seed, backend_factory=factory,
        start_positions=_start_positions(num_robots, geom_scale, seed),
        stations_by_side=stations_by_side,
    )
    world.run_until(DURATION_SEC)
    summary = world.summary()
    total_llm = sum(getattr(r, "stats", None).llm_decisions for r in router_ref if hasattr(r, "stats"))
    total_calls = sum(getattr(r, "stats", None).total for r in router_ref if hasattr(r, "stats"))
    return {
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else 0.0,
    }


def run_cell(geom_scale: float, num_robots: int) -> dict:
    adaptive_rows = [run_one("adaptive_router", num_robots, geom_scale, s) for s in range(1, N_SEEDS + 1)]
    always_llm_rows = [run_one("always_llm", num_robots, geom_scale, s) for s in range(1, N_SEEDS + 1)]

    adaptive_rates = [r["llm_invocation_rate"] for r in adaptive_rows]
    always_llm_rates = [r["llm_invocation_rate"] for r in always_llm_rows]
    rate_diffs = [a - b for a, b in zip(adaptive_rates, always_llm_rates)]
    rate_stats = compute_metric_statistics(rate_diffs)

    return {
        "mean_adaptive_rate": statistics.mean(adaptive_rates),
        "mean_rate_diff": statistics.mean(rate_diffs),
        "ci_low": rate_stats["ci95_low"],
        "ci_high": rate_stats["ci95_high"],
    }


def run() -> int:
    print(f"fleet-size / geometry isolation: {len(GEOM_SCALES)}x{len(ROBOT_COUNTS)} factorial grid, "
          f"N={N_SEEDS} paired seeds/cell, AMBIGUITY_MARGIN_SCALE fixed at {SCALE}, MockBackend\n")

    results = {}
    header = "| Geometry scale \\ Robots | " + " | ".join(f"{n}" for n in ROBOT_COUNTS) + " |"
    sep = "|---|" + "---:|" * len(ROBOT_COUNTS)
    print("### Mean adaptive_router LLM invocation rate (%)\n")
    print(header)
    print(sep)
    for gs in GEOM_SCALES:
        row = []
        for rc in ROBOT_COUNTS:
            cell = run_cell(gs, rc)
            results[(gs, rc)] = cell
            row.append(f"{cell['mean_adaptive_rate']*100:.1f}")
        print(f"| {gs}x | " + " | ".join(row) + " |")

    print()
    print("### Paired LLM-rate diff vs always_llm, 95% bootstrap CI (percentage points)\n")
    print(header)
    print(sep)
    for gs in GEOM_SCALES:
        row = []
        for rc in ROBOT_COUNTS:
            cell = results[(gs, rc)]
            row.append(f"{cell['mean_rate_diff']*100:+.1f} [{cell['ci_low']*100:+.1f},{cell['ci_high']*100:+.1f}]")
        print(f"| {gs}x | " + " | ".join(row) + " |")

    print()
    print("Interpretation: read ACROSS a row (fixed geometry, varying robot count) to isolate the")
    print("fleet-size effect. Read DOWN a column (fixed robot count, varying geometry) to isolate")
    print("the geometry effect. If a row is roughly flat while columns vary a lot, the effect is")
    print("geometry-driven, not fleet-size-driven (or vice versa).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
