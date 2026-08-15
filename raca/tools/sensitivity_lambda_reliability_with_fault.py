#!/usr/bin/env python3
"""lambda_reliability sensitivity sweep UNDER AN INJECTED FAULT (the
follow-up the earlier fault-free sweep couldn't answer: that sweep found
zero sensitivity because failure_rate(b) never left 0 with no failure
injected, an honest null result attributable to the sweep design, not
lambda_reliability itself).

Reuses the ablation methodology's fault pattern (raca/tools/
generate_ablation_report.py): the LLM backend goes unavailable partway
through the run via DegradableBackend, so failure_rate("llm") actually
becomes nonzero and the reliability penalty term has something to act on.
N=20 paired seeds (upgraded from the ablation script's N=3, since this is
specifically a statistical sensitivity question), MockBackend.

    python raca/tools/sensitivity_lambda_reliability_with_fault.py
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.backends.deterministic import DeterministicBackend  # noqa: E402
from raca_core.backends.fault_injection import DegradableBackend  # noqa: E402
from raca_core.backends.mock import MockBackend  # noqa: E402
from raca_core.router.adaptive import AdaptiveRouter  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

N_SEEDS = 20
DURATION_SEC = 60.0
DEGRADE_ONSET_SEC = 20.0  # matches the ablation script's own fault timing
LAMBDA_RELIABILITY_CANDIDATES = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]


def _start_positions(seed: int) -> dict:
    rng = random.Random(seed * 7919)
    return {
        "robot1": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
        "robot2": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
    }


def run_one(lambda_reliability: float, seed: int) -> dict:
    router_ref = []
    llm_wrappers = []

    def factory():
        deterministic = DeterministicBackend()
        llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9))
        router = AdaptiveRouter(
            deterministic=deterministic, llm=llm,
            lambda_reliability=lambda_reliability,
        )
        router.estimator.ambiguity_margin_scale = 0.04
        router_ref.append(router)
        llm_wrappers.append(llm)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"], seed=seed, backend_factory=factory,
        start_positions=_start_positions(seed),
    )
    world.schedule(DEGRADE_ONSET_SEC, lambda: [setattr(w, "available", False) for w in llm_wrappers])
    world.run_until(DURATION_SEC)
    summary = world.summary()

    total_llm = sum(r.stats.llm_decisions for r in router_ref)
    total_calls = sum(r.stats.total for r in router_ref)
    return {
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else 0.0,
    }


def run() -> int:
    print(f"lambda_reliability sensitivity UNDER INJECTED FAULT: N={N_SEEDS} paired seeds, 2 robots, "
          f"MockBackend, LLM degrades to unavailable at t={DEGRADE_ONSET_SEC}s (permanent for the rest of the run)\n")
    print("| lambda_reliability | Mean Tasks | Mean LLM Rate (post-fault effect visible) |")
    print("|---:|---:|---:|")
    for lam in LAMBDA_RELIABILITY_CANDIDATES:
        rows = [run_one(lam, seed) for seed in range(1, N_SEEDS + 1)]
        tasks = [r["tasks_completed"] for r in rows]
        rates = [r["llm_invocation_rate"] for r in rows]
        mean_tasks = statistics.mean(tasks)
        mean_rate = statistics.mean(rates)
        marker = " (penalty disabled)" if lam == 0.0 else " (shipped default)" if lam == 2.0 else ""
        print(f"| {lam}{marker} | {mean_tasks:.2f} | {mean_rate:.4f} |")

    print()
    print("Interpretation: with a real injected failure, failure_rate('llm') becomes nonzero after")
    print("t=20s, so lambda_reliability now has something to act on (unlike the fault-free sweep).")
    print("If mean LLM rate drops as lambda_reliability increases, the penalty term is doing real")
    print("work; if it's flat, the fallback's own try/except (which fires regardless of the utility")
    print("penalty) is already doing all of the practical work and the penalty term is redundant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
