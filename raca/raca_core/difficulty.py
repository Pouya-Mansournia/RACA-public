"""Decision difficulty quantification (master prompt PHASE 5).

"Do not use vague labels like easy/hard. Define measurable features."
"Difficulty metrics are computed without knowing the final outcome. Avoid
target leakage."

`DifficultyEstimator.estimate()` takes only a `RobotObservation` and the
already-free candidate list a `ReasoningBackend` would also see - never the
action a backend actually chose, never which backend was used, never the
task's eventual outcome. This is what makes it safe to use as a ROUTING
input later (Phase 7): if difficulty depended on the decision or its
result, using it to choose the backend would be circular.

Only two of the master prompt's candidate signals have a real, live data
source in this codebase today (see `raca_core.contracts.RobotObservation`'s
own docstring - urgency/risk/peer-conflict fields were deliberately not
added in Phase 1 without a defined source): ambiguity (from the
deterministic cost ranking) and a battery-derived urgency proxy. The rest
(state uncertainty, peer conflict, resource contention, historical backend
disagreement) are named here as explicit future extension points, not
silently invented with fabricated data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from raca_core.backends.deterministic import DeterministicBackend
from raca_core.contracts import RobotObservation

# ORIGINAL VALUE: 0.05, matching HybridAgent's own ambiguity_margin (Phase
# 9 of the prior research line, src/agent_core/agent_core/hybrid_agent.py).
# SUPERSEDED as the default by the Phase 5-revision recalibration (see
# docs/research_journal.md, post-Phase-14 entry): Phase 13's large-N
# campaign found the original scale made near-ties the statistical norm
# (not the exception) under this warehouse's dense station grid, because
# the cost formula's sqrt-distance term compresses adjacent-station cost
# gaps far below their nominal 2m spacing whenever a robot is far in x
# from the station line. `raca/tools/calibrate_ambiguity_scale.py` swept
# candidate values (0.001-0.05) against the SAME N=20 paired-seed
# methodology and selected 0.04 as the LARGEST (most conservative, closest
# to the original) value at which BOTH quality-preservation AND
# cost-reduction acceptance criteria passed simultaneously - a smooth,
# monotonic tradeoff was observed across the whole sweep (see that
# script's own output), not a cliff picked arbitrarily.
#
# Phases 1-13's ALREADY-RECORDED results in docs/research_journal.md all
# used the original 0.05 value and remain exactly as measured - this
# change affects only NEW work using this default going forward, per
# master prompt section 20's "any methodological change must be recorded"
# rule.
AMBIGUITY_MARGIN_SCALE = 0.04


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class DecisionContext:
    """Measurable, outcome-independent features of one decision.

    Every field here must be computable BEFORE any backend is asked to
    decide, and without looking at what any backend actually returns -
    that is the target-leakage rule this dataclass exists to enforce
    structurally, not just by convention.
    """

    num_candidates: int
    top_two_cost_margin: Optional[float]  # None when fewer than 2 candidates
    ambiguity: float  # 0.0 (clear winner or trivial) .. 1.0 (near-perfect tie)
    urgency: float  # 0.0 (full battery) .. 1.0 (empty battery) - a proxy, see module docstring
    risk: float  # currently == observation.degradation_risk (always 0.0 today - no live source yet)

    def difficulty_score(
        self,
        w_ambiguity: float = 0.6,
        w_urgency: float = 0.3,
        w_risk: float = 0.1,
    ) -> float:
        """A single scalar in [0, 1], provided for convenience only.

        These weights are a documented, provisional starting point - NOT
        fitted or validated against any outcome data (that would itself be
        a form of leakage at this phase). Phase 6/7 baselines must not
        assume this particular combination is correct; they exist to test
        that. Do not read this score as "the" difficulty without knowing
        the weights it was computed with.
        """
        return _clamp01(w_ambiguity * self.ambiguity + w_urgency * self.urgency + w_risk * self.risk)


class DifficultyEstimator:
    """Computes a `DecisionContext` from a `RobotObservation` and its
    already-free candidate list, using the SAME cost ranking
    `DeterministicBackend.rank()` would compute internally - reused rather
    than reimplemented so the ambiguity signal always matches whatever the
    deterministic backend would actually be uncertain about.
    """

    def __init__(
        self,
        ranker: Optional[DeterministicBackend] = None,
        ambiguity_margin_scale: float = AMBIGUITY_MARGIN_SCALE,
    ) -> None:
        self._ranker = ranker or DeterministicBackend()
        self.ambiguity_margin_scale = ambiguity_margin_scale

    def estimate(self, observation: RobotObservation) -> DecisionContext:
        ranked = self._ranker.rank(observation)
        num_candidates = len(ranked)

        if num_candidates < 2:
            # 0 or 1 candidate: nothing to be ambiguous about, matching
            # HybridAgent's own never-escalate rule for this exact case.
            margin = None
            ambiguity = 0.0
        else:
            (_, best_cost), (_, second_cost) = ranked[0], ranked[1]
            margin = second_cost - best_cost
            ambiguity = _clamp01(1.0 - margin / self.ambiguity_margin_scale)

        urgency = _clamp01(1.0 - observation.battery_soc)
        risk = _clamp01(observation.degradation_risk)

        return DecisionContext(
            num_candidates=num_candidates,
            top_two_cost_margin=margin,
            ambiguity=ambiguity,
            urgency=urgency,
            risk=risk,
        )
