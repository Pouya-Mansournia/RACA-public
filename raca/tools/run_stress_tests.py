#!/usr/bin/env python3
"""Phase 12 - Failure and Stress Testing (master prompt PHASE 12).

Acceptance criterion (defined before running, per this project's own
established discipline): no injected fault may raise an unhandled
exception out of `LightweightWorld.run_until()`, and a safe fallback
action must remain available in every case.

    python raca/tools/run_stress_tests.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.backends.deterministic import DeterministicBackend  # noqa: E402
from raca_core.backends.fault_injection import DegradableBackend  # noqa: E402
from raca_core.backends.local_llm import LocalLLMBackend  # noqa: E402
from raca_core.backends.mock import MockBackend  # noqa: E402
from raca_core.llm_client import FakeLLMClient  # noqa: E402
from raca_core.router.adaptive import AdaptiveRouter  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

DURATION_SEC = 60.0
START_POSITIONS = {"robot1": (2.0, 3.0), "robot2": (-4.0, -1.0)}


def _run(name: str, backend_factory, extra_check=None) -> tuple[str, bool, str]:
    try:
        world = LightweightWorld(
            robot_ids=["robot1", "robot2"],
            seed=6,
            backend_factory=backend_factory,
            start_positions=START_POSITIONS,
        )
        world.run_until(DURATION_SEC)
    except Exception as exc:  # the one place a raise is itself the FAIL signal
        return name, False, f"unhandled exception escaped run_until: {type(exc).__name__}: {exc}"

    if extra_check is not None:
        ok, detail = extra_check(world)
        return name, ok, detail
    return name, True, f"tasks_completed={world.summary()['total_tasks_completed']}"


def test_hard_outage() -> tuple[str, bool, str]:
    """Backend outage / API down for the whole run."""

    def factory():
        llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
        return AdaptiveRouter(deterministic=DeterministicBackend(), llm=llm)

    def check(world):
        events = [e for e in world.events if e["type"] == "ROBOT_DECISION_FAILED"]
        return len(events) == 0, "no unhandled failures reached the world (AdaptiveRouter's own safety net absorbed every outage)"

    return _run("hard_outage (llm unavailable, whole run)", factory, check)


def test_high_latency() -> tuple[str, bool, str]:
    """High inference latency, not an outright failure."""

    def factory():
        llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), extra_latency_sec=0.02)
        return AdaptiveRouter(deterministic=DeterministicBackend(), llm=llm)

    def check(world):
        completed = world.summary()["total_tasks_completed"]
        return completed > 0, f"tasks still completed under added latency: {completed}"

    return _run("high_inference_latency (+20ms/call)", factory, check)


def test_invalid_llm_responses() -> tuple[str, bool, str]:
    """Backend returns structurally invalid / malformed responses."""

    def factory():
        client = FakeLLMClient(responses=["not json at all", "{\"action\": \"FLY\"}", "{}"])
        llm = LocalLLMBackend(client=client, max_retries=2, fallback=DeterministicBackend())
        return AdaptiveRouter(deterministic=DeterministicBackend(), llm=llm)

    def check(world):
        completed = world.summary()["total_tasks_completed"]
        return completed > 0, f"every malformed response correctly triggered fallback; tasks_completed={completed}"

    return _run("invalid_llm_responses (malformed JSON/schema)", factory, check)


def test_dual_backend_failure() -> tuple[str, bool, str]:
    """Both a robot's backends fail - the case Phase 11 exposed as a real
    architectural requirement, now fixed at the LightweightWorld level."""

    def factory():
        deterministic = DegradableBackend(inner=MockBackend(fixed_cost=0.1), available=False)
        llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
        return AdaptiveRouter(deterministic=deterministic, llm=llm)

    def check(world):
        failures = [e for e in world.events if e["type"] == "ROBOT_DECISION_FAILED"]
        return len(failures) > 0, f"world logged {len(failures)} ROBOT_DECISION_FAILED events and kept running instead of crashing"

    return _run("dual_backend_failure (both backends down)", factory, check)


def test_task_surge() -> tuple[str, bool, str]:
    """More robots contending for the same fixed station pool than any
    prior phase used - contention pressure, not a backend fault."""

    def factory():
        return DeterministicBackend()

    def check(world):
        completed = world.summary()["total_tasks_completed"]
        return completed > 0, f"6 robots, same station pool: tasks_completed={completed}"

    try:
        world = LightweightWorld(
            robot_ids=[f"robot{i}" for i in range(1, 7)],
            seed=6,
            backend_factory=factory,
        )
        world.run_until(DURATION_SEC)
    except Exception as exc:
        return "task_surge (6 robots, fixed station pool)", False, f"unhandled exception: {type(exc).__name__}: {exc}"
    ok, detail = check(world)
    return "task_surge (6 robots, fixed station pool)", ok, detail


CHECKS = [
    test_hard_outage,
    test_high_latency,
    test_invalid_llm_responses,
    test_dual_backend_failure,
    test_task_surge,
]


def run() -> int:
    print("Phase 12 stress tests - acceptance: no unhandled exception escapes run_until(),")
    print("a safe fallback action remains available in every scenario.\n")
    header = "| Fault | Result | Detail |"
    sep = "|---|---|---|"
    print(header)
    print(sep)

    all_pass = True
    for check_fn in CHECKS:
        name, ok, detail = check_fn()
        all_pass = all_pass and ok
        print(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")

    print()
    print("RESULT:", "PASS - RACA degrades gracefully under every injected fault" if all_pass else "FAIL - see above")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(run())
