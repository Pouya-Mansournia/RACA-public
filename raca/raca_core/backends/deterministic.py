"""Deterministic cost-based ReasoningBackend.

Faithful port of `agent_core.rule_agent.RuleAgent` - same formula, same
defaults, same tie-breaking - under RACA's `ReasoningBackend` contract.
Phase 1's output-equivalence test asserts this produces byte-identical
`cost`/`action`/`station_name` values to the original for the same inputs;
this module must never diverge from that formula without an explicit,
documented, intentional change (master prompt section 1's Phase 1
acceptance criterion: 100% output equivalence for identical inputs).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Tuple

from raca_core.contracts import (
    CognitiveAction,
    ReasoningBackend,
    RobotObservation,
    StationCandidate,
)

_MAX_EXPECTED_DISTANCE_M = 20.0  # world is ~15x20m - normalizes distance into [0, 1]


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


@dataclass(frozen=True)
class DeterministicBackend(ReasoningBackend):
    w_distance: float = 0.7
    w_energy: float = 0.3
    w_health: float = 0.0
    w_workload: float = 0.0

    def _cost(self, observation: RobotObservation, x: float, y: float) -> float:
        normalized_distance = min(
            _distance(observation.x, observation.y, x, y) / _MAX_EXPECTED_DISTANCE_M, 1.0
        )
        energy_risk = 1.0 - observation.battery_soc
        return (
            self.w_distance * normalized_distance
            + self.w_energy * energy_risk
            + self.w_health * observation.degradation_risk
            + self.w_workload * observation.utilization
        )

    def rank(self, observation: RobotObservation) -> List[Tuple[StationCandidate, float]]:
        """All candidates sorted by cost ascending (ties broken by station name)."""
        return sorted(
            ((c, self._cost(observation, c.x, c.y)) for c in observation.candidate_stations),
            key=lambda pair: (pair[1], pair[0].name),
        )

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        ranked = self.rank(observation)
        if not ranked:
            return CognitiveAction(action="WAIT")

        best, best_cost = ranked[0]
        return CognitiveAction(action="BID_FOR_TASK", station_name=best.name, cost=best_cost)
