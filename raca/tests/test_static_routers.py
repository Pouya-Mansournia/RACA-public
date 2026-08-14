from __future__ import annotations

from raca_core.backends.mock import MockBackend
from raca_core.config import build_backend
from raca_core.contracts import ALLOWED_ACTIONS, RobotObservation, StationCandidate
from raca_core.router.static import (
    AlwaysDeterministicRouter,
    AlwaysLLMRouter,
    FixedAmbiguityThresholdRouter,
    RandomRouter,
    SimpleRuleRouter,
)


def _observation(candidates, battery_soc=1.0):
    return RobotObservation(
        robot_id="robot1",
        x=0.0,
        y=0.0,
        battery_soc=battery_soc,
        degradation_risk=0.0,
        utilization=0.0,
        candidate_stations=tuple(candidates),
    )


def _clear_observation():
    return _observation(
        [
            StationCandidate(name="near", side="output", x=1.0, y=0.0),
            StationCandidate(name="far", side="output", x=19.0, y=0.0),
        ]
    )


def _ambiguous_observation():
    return _observation(
        [
            StationCandidate(name="a", side="output", x=5.0, y=-1.0),
            StationCandidate(name="b", side="output", x=5.0, y=1.0),
        ]
    )


def test_always_deterministic_never_calls_llm():
    router = AlwaysDeterministicRouter(deterministic=MockBackend(fixed_cost=0.1), llm=MockBackend(fixed_cost=0.9))
    for observation in (_clear_observation(), _ambiguous_observation()):
        router.decide(observation, ALLOWED_ACTIONS)
    assert router.stats.llm_decisions == 0
    assert router.stats.deterministic_decisions == 2
    assert router.stats.llm_invocation_rate == 0.0


def test_always_llm_never_calls_deterministic():
    router = AlwaysLLMRouter(deterministic=MockBackend(fixed_cost=0.1), llm=MockBackend(fixed_cost=0.9))
    for observation in (_clear_observation(), _ambiguous_observation()):
        router.decide(observation, ALLOWED_ACTIONS)
    assert router.stats.deterministic_decisions == 0
    assert router.stats.llm_invocation_rate == 1.0


def test_fixed_ambiguity_threshold_escalates_only_when_ambiguous():
    router = FixedAmbiguityThresholdRouter(
        deterministic=MockBackend(fixed_cost=0.1), llm=MockBackend(fixed_cost=0.9)
    )
    router.decide(_clear_observation(), ALLOWED_ACTIONS)
    router.decide(_ambiguous_observation(), ALLOWED_ACTIONS)
    assert router.stats.deterministic_decisions == 1
    assert router.stats.llm_decisions == 1


def test_random_router_is_deterministic_given_same_seed():
    router_a = RandomRouter(deterministic=MockBackend(), llm=MockBackend(), llm_probability=0.5, seed=42)
    router_b = RandomRouter(deterministic=MockBackend(), llm=MockBackend(), llm_probability=0.5, seed=42)
    observation = _clear_observation()
    for _ in range(20):
        router_a.decide(observation, ALLOWED_ACTIONS)
        router_b.decide(observation, ALLOWED_ACTIONS)
    assert router_a.stats == router_b.stats


def test_random_router_probability_zero_never_calls_llm():
    router = RandomRouter(deterministic=MockBackend(), llm=MockBackend(), llm_probability=0.0, seed=1)
    for _ in range(10):
        router.decide(_clear_observation(), ALLOWED_ACTIONS)
    assert router.stats.llm_decisions == 0


def test_simple_rule_router_prefers_deterministic_when_urgent_even_if_ambiguous():
    router = SimpleRuleRouter(deterministic=MockBackend(), llm=MockBackend())
    # Low battery -> high urgency -> must stay deterministic even though the
    # observation is also ambiguous, per this router's stated priority.
    urgent_and_ambiguous = _observation(
        [
            StationCandidate(name="a", side="output", x=5.0, y=-1.0),
            StationCandidate(name="b", side="output", x=5.0, y=1.0),
        ],
        battery_soc=0.1,
    )
    router.decide(urgent_and_ambiguous, ALLOWED_ACTIONS)
    assert router.stats.llm_decisions == 0
    assert router.stats.deterministic_decisions == 1


def test_simple_rule_router_escalates_when_ambiguous_and_not_urgent():
    router = SimpleRuleRouter(deterministic=MockBackend(), llm=MockBackend())
    router.decide(_ambiguous_observation(), ALLOWED_ACTIONS)
    assert router.stats.llm_decisions == 1


def test_build_backend_constructs_every_router_by_name():
    for name in (
        "always_deterministic",
        "always_llm",
        "fixed_ambiguity_threshold",
        "random_router",
        "simple_rule_router",
    ):
        router = build_backend(
            {
                "backend": name,
                "deterministic_config": {"backend": "mock", "fixed_cost": 0.1},
                "llm_config": {"backend": "mock", "fixed_cost": 0.9},
            }
        )
        action = router.decide(_clear_observation(), ALLOWED_ACTIONS)
        assert action.action in ALLOWED_ACTIONS
