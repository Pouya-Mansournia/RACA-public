from __future__ import annotations

from raca_core.backends.fault_injection import DegradableBackend
from raca_core.backends.mock import MockBackend
from raca_core.router.adaptive import AdaptiveRouter
from raca_worlds.lightweight_world import LightweightWorld


def test_dual_backend_failure_does_not_crash_the_world():
    def factory():
        deterministic = DegradableBackend(inner=MockBackend(fixed_cost=0.1), available=False)
        llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
        return AdaptiveRouter(deterministic=deterministic, llm=llm)

    world = LightweightWorld(robot_ids=["robot1", "robot2"], seed=1, backend_factory=factory)
    # Must not raise, even though every decision for every robot fails.
    world.run_until(30.0)
    failures = [e for e in world.events if e["type"] == "ROBOT_DECISION_FAILED"]
    assert len(failures) > 0
    assert world.summary()["total_tasks_completed"] == 0


def test_one_robot_failing_does_not_block_a_healthy_peer():
    call_count = {"n": 0}

    def failing_factory():
        deterministic = DegradableBackend(inner=MockBackend(fixed_cost=0.1), available=False)
        llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
        return AdaptiveRouter(deterministic=deterministic, llm=llm)

    def healthy_factory():
        from raca_core.backends.deterministic import DeterministicBackend

        return DeterministicBackend()

    factories = {"robot1": failing_factory, "robot2": healthy_factory}

    def factory():
        # LightweightWorld calls this once per robot_id in order; capture
        # which robot is being built via a shared mutable index.
        call_count["n"] += 1
        robot_id = ["robot1", "robot2"][call_count["n"] - 1]
        return factories[robot_id]()

    world = LightweightWorld(robot_ids=["robot1", "robot2"], seed=1, backend_factory=factory)
    world.run_until(90.0)
    # robot2's own healthy DeterministicBackend must still complete real
    # tasks even though robot1's decisions are failing every attempt.
    assert world.summary()["per_robot"]["robot2"]["tasks_completed"] >= 1
    assert world.summary()["per_robot"]["robot1"]["tasks_completed"] == 0
