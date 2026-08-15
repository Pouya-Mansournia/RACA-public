#!/usr/bin/env python3
"""Ambiguity-scale recalibration (post-Phase-14 methodological revision).

Phase 13 found that `AMBIGUITY_MARGIN_SCALE=0.05` (inherited unchanged
from the prior research line's `HybridAgent`) makes near-ties the
statistical norm under this warehouse's station grid at random robot
positions - AdaptiveRouter's LLM invocation rate (95.8%) barely differed
from Always-LLM's (100%).

This script sweeps candidate scale values against the SAME N=20 paired-seed
campaign methodology Phase 13 used, and selects a replacement value using a
principled, pre-defined rule: the LARGEST scale (i.e. the most
conservative change, closest to the original 0.05) at which BOTH of Phase
13's own acceptance criteria pass simultaneously (quality preserved AND
cost meaningfully reduced) - not the value that produces the most
flattering single number in isolation. Since `ambiguity = 1 -
margin/scale`, a SMALLER scale is what reduces false-ambiguity (not
larger) - candidates below are ordered smallest-to-largest for that reason.

    python raca/tools/calibrate_ambiguity_scale.py

Per master prompt section 20 ("any methodological change must be recorded:
what changed, why, before/after definition, whether prior data remains
comparable"): this change does NOT retroactively alter any earlier phase's
recorded results (Phases 1-13 all used the original 0.05 default, and
their numbers in docs/research_journal.md remain exactly as measured). It
only changes the DEFAULT going forward for new work, recorded as a
deliberate revision with before/after evidence in this file's own output
and in docs/research_journal.md.
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.config import build_backend  # noqa: E402
from raca_core.difficulty import AMBIGUITY_MARGIN_SCALE  # noqa: E402
from raca_core.stats import compute_metric_statistics  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

# ambiguity = clamp(1 - margin/scale, 0, 1): a SMALLER scale makes any
# given margin count as LESS ambiguous (margin/scale grows faster), so
# reducing false-ambiguity means sweeping scale DOWN from the 0.05
# original, not up - the first sweep attempt got this backwards (see
# docs/research_journal.md's own record of that error) and is retained
# here only as a corrected, documented mistake, not silently rewritten.
CANDIDATE_SCALES = [0.001, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05]
N_SEEDS = 20
DURATION_SEC = 60.0
LLM_CONFIG = {"backend": "mock", "fixed_cost": 0.9}


def _start_positions(seed: int) -> dict:
    rng = random.Random(seed * 7919)
    return {
        "robot1": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
        "robot2": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
    }


def run_one(scale: float, seed: int) -> dict:
    router_ref = []

    def factory():
        router = build_backend(
            {"backend": "adaptive_router", "llm_config": LLM_CONFIG, "ambiguity_margin_scale": scale}
        )
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"], seed=seed, backend_factory=factory,
        start_positions=_start_positions(seed),
    )
    world.run_until(DURATION_SEC)
    summary = world.summary()
    total_llm = sum(r.stats.llm_decisions for r in router_ref)
    total_calls = sum(r.stats.total for r in router_ref)
    return {
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else 0.0,
    }


def run_always_llm(seed: int) -> int:
    def factory():
        return build_backend({"backend": "always_llm", "llm_config": LLM_CONFIG})

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"], seed=seed, backend_factory=factory,
        start_positions=_start_positions(seed),
    )
    world.run_until(DURATION_SEC)
    return world.summary()["total_tasks_completed"]


def run() -> int:
    print(f"ambiguity-scale sweep: N={N_SEEDS} paired seeds, candidates={CANDIDATE_SCALES}\n")
    print(f"baseline (pre-recalibration default 0.05) already measured in Phase 13: "
          f"tasks=7.40 (±0.50), llm_rate=95.8% (±5.3%). Current default is {AMBIGUITY_MARGIN_SCALE}.\n")

    always_llm_tasks = [run_always_llm(seed) for seed in range(1, N_SEEDS + 1)]
    mean_always_llm_tasks = statistics.mean(always_llm_tasks)

    header = "| Scale | Mean Tasks (±stdev) | Mean LLM Rate (±stdev) | Quality OK | Cost OK |"
    sep = "|---:|---:|---:|---|---|"
    print(header)
    print(sep)

    selected = None
    results_by_scale = {}
    for scale in CANDIDATE_SCALES:
        rows = [run_one(scale, seed) for seed in range(1, N_SEEDS + 1)]
        tasks = [r["tasks_completed"] for r in rows]
        rates = [r["llm_invocation_rate"] for r in rows]
        mean_tasks, stdev_tasks = statistics.mean(tasks), statistics.stdev(tasks)
        mean_rate, stdev_rate = statistics.mean(rates), statistics.stdev(rates)

        quality_ok = mean_tasks >= mean_always_llm_tasks - 0.5
        cost_ok = mean_rate < 0.95  # meaningfully below the ~100% Always-LLM/original-scale rate

        print(
            f"| {scale:.3f} | {mean_tasks:.2f} (±{stdev_tasks:.2f}) | "
            f"{mean_rate:.4f} (±{stdev_rate:.4f}) | {'YES' if quality_ok else 'no'} | {'YES' if cost_ok else 'no'} |"
        )
        results_by_scale[scale] = (quality_ok, cost_ok, tasks, rates)

    print()
    # Largest scale (closest to the original 0.05, least deviation from
    # the inherited HybridAgent constant) at which BOTH criteria pass -
    # candidates are defined smallest-to-largest above, so scan in reverse.
    for scale in sorted(CANDIDATE_SCALES, reverse=True):
        quality_ok, cost_ok, _, _ = results_by_scale[scale]
        if quality_ok and cost_ok:
            selected = scale
            break

    if selected is not None:
        _, _, sel_tasks, sel_rates = results_by_scale[selected]
        task_stats = compute_metric_statistics(sel_tasks)
        rate_stats = compute_metric_statistics(sel_rates)
        print(f"SELECTED: {selected} - largest (most conservative) scale where both criteria pass.")
        print(f"  selected scale, N={N_SEEDS}: tasks 95% bootstrap CI [{task_stats['ci95_low']:.3f}, {task_stats['ci95_high']:.3f}], "
              f"llm_rate 95% bootstrap CI [{rate_stats['ci95_low']:.4f}, {rate_stats['ci95_high']:.4f}]")
    else:
        print("SELECTED: none of the candidate scales passed both criteria in this sweep range - "
              "the original 0.05 default is retained, and this is itself a reportable finding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
