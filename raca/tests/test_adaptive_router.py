from __future__ import annotations

from raca_core.backends.mock import MockBackend
from raca_core.config import build_backend
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


def _clear_observation(battery_soc=1.0):
    return RobotObservation(
        robot_id="robot1",
        x=0.0,
        y=0.0,
        battery_soc=battery_soc,
        degradation_risk=0.0,
        utilization=0.0,
        candidate_stations=(
            StationCandidate(name="near", side="output", x=1.0, y=0.0),
            StationCandidate(name="far", side="output", x=19.0, y=0.0),
        ),
    )


def _router():
    return AdaptiveRouter(deterministic=MockBackend(fixed_cost=0.1), llm=MockBackend(fixed_cost=0.9))


def test_prefers_llm_when_ambiguous_and_not_urgent():
    router = _router()
    router.decide(_ambiguous_observation(battery_soc=1.0), ALLOWED_ACTIONS)
    assert router.stats.llm_decisions == 1
    assert router.stats.deterministic_decisions == 0


def test_prefers_deterministic_when_ambiguous_but_urgent():
    router = _router()
    # Same ambiguous geometry, but battery critically low -> urgency high
    # enough that the latency penalty on the slow LLM backend outweighs its
    # quality bonus - this is the whole point of the utility formula's
    # urgency-scaled latency term.
    router.decide(_ambiguous_observation(battery_soc=0.02), ALLOWED_ACTIONS)
    assert router.stats.deterministic_decisions == 1
    assert router.stats.llm_decisions == 0


def test_prefers_deterministic_when_clear_and_not_urgent():
    router = _router()
    router.decide(_clear_observation(battery_soc=1.0), ALLOWED_ACTIONS)
    assert router.stats.deterministic_decisions == 1
    assert router.stats.llm_decisions == 0


def test_latency_history_updates_after_each_call():
    router = _router()
    assert router._latency_history == {}
    router.decide(_clear_observation(), ALLOWED_ACTIONS)
    assert "deterministic" in router._latency_history
    assert len(router._latency_history["deterministic"]) == 1


def test_zero_latency_prior_for_llm_would_always_win_when_ambiguous():
    # Sanity check on the formula itself, not the router's default config:
    # if LLM were free (latency prior 0), it should win whenever it has any
    # quality bonus at all, regardless of urgency.
    router = AdaptiveRouter(
        deterministic=MockBackend(),
        llm=MockBackend(),
        latency_priors_sec={"deterministic": 0.0001, "llm": 0.0},
    )
    router.decide(_ambiguous_observation(battery_soc=0.0), ALLOWED_ACTIONS)
    assert router.stats.llm_decisions == 1


def test_build_backend_constructs_adaptive_router():
    router = build_backend(
        {
            "backend": "adaptive_router",
            "deterministic_config": {"backend": "mock", "fixed_cost": 0.1},
            "llm_config": {"backend": "mock", "fixed_cost": 0.9},
        }
    )
    assert isinstance(router, AdaptiveRouter)
    action = router.decide(_clear_observation(), ALLOWED_ACTIONS)
    assert action.action in ALLOWED_ACTIONS
