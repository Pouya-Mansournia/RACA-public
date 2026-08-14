"""RACA V1 - cost-aware adaptive reasoning router (master prompt PHASE 7).

The router decides, per decision, which backend should answer it, using an
interpretable cost-aware utility (NOT reinforcement learning - the master
prompt explicitly says not to start there):

    U(b | x) = Q(b, x) - lambda_latency * L(b) * (1 + urgency(x))

Every term is either a documented modeling assumption or a real measured
quantity - never invented:

  - `L(b)`: mean measured decision latency for backend `b`, a running
    average over every call this router instance has actually made (self-
    seeded from `latency_priors_sec`, real numbers taken from this
    project's own Phase 4/6 measurements - see that constant's docstring -
    not guessed). This is a first taste of Phase 8's self-calibration
    (backend behavior changes routing), scoped down here to latency only;
    Phase 8 adds reliability/availability history on top of this same
    mechanism.
  - `urgency(x)`: `DifficultyEstimator`'s battery-derived urgency signal
    (Phase 5) - a real, measured feature of the observation.
  - `Q(b, x)`: expected decision quality. `Q(deterministic, x) = 1.0`
    (reference baseline - this project has no ground-truth quality label
    per decision to calibrate an absolute value against, so 1.0 is a
    reference point, not a claim of "perfect"). `Q(llm, x) = 1.0 +
    quality_bonus_scale * ambiguity(x)` - THIS IS A MODELING ASSUMPTION,
    not a measured quantity: it encodes master prompt Hypothesis 2 ("high-
    ambiguity decisions: LLM may improve decision quality enough to
    justify additional latency") as a testable prior, not a proven fact.
    Later phases (ablation, large-scale campaigns with real task-outcome
    labels) must validate or refute this assumption - it is not smuggled in
    as ground truth here.

No compute/monetary cost term is included: this project only runs a local,
free Ollama model with no per-token billing, so `C(b)` would be fabricated
data (master prompt: never invent what isn't measured). The formula stays
ready for a `C(b)` term once a paid backend exists (Phase 9).

PHASE 8 EXTENSION - self-calibration to backend reliability: the utility
above is extended with a third term,

    U(b | x) = Q(b, x)
               - lambda_latency * L(b) * (1 + urgency(x))
               - lambda_reliability * failure_rate(b)

`failure_rate(b)` is a real, self-updating ratio (failures / attempts) this
router tracks per backend from its OWN observed `decide()` outcomes - an
exception raised by a backend counts as a failure, matching the master
prompt's stress-testing framing ("backend timeout, unavailable, invalid
response"). A failing backend is never allowed to break the calling robot:
`decide()` catches the exception, records the failure, and immediately
falls back to the OTHER backend for that one call - the router's SELECTION
for future calls shifts away from the unreliable backend via the utility
penalty, while its per-call safety net (the try/except) is unconditional
and does not depend on the penalty having "caught up" yet.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List

from raca_core.contracts import CognitiveAction, ReasoningBackend, RobotObservation
from raca_core.difficulty import DifficultyEstimator
from raca_core.router.static import RouterStats

# Real numbers from this project's own measurements, not guesses:
# - deterministic: raca/docs mean latency observed in Phase 4/6
#   (~0.01-0.02 ms, i.e. ~0.00001-0.00002 sec) - use 0.0001 sec as a round,
#   slightly conservative prior.
# - llm: Phase 4's re-run with a real reachable local qwen2.5:7b model
#   (raca/tools/generate_backend_report.py), mean ~3.9 sec.
LATENCY_PRIORS_SEC: Dict[str, float] = {
    "deterministic": 0.0001,
    "llm": 3.9,
}


@dataclass
class AdaptiveRouter(ReasoningBackend):
    deterministic: ReasoningBackend
    llm: ReasoningBackend
    estimator: DifficultyEstimator = field(default_factory=DifficultyEstimator)
    lambda_latency: float = 0.1
    quality_bonus_scale: float = 0.5
    lambda_reliability: float = 2.0
    # Phase 11 ablation switch: when False, the latency penalty no longer
    # scales with urgency(x) (always uses a (1+0)=1 multiplier instead of
    # (1+urgency)) - isolates the marginal contribution of urgency-awareness
    # specifically, distinct from ambiguity-awareness (quality_bonus_scale)
    # or reliability-awareness (lambda_reliability), each independently
    # zeroable via their own existing parameter.
    urgency_aware: bool = True
    latency_priors_sec: Dict[str, float] = field(default_factory=lambda: dict(LATENCY_PRIORS_SEC))
    stats: RouterStats = field(default_factory=RouterStats, init=False)
    _latency_history: Dict[str, List[float]] = field(default_factory=dict, init=False, repr=False)
    _attempts: Dict[str, int] = field(default_factory=lambda: {"deterministic": 0, "llm": 0}, init=False, repr=False)
    _failures: Dict[str, int] = field(default_factory=lambda: {"deterministic": 0, "llm": 0}, init=False, repr=False)

    def _mean_latency_sec(self, backend_name: str) -> float:
        history = self._latency_history.get(backend_name)
        if not history:
            return self.latency_priors_sec[backend_name]
        return sum(history) / len(history)

    def failure_rate(self, backend_name: str) -> float:
        attempts = self._attempts[backend_name]
        return (self._failures[backend_name] / attempts) if attempts else 0.0

    def _utility(self, backend_name: str, ambiguity: float, urgency: float) -> float:
        quality = 1.0 + (self.quality_bonus_scale * ambiguity if backend_name == "llm" else 0.0)
        urgency_multiplier = (1.0 + urgency) if self.urgency_aware else 1.0
        latency_penalty = self.lambda_latency * self._mean_latency_sec(backend_name) * urgency_multiplier
        reliability_penalty = self.lambda_reliability * self.failure_rate(backend_name)
        return quality - latency_penalty - reliability_penalty

    def _backend(self, name: str) -> ReasoningBackend:
        return self.llm if name == "llm" else self.deterministic

    def _try_decide(
        self, backend_name: str, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ):
        """Returns (action, succeeded). Never raises - a failing backend must
        never break the calling robot (master prompt Phase 12's stress-test
        requirement, tested a full run ahead of Phase 12 itself here)."""
        self._attempts[backend_name] += 1
        started = time.perf_counter()
        try:
            action = self._backend(backend_name).decide(observation, allowed_actions)
        except Exception:
            self._failures[backend_name] += 1
            return None, False
        elapsed_sec = time.perf_counter() - started
        self._latency_history.setdefault(backend_name, []).append(elapsed_sec)
        return action, True

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        context = self.estimator.estimate(observation)
        u_deterministic = self._utility("deterministic", context.ambiguity, context.urgency)
        u_llm = self._utility("llm", context.ambiguity, context.urgency)

        chosen_name = "llm" if u_llm > u_deterministic else "deterministic"
        fallback_name = "deterministic" if chosen_name == "llm" else "llm"

        action, succeeded = self._try_decide(chosen_name, observation, allowed_actions)
        used_name = chosen_name
        if not succeeded:
            # Safety net: this call still needs an answer NOW, independent of
            # whether the utility penalty has caught up yet - try the other
            # backend once. If both fail, the caller's own backend contract
            # (LocalLLMBackend/DeterministicBackend) already never raises for
            # a routine input, so this is a genuine dual-failure edge case;
            # the exception propagates rather than fabricating an action.
            action, succeeded = self._try_decide(fallback_name, observation, allowed_actions)
            used_name = fallback_name
            if not succeeded:
                raise RuntimeError(
                    f"both backends failed for this decision (deterministic and llm)"
                )

        if used_name == "llm":
            self.stats.llm_decisions += 1
        else:
            self.stats.deterministic_decisions += 1
        return action
