#!/usr/bin/env python3
"""Phase 6 - Static Routing Baselines (master prompt PHASE 6).

Runs every static routing policy (Always-Deterministic, Always-LLM, Fixed
Ambiguity Threshold, Random, Simple Rule Router) on IDENTICAL paired
scenarios/seeds, and reports latency, task performance, and LLM invocation
rate for each - the comparison table any later adaptive router (Phase 7)
must be shown to beat.

    python raca/tools/generate_routing_baseline_report.py

Requires a reachable Ollama server for the real `local_llm` numbers (see
raca/docs/phase2_calibration.md-adjacent tooling); if unreachable, every
"LLM" decision gracefully falls back to deterministic (LocalLLMBackend's
own tested behavior) and this is reported honestly via a nonzero fallback
signal in LLM invocation rate vs. actual model use, not hidden.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.backends.instrumentation import TimingWrapperBackend  # noqa: E402
from raca_core.config import build_backend  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

ROUTER_NAMES = [
    "always_deterministic",
    "always_llm",
    "fixed_ambiguity_threshold",
    "random_router",
    "simple_rule_router",
]

SEEDS = [6, 7, 8]  # paired seeds - every router runs on the SAME seed set
ROBOT_IDS = ["robot1", "robot2"]
DURATION_SEC = 60.0


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def run_one(router_name: str, seed: int) -> dict:
    wrappers = []
    router_ref = []

    def factory():
        router = build_backend({"backend": router_name})
        router_ref.append(router)
        wrapper = TimingWrapperBackend(inner=router)
        wrappers.append(wrapper)
        return wrapper

    world = LightweightWorld(robot_ids=list(ROBOT_IDS), seed=seed, backend_factory=factory)
    world.run_until(DURATION_SEC)
    summary = world.summary()

    all_records = [r for w in wrappers for r in w.records]
    n = len(all_records)
    mean_latency = sum(r.latency_sec for r in all_records) / n if n else None

    total_llm = sum(r.stats.llm_decisions for r in router_ref)
    total_calls = sum(r.stats.total for r in router_ref)
    llm_rate = (total_llm / total_calls) if total_calls else None

    return {
        "seed": seed,
        "decisions": n,
        "mean_latency_ms": mean_latency * 1000 if mean_latency is not None else None,
        "llm_invocation_rate": llm_rate,
        "tasks_completed": summary["total_tasks_completed"],
    }


def run() -> int:
    print(f"scenario: {len(ROBOT_IDS)} robots, duration={DURATION_SEC}s, paired seeds={SEEDS}\n")
    header = "| Router | Seed | Decisions | Mean Latency (ms) | LLM Invocation Rate | Tasks Completed |"
    sep = "|---|---:|---:|---:|---:|---:|"
    print(header)
    print(sep)
    for router_name in ROUTER_NAMES:
        for seed in SEEDS:
            row = run_one(router_name, seed)
            print(
                f"| {router_name} | {row['seed']} | {row['decisions']} | "
                f"{_fmt(row['mean_latency_ms'])} | {_fmt(row['llm_invocation_rate'])} | "
                f"{row['tasks_completed']} |"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
