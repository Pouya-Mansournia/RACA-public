#!/usr/bin/env python3
"""Held-out confirmatory re-evaluation of the ambiguity-scale recalibration
(final pre-submission red-team audit, Critical Audit 1 / BLOCKING item 2).

The original recalibration sweeps (`calibrate_ambiguity_scale.py` and
`calibrate_ambiguity_scale_at_larger_geometry.py`) select a scale value
AND report that value's bootstrap CI using the SAME N=20 seed set
(seeds 1-20), which is optimistic relative to a true held-out test. This
script takes the ALREADY-SELECTED scale for each geometry (not re-tuned
here - that would defeat the point) and evaluates it on a fresh, disjoint
seed range (1001-1020) never used in any prior sweep or campaign in this
project, reporting the same paired-difference bootstrap CI for direct
comparison against the in-sample number.

    python raca/tools/holdout_reevaluate_ambiguity_scale.py
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
HELD_OUT_SEED_START = 1001  # disjoint from seeds 1-20 used by every tuning sweep
DURATION_SEC = 60.0
LLM_CONFIG = {"backend": "mock", "fixed_cost": 0.9}

# (geometry name, geom_scale, num_robots, selected scale, in-sample LLM-rate-diff CI, duration)
GEOMETRIES = [
    ("2_robots_original", 1.0, 2, 0.04, (-7.9, -2.6), 60.0),
    ("100_robots_5x", 5.0, 100, 0.05, (-11.6, -6.7), 300.0),
    ("200_robots_10x", 10.0, 200, 0.05, (-16.4, -9.4), 300.0),
    ("1000_robots_50x", 50.0, 1000, 0.05, (-30.0, -14.1), 300.0),
]


def _start_positions(num_robots: int, geom_scale: float, seed: int) -> dict:
    rng = random.Random(seed * 7919)
    x_bound = 6.5 * geom_scale
    y_bound = 8.5 * geom_scale
    return {
        f"robot{i}": (rng.uniform(-x_bound, x_bound), rng.uniform(-y_bound, y_bound))
        for i in range(1, num_robots + 1)
    }


def run_one(router_name: str, num_robots: int, geom_scale: float, seed: int, scale: float, duration: float) -> dict:
    _, stations_by_side = build_station_table(geom_scale)
    robot_ids = [f"robot{i}" for i in range(1, num_robots + 1)]
    router_ref = []

    def factory():
        cfg = {"backend": router_name, "llm_config": LLM_CONFIG}
        if router_name == "adaptive_router":
            cfg["ambiguity_margin_scale"] = scale
        router = build_backend(cfg)
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=robot_ids, seed=seed, backend_factory=factory,
        start_positions=_start_positions(num_robots, geom_scale, seed),
        stations_by_side=stations_by_side,
    )
    world.run_until(duration)
    summary = world.summary()
    total_llm = sum(getattr(r, "stats", None).llm_decisions for r in router_ref if hasattr(r, "stats"))
    total_calls = sum(getattr(r, "stats", None).total for r in router_ref if hasattr(r, "stats"))
    return {
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else 0.0,
    }


def run() -> int:
    print(f"held-out confirmatory re-evaluation: seeds {HELD_OUT_SEED_START}-{HELD_OUT_SEED_START + N_SEEDS - 1} "
          f"(disjoint from seeds 1-20 used to select every scale below)\n")

    for name, geom_scale, num_robots, scale, in_sample_ci, duration in GEOMETRIES:
        print(f"### {name} (selected scale={scale}, geometry scale={geom_scale}x, {num_robots} robots)\n")
        seeds = range(HELD_OUT_SEED_START, HELD_OUT_SEED_START + N_SEEDS)
        adaptive_rows = [run_one("adaptive_router", num_robots, geom_scale, s, scale, duration) for s in seeds]
        always_llm_rows = [run_one("always_llm", num_robots, geom_scale, s, scale, duration) for s in seeds]

        adaptive_tasks = [r["tasks_completed"] for r in adaptive_rows]
        always_llm_tasks = [r["tasks_completed"] for r in always_llm_rows]
        task_diffs = [a - b for a, b in zip(adaptive_tasks, always_llm_tasks)]

        adaptive_rates = [r["llm_invocation_rate"] for r in adaptive_rows]
        always_llm_rates = [r["llm_invocation_rate"] for r in always_llm_rows]
        rate_diffs = [a - b for a, b in zip(adaptive_rates, always_llm_rates)]

        task_stats = compute_metric_statistics(task_diffs)
        rate_stats = compute_metric_statistics(rate_diffs)

        print(f"  held-out N=20, task-count diff: mean {statistics.mean(task_diffs):+.3f}, "
              f"95% CI [{task_stats['ci95_low']:+.3f}, {task_stats['ci95_high']:+.3f}]")
        print(f"  held-out N=20, LLM-rate diff:   mean {statistics.mean(rate_diffs):+.4f}, "
              f"95% CI [{rate_stats['ci95_low']:+.4f}, {rate_stats['ci95_high']:+.4f}] "
              f"({rate_stats['ci95_low']*100:+.1f}pp to {rate_stats['ci95_high']*100:+.1f}pp)")
        print(f"  in-sample (tuning-seed) CI was: [{in_sample_ci[0]:+.1f}pp, {in_sample_ci[1]:+.1f}pp]")
        holds = rate_stats['ci95_high'] * 100 < 0
        print(f"  [{'CONFIRMED' if holds else 'NOT CONFIRMED'}] held-out CI stays below zero (cost reduction generalizes beyond the tuning seeds)")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
