"""MockBackend: a trivially simple ReasoningBackend for pluggability tests.

Master prompt Phase 3's explicit backend list: DeterministicBackend,
LocalLLMBackend, MockBackend, ReplayBackend. Unlike `ReplayBackend` (which
replays a fixed pre-recorded script, ignoring `decide()`'s inputs entirely),
`MockBackend` DOES look at the observation but answers with a trivial,
deliberately non-optimal policy (always bid for the first candidate
station, at a fixed cost) - useful as the simplest possible "this backend
is genuinely live and responding to input" smoke-test double, distinct from
both the real cost formula (`DeterministicBackend`) and a canned script
(`ReplayBackend`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet

from raca_core.contracts import CognitiveAction, ReasoningBackend, RobotObservation


@dataclass
class MockBackend(ReasoningBackend):
    fixed_cost: float = 0.5

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        if not observation.candidate_stations:
            return CognitiveAction(action="WAIT")
        first = observation.candidate_stations[0]
        return CognitiveAction(action="BID_FOR_TASK", station_name=first.name, cost=self.fixed_cost)
