#!/usr/bin/env python3
"""Re-runs the Phase 13/post-14 ambiguity-scale sweep at the two larger
geometries `run_scale_stress_test.py` introduced (5x/100 robots,
10x/200 robots), instead of assuming the 2-robot-calibrated
AMBIGUITY_MARGIN_SCALE=0.04 transfers unchanged. Same methodology as
`calibrate_ambiguity_scale.py`: N=20 paired seeds per candidate scale, a
pre-defined selection rule (largest/most-conservative scale where both
quality and cost criteria pass), and a bootstrap 95% CI on the selected
scale's paired difference against always_llm.

    python raca/tools/calibrate_ambiguity_scale_at_larger_geometry.py
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

CANDIDATE_SCALES = [0.001, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05]
N_SEEDS = 20
DURATION_SEC = 300.0
LLM_CONFIG = {"backend": "mock", "fixed_cost": 0.9}

GEOMETRIES = [
    {"name": "5x_warehouse_100_robots", "geom_scale": 5.0, "num_robots": 100},
    {"name": "10x_city_200_robots", "geom_scale": 10.0, "num_robots": 200},
    {"name": "50x_city_1000_robots", "geom_scale": 50.0, "num_robots": 1000},
]


def _start_positions(num_robots: int, geom_scale: float, seed: int) -> dict:
    rng = random.Random(seed * 7919)
    x_bound = 6.5 * geom_scale
    y_bound = 8.5 * geom_scale
    return {
        f"robot{i}": (rng.uniform(-x_bound, x_bound), rng.uniform(-y_bound, y_bound))
        for i in range(1, num_robots + 1)
    }


def run_one(router_name: str, geom: dict, seed: int, ambiguity_scale: float = None) -> dict:
    num_robots = geom["num_robots"]
    _, stations_by_side = build_station_table(geom["geom_scale"])
    robot_ids = [f"robot{i}" for i in range(1, num_robots + 1)]
    router_ref = []

    def factory():
        cfg = {"backend": router_name, "llm_config": LLM_CONFIG}
        if router_name == "adaptive_router" and ambiguity_scale is not None:
            cfg["ambiguity_margin_scale"] = ambiguity_scale
        router = build_backend(cfg)
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=robot_ids, seed=seed, backend_factory=factory,
        start_positions=_start_positions(num_robots, geom["geom_scale"], seed),
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


def run_geometry(geom: dict) -> None:
    print(f"### {geom['name']} (geometry scale={geom['geom_scale']}x, {geom['num_robots']} robots, N={N_SEEDS} paired seeds)\n")

    always_llm_rows = [run_one("always_llm", geom, seed) for seed in range(1, N_SEEDS + 1)]
    always_llm_tasks = [r["tasks_completed"] for r in always_llm_rows]
    mean_always_llm_tasks = statistics.mean(always_llm_tasks)

    header = "| Scale | Mean Tasks (±stdev) | Mean LLM Rate (±stdev) | Quality OK | Cost OK |"
    sep = "|---:|---:|---:|---|---|"
    print(header)
    print(sep)

    results_by_scale = {}
    for scale in CANDIDATE_SCALES:
        rows = [run_one("adaptive_router", geom, seed, ambiguity_scale=scale) for seed in range(1, N_SEEDS + 1)]
        tasks = [r["tasks_completed"] for r in rows]
        rates = [r["llm_invocation_rate"] for r in rows]
        mean_tasks, stdev_tasks = statistics.mean(tasks), statistics.stdev(tasks)
        mean_rate, stdev_rate = statistics.mean(rates), statistics.stdev(rates)
        quality_ok = mean_tasks >= mean_always_llm_tasks - 0.5
        cost_ok = mean_rate < 0.95
        print(
            f"| {scale:.3f} | {mean_tasks:.2f} (±{stdev_tasks:.2f}) | "
            f"{mean_rate:.4f} (±{stdev_rate:.4f}) | {'YES' if quality_ok else 'no'} | {'YES' if cost_ok else 'no'} |"
        )
        results_by_scale[scale] = (quality_ok, cost_ok, tasks, rates)

    print()
    selected = None
    for scale in sorted(CANDIDATE_SCALES, reverse=True):
        quality_ok, cost_ok, _, _ = results_by_scale[scale]
        if quality_ok and cost_ok:
            selected = scale
            break

    if selected is not None:
        _, _, sel_tasks, sel_rates = results_by_scale[selected]
        task_diffs = [a - b for a, b in zip(sel_tasks, always_llm_tasks)]
        rate_diffs = [a - b for a, b in zip(sel_rates, [r["llm_invocation_rate"] for r in always_llm_rows])]
        task_diff_stats = compute_metric_statistics(task_diffs)
        rate_diff_stats = compute_metric_statistics(rate_diffs)
        print(f"SELECTED at this geometry: {selected} (largest scale where both criteria pass)")
        print(f"  paired diff vs always_llm, N={N_SEEDS}: task-count 95% CI [{task_diff_stats['ci95_low']:+.3f}, {task_diff_stats['ci95_high']:+.3f}], "
              f"LLM-rate 95% CI [{rate_diff_stats['ci95_low']:+.4f}, {rate_diff_stats['ci95_high']:+.4f}]")
        print(f"  compare to the 2-robot, scale=1.0 default currently shipped: 0.04")
        if selected != 0.04:
            print(f"  MISMATCH: 0.04 does NOT transfer unchanged to this geometry - the criterion-passing value here is {selected}")
        else:
            print(f"  0.04 happens to also be the criterion-passing value at this geometry")
    else:
        print("SELECTED: none of the candidate scales passed both criteria at this geometry - "
              "the mechanism does not reach the pre-defined cost-reduction bar here at any swept scale.")
    print()


def run() -> int:
    print(f"ambiguity-scale re-calibration at larger geometries: candidates={CANDIDATE_SCALES}, N={N_SEEDS} paired seeds each\n")
    for geom in GEOMETRIES:
        run_geometry(geom)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
