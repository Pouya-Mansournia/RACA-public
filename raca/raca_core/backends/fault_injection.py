"""Controllable fault injection for testing router self-calibration and
stress resilience (master prompt PHASES 8 and 12).

`DegradableBackend` wraps any `ReasoningBackend`; a caller flips its public
`available`/`extra_latency_sec` attributes mid-run to simulate a backend
going slow or going down, WITHOUT touching the router or the wrapped
backend's own code - the same "inject controlled degradation, confirm
adaptation" pattern the master prompt asks for at both phases.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import FrozenSet

from raca_core.contracts import CognitiveAction, ReasoningBackend, RobotObservation


class InjectedFailure(RuntimeError):
    """Raised by `DegradableBackend` when `available=False` - a real
    exception a router must be able to survive, not a special sentinel
    value that could be silently swallowed."""


@dataclass
class DegradableBackend(ReasoningBackend):
    inner: ReasoningBackend
    available: bool = True
    extra_latency_sec: float = 0.0

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        if not self.available:
            raise InjectedFailure("backend unavailable (injected)")
        if self.extra_latency_sec > 0:
            time.sleep(self.extra_latency_sec)
        return self.inner.decide(observation, allowed_actions)


@dataclass
class FallbackBackend(ReasoningBackend):
    """Wraps `primary`; on any exception from `primary.decide()`, catches it
    and calls `fallback.decide()` instead - the SAME try/except-and-retry
    logic `AdaptiveRouter._try_decide` uses internally, extracted here so it
    can be applied to a STATIC router's backend too.

    Exists specifically for the final pre-submission red-team audit's
    Critical Audit 5 finding: the static routers in `router/static.py` call
    their backends directly, with no exception handling at all, so any
    "static router crashes, AdaptiveRouter survives" comparison is
    confounded between the ROUTING POLICY and the presence/absence of this
    wrapper. Wrapping a static router's backend in `FallbackBackend` gives
    it the identical safety net, isolating the routing-policy variable.
    """

    primary: ReasoningBackend
    fallback: ReasoningBackend

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        try:
            return self.primary.decide(observation, allowed_actions)
        except Exception:
            return self.fallback.decide(observation, allowed_actions)
