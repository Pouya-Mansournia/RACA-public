#!/usr/bin/env python3
"""Phase 11 - Systematic Ablations (master prompt PHASE 11).

Ablates each signal AdaptiveRouter's utility uses, one at a time, on
IDENTICAL paired seeds/scenario, to identify which signals actually
contribute to useful routing behavior (vs. cosmetic complexity).

    python raca/tools/generate_ablation_report.py

Uses MockBackend for the "llm" role (fast, deterministic) so this script
isolates each signal's effect on ROUTING SELECTION, not on any specific
model's latency variance - Phase 4/6/7/9/10 already established the real-
model latency numbers this project's priors are calibrated from.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.backends.deterministic import DeterministicBackend  # noqa: E402
from raca_core.backends.fault_injection import DegradableBackend, FallbackBackend  # noqa: E402
from raca_core.backends.mock import MockBackend  # noqa: E402
from raca_core.router.adaptive import AdaptiveRouter  # noqa: E402
from raca_core.router.static import FixedAmbiguityThresholdRouter  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

SEEDS = [6, 7, 8]
DURATION_SEC = 60.0
START_POSITIONS_BY_SEED = {
    6: {"robot1": (2.0, 3.0), "robot2": (-4.0, -1.0)},
    7: {"robot1": (5.0, -2.0), "robot2": (0.5, 4.0)},
    8: {"robot1": (-3.0, 1.0), "robot2": (6.0, -6.0)},
}

# One failure injected partway through, same for every ablation config, so
# "No backend reliability history" has something real to be measured
# against - without an injected failure, lambda_reliability's effect would
# never be exercised at all (failure_rate stays 0 for everyone).
DEGRADE_ONSET_SEC = 20.0


def build_ablation(name: str) -> AdaptiveRouter:
    deterministic = DeterministicBackend()
    llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9))
    common = dict(deterministic=deterministic, llm=llm)

    if name == "full_raca":
        return AdaptiveRouter(**common), llm
    if name == "no_latency_awareness":
        return AdaptiveRouter(**common, lambda_latency=0.0), llm
    if name == "no_urgency_awareness":
        return AdaptiveRouter(**common, urgency_aware=False), llm
    if name == "no_ambiguity_awareness":
        return AdaptiveRouter(**common, quality_bonus_scale=0.0), llm
    if name == "no_reliability_history":
        return AdaptiveRouter(**common, lambda_reliability=0.0), llm
    if name == "static_fixed_threshold":
        return FixedAmbiguityThresholdRouter(deterministic=deterministic, llm=llm), llm
    if name == "static_fixed_threshold_with_fallback":
        # Critical Audit 5 deconfounding variant (final_presubmission_audit/):
        # identical fixed-threshold routing POLICY, but the llm role is
        # wrapped in the SAME try/except-and-retry safety net AdaptiveRouter
        # has built in, so a crash/survive difference against
        # "static_fixed_threshold" above isolates the wrapper's effect from
        # the routing policy's effect.
        wrapped_llm = FallbackBackend(primary=llm, fallback=deterministic)
        return FixedAmbiguityThresholdRouter(deterministic=deterministic, llm=wrapped_llm), llm
    raise ValueError(name)


ABLATIONS = [
    "full_raca",
    "no_latency_awareness",
    "no_urgency_awareness",
    "no_ambiguity_awareness",
    "no_reliability_history",
    "static_fixed_threshold",
    "static_fixed_threshold_with_fallback",
]


def run_one(ablation_name: str, seed: int) -> dict:
    router_refs = []
    llm_wrappers = []

    def factory():
        router, llm_wrapper = build_ablation(ablation_name)
        router_refs.append(router)
        llm_wrappers.append(llm_wrapper)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"],
        seed=seed,
        backend_factory=factory,
        start_positions=START_POSITIONS_BY_SEED[seed],
    )
    world.schedule(DEGRADE_ONSET_SEC, lambda: [setattr(w, "available", False) for w in llm_wrappers])
    world.run_until(DURATION_SEC)
    summary = world.summary()

    total_llm = sum(r.stats.llm_decisions for r in router_refs)
    total_calls = sum(r.stats.total for r in router_refs)
    return {
        "ablation": ablation_name,
        "seed": seed,
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else None,
    }


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def run() -> int:
    print(f"scenario: 2 robots, duration={DURATION_SEC}s, paired seeds={SEEDS}, "
          f"llm degrades to unavailable at t={DEGRADE_ONSET_SEC}s\n")
    print("NOTE on static_fixed_threshold_with_fallback (Critical Audit 5 deconfounding variant):")
    print("its LLM Invocation Rate counts attempts routed to the LLM slot, not confirmed LLM")
    print("responses - FallbackBackend can silently substitute the deterministic backend's answer")
    print("after a caught exception, so this row's rate is an upper bound on true LLM usage, not")
    print("an exact figure. Mean Tasks Completed is unaffected by this and is the metric that")
    print("actually answers the crash/survive question.\n")
    header = "| Ablation | Mean Tasks Completed | Mean LLM Invocation Rate |"
    sep = "|---|---:|---:|"
    print(header)
    print(sep)

    for ablation_name in ABLATIONS:
        try:
            rows = [run_one(ablation_name, seed) for seed in SEEDS]
        except Exception as exc:
            # A real, reportable finding, not a bug to hide: the STATIC
            # baseline router (unlike AdaptiveRouter, which has Phase 8's
            # try/except safety net built into every decide() call) has no
            # failure handling at all - an injected LLM outage crashes it
            # outright. This IS the ablation result for this row.
            print(f"| {ablation_name} | CRASHED | {type(exc).__name__}: {exc} |")
            continue
        mean_tasks = sum(r["tasks_completed"] for r in rows) / len(rows)
        rates = [r["llm_invocation_rate"] for r in rows if r["llm_invocation_rate"] is not None]
        mean_rate = sum(rates) / len(rates) if rates else None
        print(f"| {ablation_name} | {mean_tasks:.2f} | {_fmt(mean_rate)} |")

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
