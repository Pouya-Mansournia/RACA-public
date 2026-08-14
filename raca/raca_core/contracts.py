"""Platform-independent observation/action contracts (RACA master prompt section 7).

This is a faithful, behavior-preserving port of
`src/agent_core/agent_core/interfaces.py` (Phase 6 of the prior research
line) under RACA's own naming, plus one deliberate change: `robot_id` and
station-candidate framing are made explicit as ROS-independent so this
module never needs to know it originated in a ROS-coupled system.

Deliberately NOT extended yet with the master prompt's full
`RobotObservation` example schema (`urgency`, `ambiguity`, `risk`,
`peer_states`, `environment_context`, ...): Phase 1's job is proving the
existing deterministic decision logic is equivalence-preserving once
extracted from ROS 2, not redesigning the schema. Those fields belong to
Phase 5 (DecisionContext / DifficultyEstimator) and Phase 9 (Reasoning
Router inputs), where they will be added with a defined data source for
each - per the master prompt's own "do not over-engineer the first version"
rule (section 7).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

ALLOWED_ACTIONS: FrozenSet[str] = frozenset({"BID_FOR_TASK", "WAIT"})


@dataclass(frozen=True)
class StationCandidate:
    """One free station a robot could bid for, as seen in its local belief state."""

    name: str
    side: str  # "input" | "output"
    x: float
    y: float


@dataclass(frozen=True)
class RobotObservation:
    """Everything a ReasoningBackend is allowed to see for one decision.

    Field-for-field equivalent to `agent_core.interfaces.Observation` - this
    is intentionally a rename/relocation, not a redesign, so Phase 1's
    output-equivalence test has a meaningful baseline to compare against.
    """

    robot_id: str
    x: float
    y: float
    battery_soc: float
    degradation_risk: float
    utilization: float
    candidate_stations: Tuple[StationCandidate, ...]


@dataclass(frozen=True)
class CognitiveAction:
    """A validated, structured decision - never raw text or code."""

    action: str
    station_name: Optional[str] = None
    cost: Optional[float] = None

    def __post_init__(self) -> None:
        if self.action not in ALLOWED_ACTIONS:
            raise ValueError(f"unknown action {self.action!r}, allowed: {sorted(ALLOWED_ACTIONS)}")
        if self.action == "BID_FOR_TASK" and (self.station_name is None or self.cost is None):
            raise ValueError("BID_FOR_TASK requires station_name and cost")


class ReasoningBackend(ABC):
    """Provider-independent decision-making strategy for one robot.

    This is `agent_core.interfaces.AgentBackend` under RACA's naming
    (master prompt section 8's `ReasoningBackend` contract). No ROS
    import may ever appear in this module or in any concrete backend
    under `raca_core.backends`.
    """

    @abstractmethod
    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        """Return exactly one validated CognitiveAction given the current observation."""
        raise NotImplementedError
