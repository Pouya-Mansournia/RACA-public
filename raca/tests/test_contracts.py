from __future__ import annotations

import pytest

from raca_core.contracts import ALLOWED_ACTIONS, CognitiveAction, StationCandidate


def test_allowed_actions_unchanged_from_prior_line():
    assert ALLOWED_ACTIONS == frozenset({"BID_FOR_TASK", "WAIT"})


def test_wait_action_needs_no_station_or_cost():
    action = CognitiveAction(action="WAIT")
    assert action.station_name is None
    assert action.cost is None


def test_bid_for_task_requires_station_name_and_cost():
    with pytest.raises(ValueError):
        CognitiveAction(action="BID_FOR_TASK")


def test_bid_for_task_valid():
    action = CognitiveAction(action="BID_FOR_TASK", station_name="output_station_1", cost=0.5)
    assert action.station_name == "output_station_1"
    assert action.cost == 0.5


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        CognitiveAction(action="FLY_TO_MOON")


def test_station_candidate_is_frozen():
    candidate = StationCandidate(name="s1", side="input", x=1.0, y=2.0)
    with pytest.raises(Exception):
        candidate.x = 5.0  # type: ignore[misc]
