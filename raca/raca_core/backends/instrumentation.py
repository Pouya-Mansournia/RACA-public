"""Latency/outcome instrumentation wrapper (master prompt Phase 4).

`TimingWrapperBackend` wraps any `ReasoningBackend` and records real,
measured `time.perf_counter()` latency and outcome for every `decide()`
call - the empirical basis Phase 4 asks for ("measure each reasoning
backend independently... decision latency, success rate, invalid-action
rate, fallback rate") without modifying any backend's own code, and without
guessing/estimating any number it doesn't actually observe (never fabricate
what wasn't measured - the same rule the prior research line's
`docs/current_limitations.md` follows throughout).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import FrozenSet, List

from raca_core.contracts import ALLOWED_ACTIONS, CognitiveAction, ReasoningBackend, RobotObservation


@dataclass
class DecisionRecord:
    latency_sec: float
    action: str
    valid: bool
    fallback_used: bool


@dataclass
class TimingWrapperBackend(ReasoningBackend):
    inner: ReasoningBackend
    records: List[DecisionRecord] = field(default_factory=list, init=False, repr=False)

    def decide(
        self, observation: RobotObservation, allowed_actions: FrozenSet[str]
    ) -> CognitiveAction:
        started = time.perf_counter()
        try:
            action = self.inner.decide(observation, allowed_actions)
            valid = action.action in allowed_actions
        except Exception:
            latency_sec = time.perf_counter() - started
            self.records.append(
                DecisionRecord(latency_sec=latency_sec, action="ERROR", valid=False, fallback_used=False)
            )
            raise
        latency_sec = time.perf_counter() - started
        # LocalLLMBackend (and HybridAgent-style backends) expose a
        # last_decision_meta.fallback_used flag when present; other
        # backends simply never fall back, so this reads False for them.
        meta = getattr(self.inner, "last_decision_meta", None)
        fallback_used = bool(getattr(meta, "fallback_used", False)) if meta is not None else False
        self.records.append(
            DecisionRecord(latency_sec=latency_sec, action=action.action, valid=valid, fallback_used=fallback_used)
        )
        return action

    def stats(self) -> dict:
        if not self.records:
            return {
                "decisions": 0,
                "mean_latency_sec": None,
                "median_latency_sec": None,
                "p95_latency_sec": None,
                "validity_rate": None,
                "fallback_rate": None,
            }
        latencies = sorted(r.latency_sec for r in self.records)
        n = len(latencies)
        p95_index = min(n - 1, int(round(0.95 * (n - 1))))
        return {
            "decisions": n,
            "mean_latency_sec": sum(latencies) / n,
            "median_latency_sec": latencies[n // 2],
            "p95_latency_sec": latencies[p95_index],
            "validity_rate": sum(1 for r in self.records if r.valid) / n,
            "fallback_rate": sum(1 for r in self.records if r.fallback_used) / n,
        }
