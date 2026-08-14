from __future__ import annotations

import pytest

from raca_core.backends.fault_injection import DegradableBackend, InjectedFailure
from raca_core.backends.mock import MockBackend
from raca_core.contracts import ALLOWED_ACTIONS, RobotObservation, StationCandidate
from raca_core.router.adaptive import AdaptiveRouter


def _ambiguous_observation(battery_soc=1.0):
    return RobotObservation(
        robot_id="robot1",
        x=0.0,
        y=0.0,
        battery_soc=battery_soc,
        degradation_risk=0.0,
        utilization=0.0,
        candidate_stations=(
            StationCandidate(name="a", side="output", x=5.0, y=-1.0),
            StationCandidate(name="b", side="output", x=5.0, y=1.0),
        ),
    )


def test_single_backend_failure_never_breaks_the_router():
    llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
    router = AdaptiveRouter(deterministic=MockBackend(fixed_cost=0.1), llm=llm)
    # LLM would normally be preferred here (ambiguous + full battery), but
    # it's injected-unavailable - the router must still return a valid
    # action via its safety-net fallback, never raise.
    action = router.decide(_ambiguous_observation(), ALLOWED_ACTIONS)
    assert action.action in ALLOWED_ACTIONS
    assert router.failure_rate("llm") > 0.0


def test_repeated_failures_shift_selection_away_from_the_backend():
    llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
    router = AdaptiveRouter(deterministic=MockBackend(fixed_cost=0.1), llm=llm)

    for _ in range(10):
        router.decide(_ambiguous_observation(), ALLOWED_ACTIONS)

    # Every call attempted llm first (it would have been preferred while
    # healthy) and fell back to deterministic every time - all 10 final
    # answers came from deterministic, and llm's tracked failure_rate
    # reflects every one of those failed attempts.
    assert router.stats.deterministic_decisions == 10
    assert router.failure_rate("llm") == 1.0


def test_no_automatic_reprobe_after_backend_recovers_documented_limitation():
    # Known, documented limitation (see adaptive.py's module docstring):
    # failure_rate is a simple running ratio with no decay and no periodic
    # re-probe mechanism. Once a backend's penalty is large enough to make
    # it permanently lose the utility comparison, the router stops
    # attempting it entirely - even after it recovers - until some OTHER
    # signal (a future Phase 8+ extension) gives it a reason to try again.
    # This test documents that behavior as real, not silently papering over
    # it with an assumed recovery mechanism that does not exist yet.
    llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
    router = AdaptiveRouter(deterministic=MockBackend(fixed_cost=0.1), llm=llm)

    router.decide(_ambiguous_observation(), ALLOWED_ACTIONS)
    assert router.failure_rate("llm") == 1.0
    attempts_before = router._attempts["llm"]

    llm.available = True
    router.decide(_ambiguous_observation(), ALLOWED_ACTIONS)
    # The router chose not to re-attempt llm at all - its own accumulated
    # reliability penalty outweighs llm's quality bonus, so llm's attempt
    # count is unchanged even though it would have succeeded this time.
    assert router._attempts["llm"] == attempts_before
    assert router.failure_rate("llm") == 1.0


def test_dual_backend_failure_raises_rather_than_fabricating_an_action():
    llm = DegradableBackend(inner=MockBackend(fixed_cost=0.9), available=False)
    deterministic = DegradableBackend(inner=MockBackend(fixed_cost=0.1), available=False)
    router = AdaptiveRouter(deterministic=deterministic, llm=llm)
    with pytest.raises(RuntimeError):
        router.decide(_ambiguous_observation(), ALLOWED_ACTIONS)


def test_degradable_backend_raises_injected_failure_type():
    backend = DegradableBackend(inner=MockBackend(), available=False)
    with pytest.raises(InjectedFailure):
        backend.decide(_ambiguous_observation(), ALLOWED_ACTIONS)
