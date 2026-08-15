#!/usr/bin/env python3
"""Phase 7 acceptance check: RACA V1 (AdaptiveRouter) vs. its baselines.

Acceptance criterion, defined here BEFORE reading the results below (same
discipline as raca/docs/phase2_calibration.md):

    AdaptiveRouter must complete at least as many tasks as
    Always-Deterministic (quality not worse than the free baseline) AND
    invoke the LLM strictly less often than Always-LLM (real cost
    reduction), across the SAME paired seeds and (per the Phase 6 finding)
    NON-symmetric robot starting positions.

Runs with plain `python3` (a reachable Ollama server gives real `llm`
numbers; unreachable gracefully falls back, per LocalLLMBackend's own
tested behavior):

    python raca/tools/generate_adaptive_router_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.config import build_backend  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

ROUTER_NAMES = ["always_deterministic", "always_llm", "adaptive_router"]
SEEDS = [6, 7, 8]
DURATION_SEC = 60.0

# Deliberately NON-symmetric per seed - the Phase 6 finding was that
# all-at-origin spawns make ambiguity saturate at ~1.0 for every decision,
# which would make an adaptive router indistinguishable from Always-LLM by
# construction, not by design.
START_POSITIONS_BY_SEED = {
    6: {"robot1": (2.0, 3.0), "robot2": (-4.0, -1.0)},
    7: {"robot1": (5.0, -2.0), "robot2": (0.5, 4.0)},
    8: {"robot1": (-3.0, 1.0), "robot2": (6.0, -6.0)},
}


def run_one(router_name: str, seed: int) -> dict:
    router_ref = []

    def factory():
        router = build_backend({"backend": router_name})
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"],
        seed=seed,
        backend_factory=factory,
        start_positions=START_POSITIONS_BY_SEED[seed],
    )
    world.run_until(DURATION_SEC)
    summary = world.summary()

    total_llm = sum(getattr(r, "stats", None).llm_decisions for r in router_ref if hasattr(r, "stats"))
    total_calls = sum(getattr(r, "stats", None).total for r in router_ref if hasattr(r, "stats"))
    llm_rate = (total_llm / total_calls) if total_calls else None

    return {
        "seed": seed,
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": llm_rate,
        "llm_calls": total_llm,
        "total_calls": total_calls,
    }


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def run() -> int:
    print(f"scenario: 2 robots, duration={DURATION_SEC}s, paired seeds={SEEDS}, non-symmetric start positions\n")
    header = "| Router | Seed | Tasks Completed | LLM Invocation Rate | LLM Calls |"
    sep = "|---|---:|---:|---:|---:|"
    print(header)
    print(sep)

    results = {name: [] for name in ROUTER_NAMES}
    for router_name in ROUTER_NAMES:
        for seed in SEEDS:
            row = run_one(router_name, seed)
            results[router_name].append(row)
            print(
                f"| {router_name} | {row['seed']} | {row['tasks_completed']} | "
                f"{_fmt(row['llm_invocation_rate'])} | {row['llm_calls']} |"
            )

    print()
    mean_tasks_det = sum(r["tasks_completed"] for r in results["always_deterministic"]) / len(SEEDS)
    mean_tasks_llm = sum(r["tasks_completed"] for r in results["always_llm"]) / len(SEEDS)
    mean_tasks_adaptive = sum(r["tasks_completed"] for r in results["adaptive_router"]) / len(SEEDS)
    mean_llm_rate_always = sum(r["llm_invocation_rate"] for r in results["always_llm"]) / len(SEEDS)
    mean_llm_rate_adaptive = sum(r["llm_invocation_rate"] for r in results["adaptive_router"]) / len(SEEDS)

    print(f"mean tasks_completed: always_deterministic={mean_tasks_det:.2f}, "
          f"always_llm={mean_tasks_llm:.2f}, adaptive_router={mean_tasks_adaptive:.2f}")
    print(f"mean llm_invocation_rate: always_llm={mean_llm_rate_always:.4f}, "
          f"adaptive_router={mean_llm_rate_adaptive:.4f}")

    quality_ok = mean_tasks_adaptive >= mean_tasks_det
    cost_ok = mean_llm_rate_adaptive < mean_llm_rate_always

    print()
    print(f"  [{'PASS' if quality_ok else 'FAIL'}] quality: adaptive_router tasks >= always_deterministic tasks")
    print(f"  [{'PASS' if cost_ok else 'FAIL'}] cost: adaptive_router LLM rate < always_llm LLM rate")
    print()
    print("RESULT:", "PASS - RACA V1 beats Always-LLM on the defined multi-objective criterion"
          if (quality_ok and cost_ok) else "FAIL - see above")
    return 0 if (quality_ok and cost_ok) else 1


if __name__ == "__main__":
    raise SystemExit(run())
