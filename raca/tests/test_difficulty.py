from __future__ import annotations

from raca_core.contracts import RobotObservation, StationCandidate
from raca_core.difficulty import DifficultyEstimator


def _observation(candidates, battery_soc=1.0, degradation_risk=0.0):
    return RobotObservation(
        robot_id="robot1",
        x=0.0,
        y=0.0,
        battery_soc=battery_soc,
        degradation_risk=degradation_risk,
        utilization=0.0,
        candidate_stations=tuple(candidates),
    )


def test_zero_candidates_is_zero_ambiguity():
    estimator = DifficultyEstimator()
    context = estimator.estimate(_observation([]))
    assert context.num_candidates == 0
    assert context.top_two_cost_margin is None
    assert context.ambiguity == 0.0


def test_one_candidate_is_zero_ambiguity():
    estimator = DifficultyEstimator()
    context = estimator.estimate(
        _observation([StationCandidate(name="s1", side="output", x=5.0, y=0.0)])
    )
    assert context.num_candidates == 1
    assert context.ambiguity == 0.0


def test_near_tied_candidates_are_high_ambiguity():
    estimator = DifficultyEstimator()
    # Symmetric around the robot's origin -> near-identical cost, matching
    # the real warehouse geometry's own known ambiguous first-decision case
    # (docs/research_extension_plan.md Phase 9's live validation notes).
    context = estimator.estimate(
        _observation(
            [
                StationCandidate(name="a", side="output", x=5.0, y=-1.0),
                StationCandidate(name="b", side="output", x=5.0, y=1.0),
            ]
        )
    )
    assert context.ambiguity > 0.9


def test_clearly_separated_candidates_are_low_ambiguity():
    estimator = DifficultyEstimator()
    context = estimator.estimate(
        _observation(
            [
                StationCandidate(name="near", side="output", x=1.0, y=0.0),
                StationCandidate(name="far", side="output", x=19.0, y=0.0),
            ]
        )
    )
    assert context.ambiguity == 0.0


def test_low_battery_is_high_urgency():
    estimator = DifficultyEstimator()
    context = estimator.estimate(_observation([], battery_soc=0.05))
    assert context.urgency > 0.9


def test_full_battery_is_zero_urgency():
    estimator = DifficultyEstimator()
    context = estimator.estimate(_observation([], battery_soc=1.0))
    assert context.urgency == 0.0


def test_difficulty_score_is_bounded():
    estimator = DifficultyEstimator()
    context = estimator.estimate(_observation([], battery_soc=0.0, degradation_risk=1.0))
    score = context.difficulty_score()
    assert 0.0 <= score <= 1.0


def test_estimate_never_needs_a_chosen_action():
    # Structural leakage check: DifficultyEstimator.estimate's signature
    # only accepts a RobotObservation - there is no way to pass it a
    # CognitiveAction or backend identity even by mistake.
    import inspect

    signature = inspect.signature(DifficultyEstimator.estimate)
    assert list(signature.parameters) == ["self", "observation"]
