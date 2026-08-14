"""Static routing baselines (master prompt PHASE 6).

"Before adaptive routing, test simple routing strategies... These become
the baselines against which RACA must later compete." None of these
classes learn or adapt during a run - they are fixed policies, evaluated
on identical paired scenarios/seeds so a later adaptive router (Phase 7)
has a real, not strawman, comparison.

Every router here implements `ReasoningBackend` itself, so `LightweightWorld`
(or any adapter) never needs to know it's talking to a router instead of a
single backend - the same substitutability principle Phase 3 already
established for individual backends.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import FrozenSet, Optional

from raca_core.contracts import CognitiveAction, ReasoningBackend, RobotObservation
from raca_core.difficulty import DifficultyEstimator


@dataclass
class RouterStats:
    deterministic_decisions: int = 0
    llm_decisions: int = 0

    @property
    def total(self) -> int:
        return self.deterministic_decisions + self.llm_decisions

    @property
    def llm_invocation_rate(self) -> Optional[float]:
        return (self.llm_decisions / self.total) if self.total else None


@dataclass
class _BaseRouter(ReasoningBackend):
    deterministic: ReasoningBackend
    llm: ReasoningBackend
    stats: RouterStats = field(default_factory=RouterStats, init=False)

    def _decide_deterministic(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        self.stats.deterministic_decisions += 1
        return self.deterministic.decide(observation, allowed_actions)

    def _decide_llm(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        self.stats.llm_decisions += 1
        return self.llm.decide(observation, allowed_actions)


@dataclass
class AlwaysDeterministicRouter(_BaseRouter):
    """Baseline: never consult the LLM, regardless of difficulty."""

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        return self._decide_deterministic(observation, allowed_actions)


@dataclass
class AlwaysLLMRouter(_BaseRouter):
    """Baseline: always consult the LLM, regardless of difficulty."""

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        return self._decide_llm(observation, allowed_actions)


@dataclass
class FixedAmbiguityThresholdRouter(_BaseRouter):
    """Baseline: escalate to the LLM only when DifficultyEstimator's
    ambiguity signal exceeds a fixed threshold. With the default threshold
    (0.0 - any nonzero ambiguity), this reproduces
    `agent_core.hybrid_agent.HybridAgent`'s exact escalation rule (Phase 9
    of the prior research line), now expressed through the general-purpose
    `DifficultyEstimator` instead of a bespoke inline computation.
    """

    ambiguity_threshold: float = 0.0
    estimator: DifficultyEstimator = field(default_factory=DifficultyEstimator)

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        context = self.estimator.estimate(observation)
        if context.ambiguity > self.ambiguity_threshold:
            return self._decide_llm(observation, allowed_actions)
        return self._decide_deterministic(observation, allowed_actions)


@dataclass
class RandomRouter(_BaseRouter):
    """Baseline: ignore difficulty entirely, pick a backend with a fixed
    probability. Exists to prove any routing signal beats no signal at all -
    a router that doesn't outperform this is not doing useful routing."""

    llm_probability: float = 0.5
    seed: int = 0
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        if self._rng.random() < self.llm_probability:
            return self._decide_llm(observation, allowed_actions)
        return self._decide_deterministic(observation, allowed_actions)


@dataclass
class SimpleRuleRouter(_BaseRouter):
    """Baseline: a hand-written multi-signal rule, distinct from the
    single-threshold FixedAmbiguityThresholdRouter - urgency takes priority
    (a robot that is critically low on battery gets the fast deterministic
    path even if the decision is ambiguous, since latency itself is a risk
    at that point), otherwise ambiguity decides."""

    urgency_threshold: float = 0.7
    ambiguity_threshold: float = 0.5
    estimator: DifficultyEstimator = field(default_factory=DifficultyEstimator)

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        context = self.estimator.estimate(observation)
        if context.urgency > self.urgency_threshold:
            return self._decide_deterministic(observation, allowed_actions)
        if context.ambiguity > self.ambiguity_threshold:
            return self._decide_llm(observation, allowed_actions)
        return self._decide_deterministic(observation, allowed_actions)
