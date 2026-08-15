#!/usr/bin/env python3
"""Coarse sensitivity sweep on lambda_latency and lambda_reliability
(final pre-submission red-team audit, item 7: "does the qualitative
result survive across a reasonable parameter region," not a search for
the best-looking combination).

Reuses the exact N=20 paired-seed, 2-robot, MockBackend methodology
Phase 13/the ambiguity-scale sweep already use, holding
AMBIGUITY_MARGIN_SCALE at its selected default (0.04) and varying
lambda_latency and lambda_reliability independently around their shipped
defaults (0.1 and 2.0). Selection criteria are the SAME pre-defined ones
used throughout this project (quality within 0.5 tasks of always_llm;
LLM rate more than 5 points below always_llm's).

    python raca/tools/sensitivity_lambda_sweep.py
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.config import build_backend  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

N_SEEDS = 20
DURATION_SEC = 60.0
LLM_CONFIG = {"backend": "mock", "fixed_cost": 0.9}

# Shipped defaults: lambda_latency=0.1, lambda_reliability=2.0
LAMBDA_LATENCY_CANDIDATES = [0.01, 0.05, 0.1, 0.5, 1.0]
LAMBDA_RELIABILITY_CANDIDATES = [0.5, 1.0, 2.0, 5.0, 10.0]


def _start_positions(seed: int) -> dict:
    rng = random.Random(seed * 7919)
    return {
        "robot1": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
        "robot2": (rng.uniform(-6.5, 6.5), rng.uniform(-8.5, 8.5)),
    }


def run_one(router_name: str, seed: int, lambda_latency=None, lambda_reliability=None) -> dict:
    router_ref = []

    def factory():
        cfg = {"backend": router_name, "llm_config": LLM_CONFIG}
        if router_name == "adaptive_router":
            cfg["ambiguity_margin_scale"] = 0.04
            if lambda_latency is not None:
                cfg["lambda_latency"] = lambda_latency
            if lambda_reliability is not None:
                cfg["lambda_reliability"] = lambda_reliability
        router = build_backend(cfg)
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"], seed=seed, backend_factory=factory,
        start_positions=_start_positions(seed),
    )
    world.run_until(DURATION_SEC)
    summary = world.summary()
    total_llm = sum(getattr(r, "stats", None).llm_decisions for r in router_ref if hasattr(r, "stats"))
    total_calls = sum(getattr(r, "stats", None).total for r in router_ref if hasattr(r, "stats"))
    return {
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else 0.0,
    }


def sweep_one_dimension(name: str, candidates, kwarg_name: str, always_llm_tasks: list) -> None:
    mean_always_llm_tasks = statistics.mean(always_llm_tasks)
    print(f"### {name} sweep (other lambda held at its shipped default)\n")
    print("| Value | Mean Tasks | Mean LLM Rate | Quality OK | Cost OK |")
    print("|---:|---:|---:|---|---|")
    for value in candidates:
        kwargs = {kwarg_name: value}
        rows = [run_one("adaptive_router", seed, **kwargs) for seed in range(1, N_SEEDS + 1)]
        tasks = [r["tasks_completed"] for r in rows]
        rates = [r["llm_invocation_rate"] for r in rows]
        mean_tasks = statistics.mean(tasks)
        mean_rate = statistics.mean(rates)
        quality_ok = mean_tasks >= mean_always_llm_tasks - 0.5
        cost_ok = mean_rate < 0.95
        marker = " (shipped default)" if (kwarg_name == "lambda_latency" and value == 0.1) or (kwarg_name == "lambda_reliability" and value == 2.0) else ""
        print(f"| {value}{marker} | {mean_tasks:.2f} | {mean_rate:.4f} | {'YES' if quality_ok else 'no'} | {'YES' if cost_ok else 'no'} |")
    print()


def run() -> int:
    print(f"lambda sensitivity sweep: N={N_SEEDS} paired seeds, 2 robots, AMBIGUITY_MARGIN_SCALE fixed at 0.04\n")
    print("Goal: does the qualitative result (quality preserved AND cost meaningfully reduced) survive")
    print("across this parameter region, not which single value looks best.\n")

    always_llm_tasks = [run_one("always_llm", seed)["tasks_completed"] for seed in range(1, N_SEEDS + 1)]

    sweep_one_dimension("lambda_latency", LAMBDA_LATENCY_CANDIDATES, "lambda_latency", always_llm_tasks)
    sweep_one_dimension("lambda_reliability", LAMBDA_RELIABILITY_CANDIDATES, "lambda_reliability", always_llm_tasks)

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
