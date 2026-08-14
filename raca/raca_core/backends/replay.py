"""Scripted ReasoningBackend that replays a fixed action sequence.

Port of `agent_core.replay_agent.ReplayAgent`. Gives integration tests a
fully deterministic decision source with zero simulation variance,
independent of DeterministicBackend's cost math being correct.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, List

from raca_core.contracts import CognitiveAction, ReasoningBackend, RobotObservation


@dataclass
class ReplayBackend(ReasoningBackend):
    """Returns `script[i]` on the i-th call to `decide()`; `WAIT` once exhausted."""

    script: List[CognitiveAction] = field(default_factory=list)
    _calls: int = field(default=0, init=False, repr=False)

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        if self._calls < len(self.script):
            action = self.script[self._calls]
        else:
            action = CognitiveAction(action="WAIT")
        self._calls += 1
        return action
