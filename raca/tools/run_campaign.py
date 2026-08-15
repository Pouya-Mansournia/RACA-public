#!/usr/bin/env python3
"""Phase 13 - Large-Scale Campaign (master prompt PHASE 13).

Runs 3 routing strategies (Always-Deterministic, Always-LLM, RACA V1
AdaptiveRouter) across N paired seeds with varied, non-symmetric robot
start positions (Phase 6/7's own documented requirement for a meaningful
comparison), using the lightweight simulator so this scale is actually
feasible - the historical Gazebo/ROS line's own documented cost (~20-40
minutes wall-clock per short run, docs/current_limitations.md) made
anything past a 2-4 seed pilot infeasible; this world runs 20 paired seeds
in well under a minute.

SCOPE STATEMENT (read before interpreting results): the `llm` role here is
`MockBackend`, not a real model call. This is a deliberate choice for a
run at this N - Phases 4/6/7/9/10 already validated real local-model
behavior (latency, validity, domain sensitivity) at smaller N; a 20-seed x
3-router x real-model campaign would need real network/inference latency
per call and take far longer than this repository's established real-model
runs. This campaign instead measures the ROUTING MECHANISM's statistical
behavior (task-completion parity, LLM-invocation-rate reduction, effect
size across seeds) - real for what it measures, explicitly not a restatement
of Phase 4's real-latency numbers at larger N. A genuine real-model
large-scale campaign remains future work, same honesty as the historical
research line's own Milestone 5 "pilot vs. full campaign" distinction.

    python raca/tools/run_campaign.py
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
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

ROUTER_NAMES = ["always_deterministic", "always_llm", "adaptive_router"]
N_SEEDS = 20
DURATION_SEC = 60.0
LLM_CONFIG = {"backend": "mock", "fixed_cost": 0.9}  # see module docstring


def _start_positions(seed: int) -> dict:
    rng = random.Random(seed * 7919)  # distinct stream from the world's own per-robot RNG
    return {
        "robot1": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
        "robot2": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
    }


def run_one(router_name: str, seed: int) -> dict:
    router_ref = []

    def factory():
        router = build_backend({"backend": router_name, "llm_config": LLM_CONFIG})
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"],
        seed=seed,
        backend_factory=factory,
        start_positions=_start_positions(seed),
    )
    world.run_until(DURATION_SEC)
    summary = world.summary()

    total_llm = sum(getattr(r, "stats", None).llm_decisions for r in router_ref if hasattr(r, "stats"))
    total_calls = sum(getattr(r, "stats", None).total for r in router_ref if hasattr(r, "stats"))

    return {
        "seed": seed,
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else 0.0,
    }


def run() -> int:
    print(f"campaign: {len(ROUTER_NAMES)} routers x {N_SEEDS} paired seeds, "
          f"2 robots, duration={DURATION_SEC}s, varied non-symmetric start positions\n")

    results = {name: [run_one(name, seed) for seed in range(1, N_SEEDS + 1)] for name in ROUTER_NAMES}

    header = "| Router | N | Mean Tasks (± stdev) | Mean LLM Rate (± stdev) |"
    sep = "|---|---:|---:|---:|"
    print(header)
    print(sep)
    for name in ROUTER_NAMES:
        rows = results[name]
        tasks = [r["tasks_completed"] for r in rows]
        rates = [r["llm_invocation_rate"] for r in rows]
        print(
            f"| {name} | {len(rows)} | {statistics.mean(tasks):.2f} (±{statistics.stdev(tasks):.2f}) | "
            f"{statistics.mean(rates):.4f} (±{statistics.stdev(rates):.4f}) |"
        )

    print()
    # Paired difference: adaptive_router vs. always_llm, same seed set.
    adaptive_tasks = [r["tasks_completed"] for r in results["adaptive_router"]]
    always_llm_tasks = [r["tasks_completed"] for r in results["always_llm"]]
    task_diffs = [a - b for a, b in zip(adaptive_tasks, always_llm_tasks)]
    mean_task_diff = statistics.mean(task_diffs)

    adaptive_rates = [r["llm_invocation_rate"] for r in results["adaptive_router"]]
    always_llm_rates = [r["llm_invocation_rate"] for r in results["always_llm"]]
    mean_rate_diff = statistics.mean(a - b for a, b in zip(adaptive_rates, always_llm_rates))

    print(f"paired diff (adaptive_router - always_llm), N={N_SEEDS}:")
    print(f"  mean task-count diff: {mean_task_diff:+.3f} (stdev {statistics.stdev(task_diffs):.3f})")
    print(f"  mean LLM-rate diff:   {mean_rate_diff:+.4f}")

    task_diff_stats = compute_metric_statistics(task_diffs)
    rate_diffs = [a - b for a, b in zip(adaptive_rates, always_llm_rates)]
    rate_diff_stats = compute_metric_statistics(rate_diffs)
    print(f"  task-count diff 95% bootstrap CI: [{task_diff_stats['ci95_low']:+.3f}, {task_diff_stats['ci95_high']:+.3f}]")
    print(f"  LLM-rate diff 95% bootstrap CI:   [{rate_diff_stats['ci95_low']:+.4f}, {rate_diff_stats['ci95_high']:+.4f}]")

    quality_preserved = mean_task_diff >= -0.5  # small defined tolerance, not exact-zero
    cost_reduced = mean_rate_diff < -0.05

    print()
    print(f"  [{'PASS' if quality_preserved else 'FAIL'}] quality preserved: adaptive_router task count within 0.5 of always_llm's, on average across {N_SEEDS} seeds")
    print(f"  [{'PASS' if cost_reduced else 'FAIL'}] cost reduced: adaptive_router's LLM rate is meaningfully lower than always_llm's")
    return 0 if (quality_preserved and cost_reduced) else 1


if __name__ == "__main__":
    raise SystemExit(run())
