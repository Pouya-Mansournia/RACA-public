from __future__ import annotations

from raca_core.backends.deterministic import DeterministicBackend
from raca_core.contracts import ALLOWED_ACTIONS, RobotObservation, StationCandidate


def _observation(**overrides):
    defaults = dict(
        robot_id="robot1",
        x=0.0,
        y=0.0,
        battery_soc=1.0,
        degradation_risk=0.0,
        utilization=0.0,
        candidate_stations=(
            StationCandidate(name="output_station_1", side="output", x=5.0, y=0.0),
            StationCandidate(name="output_station_2", side="output", x=1.0, y=0.0),
        ),
    )
    defaults.update(overrides)
    return RobotObservation(**defaults)


def test_no_candidates_returns_wait():
    backend = DeterministicBackend()
    observation = _observation(candidate_stations=())
    action = backend.decide(observation, ALLOWED_ACTIONS)
    assert action.action == "WAIT"


def test_picks_lowest_cost_candidate():
    backend = DeterministicBackend()
    observation = _observation()
    action = backend.decide(observation, ALLOWED_ACTIONS)
    assert action.action == "BID_FOR_TASK"
    assert action.station_name == "output_station_2"  # closer -> lower cost


def test_cost_formula_matches_prior_research_line_exactly():
    # 0.7 * normalized_distance + 0.3 * energy_risk, world normalizer = 20.0,
    # battery_soc=1.0 -> energy_risk=0.0 -- byte-for-byte agent_core.RuleAgent's
    # documented defaults (src/agent_core/agent_core/rule_agent.py).
    backend = DeterministicBackend()
    observation = _observation(x=0.0, y=0.0, battery_soc=1.0)
    action = backend.decide(observation, ALLOWED_ACTIONS)
    expected_cost = 0.7 * (1.0 / 20.0)
    assert action.cost == expected_cost


def test_ties_broken_by_station_name():
    backend = DeterministicBackend()
    observation = _observation(
        candidate_stations=(
            StationCandidate(name="b_station", side="output", x=3.0, y=0.0),
            StationCandidate(name="a_station", side="output", x=3.0, y=0.0),
        )
    )
    action = backend.decide(observation, ALLOWED_ACTIONS)
    assert action.station_name == "a_station"


def test_rank_exposes_full_ordering():
    backend = DeterministicBackend()
    observation = _observation()
    ranked = backend.rank(observation)
    assert [c.name for c, _ in ranked] == ["output_station_2", "output_station_1"]
