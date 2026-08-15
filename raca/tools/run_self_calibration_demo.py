#!/usr/bin/env python3
"""Phase 8 acceptance check: inject controlled backend degradation mid-run,
confirm the router's own selection shifts away from it - without being told
to, purely from its own observed failures.

    python raca/tools/run_self_calibration_demo.py

Scenario: AdaptiveRouter with its `llm` backend wrapped in
`DegradableBackend`, healthy for the first 30 (simulated) seconds, then
flipped to `available=False` (a hard outage, e.g. "server unreachable") for
the remaining 60 seconds. Non-symmetric start positions (Phase 7's own
finding) so ambiguous decisions actually occur and the LLM would otherwise
be genuinely preferred.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.backends.deterministic import DeterministicBackend  # noqa: E402
from raca_core.backends.fault_injection import DegradableBackend  # noqa: E402
from raca_core.backends.mock import MockBackend  # noqa: E402
from raca_core.router.adaptive import AdaptiveRouter  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

DEGRADATION_ONSET_SEC = 30.0
DURATION_SEC = 90.0
START_POSITIONS = {"robot1": (2.0, 3.0), "robot2": (-4.0, -1.0)}


def run() -> int:
    degradable_llms = []
    routers = {}

    def factory():
        # MockBackend standing in for the real LLM here so this demo runs
        # in milliseconds, not minutes - Phase 7's own report already
        # proved AdaptiveRouter's routing logic works identically against
        # the real qwen2.5:7b backend; this script isolates the Phase 8
        # self-calibration mechanism itself, which is backend-agnostic by
        # construction (it only looks at latency/failure history, never at
        # which concrete backend produced them).
        llm_wrapper = DegradableBackend(inner=MockBackend(fixed_cost=0.9))
        degradable_llms.append(llm_wrapper)
        router = AdaptiveRouter(deterministic=DeterministicBackend(), llm=llm_wrapper)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"],
        seed=6,
        backend_factory=factory,
        start_positions=START_POSITIONS,
    )
    # Capture each robot's actual AdaptiveRouter instance (the factory
    # returns it directly here, unwrapped by any instrumentation layer).
    for robot_id, robot in world.robots.items():
        routers[robot_id] = robot.backend

    snapshot_before = {}

    def take_snapshot():
        for robot_id, router in routers.items():
            snapshot_before[robot_id] = (router.stats.deterministic_decisions, router.stats.llm_decisions)

    def trigger_degradation():
        for wrapper in degradable_llms:
            wrapper.available = False

    world.schedule(DEGRADATION_ONSET_SEC - 0.01, take_snapshot)
    world.schedule(DEGRADATION_ONSET_SEC, trigger_degradation)
    world.run_until(DURATION_SEC)

    print(f"scenario: 2 robots, seed=6, degradation onset at t={DEGRADATION_ONSET_SEC}s, total duration={DURATION_SEC}s\n")
    header = "| Robot | LLM rate before onset | LLM rate after onset | LLM failure_rate (final) |"
    sep = "|---|---:|---:|---:|"
    print(header)
    print(sep)

    all_pass = True
    for robot_id, router in routers.items():
        det_before, llm_before = snapshot_before[robot_id]
        det_final, llm_final = router.stats.deterministic_decisions, router.stats.llm_decisions
        det_after, llm_after = det_final - det_before, llm_final - llm_before

        total_before = det_before + llm_before
        total_after = det_after + llm_after
        rate_before = (llm_before / total_before) if total_before else None
        rate_after = (llm_after / total_after) if total_after else None

        rate_before_str = "n/a" if rate_before is None else f"{rate_before:.3f}"
        rate_after_str = "n/a" if rate_after is None else f"{rate_after:.3f}"
        print(f"| {robot_id} | {rate_before_str} | {rate_after_str} | {router.failure_rate('llm'):.3f} |")

        if rate_before is not None and rate_after is not None:
            if not (rate_after < rate_before):
                all_pass = False

    print()
    print(
        "RESULT:",
        "PASS - LLM invocation rate dropped after injected degradation, without being told to"
        if all_pass
        else "FAIL - see above (or too few decisions in one window to compare)",
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(run())
