from __future__ import annotations

from raca_core.backends.replay import ReplayBackend
from raca_core.contracts import ALLOWED_ACTIONS, CognitiveAction, RobotObservation


def _observation():
    return RobotObservation(
        robot_id="robot1",
        x=0.0,
        y=0.0,
        battery_soc=1.0,
        degradation_risk=0.0,
        utilization=0.0,
        candidate_stations=(),
    )


def test_replays_script_in_order_then_waits():
    script = [
        CognitiveAction(action="BID_FOR_TASK", station_name="s1", cost=0.1),
        CognitiveAction(action="WAIT"),
    ]
    backend = ReplayBackend(script=script)
    observation = _observation()

    first = backend.decide(observation, ALLOWED_ACTIONS)
    second = backend.decide(observation, ALLOWED_ACTIONS)
    third = backend.decide(observation, ALLOWED_ACTIONS)  # past end of script

    assert first.station_name == "s1"
    assert second.action == "WAIT"
    assert third.action == "WAIT"
