"""Domain profiles (master prompt PHASE 10).

"Test whether the value of reasoning depends on the domain... Same RACA
architecture. Different domain adapters/configuration. No redesign of the
core router."

A domain profile is nothing more than a set of `AdaptiveRouter` config
values - it does not change `raca_core`'s code, `LightweightWorld`'s code,
or the router's formula. This is deliberate: if testing a new domain
required redesigning the router, that would already be evidence against
the model-agnostic/domain-agnostic architecture claim this project is
trying to establish.

Two profiles, matching the master prompt's own Domain A/B framing:

  - `warehouse_failover` (Domain A, time-critical): high penalty for
    decision latency - this project's own Phase 4/6/7 measurements
    (deterministic ~0.0001s vs. real local LLM ~3.9s) are what
    `lambda_latency`'s default value was already calibrated against.
  - `service_robot` (Domain B, time-tolerant / semantically complex):
    lower latency penalty - a lower `lambda_latency` models a domain where
    an extra few seconds of reasoning is a minor cost relative to the task
    (e.g. a receptionist/concierge robot answering a request), and a higher
    `quality_bonus_scale` models a domain where contextual/semantic
    reasoning plausibly matters more per decision. Both numbers are
    PROVISIONAL MODELING CHOICES for a domain that has no dedicated
    real-world adapter or dataset in this repository yet - documented
    honestly as such, not measured from a real service-robot deployment.
"""
from __future__ import annotations

from typing import Any, Dict

DOMAIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "warehouse_failover": {
        "lambda_latency": 0.1,
        "quality_bonus_scale": 0.5,
        "lambda_reliability": 2.0,
    },
    "service_robot": {
        "lambda_latency": 0.02,
        "quality_bonus_scale": 0.8,
        "lambda_reliability": 2.0,
    },
}


def domain_router_config(domain_name: str, **overrides: Any) -> Dict[str, Any]:
    if domain_name not in DOMAIN_PROFILES:
        raise ValueError(f"unknown domain {domain_name!r}, known: {sorted(DOMAIN_PROFILES)}")
    config = {"backend": "adaptive_router", **DOMAIN_PROFILES[domain_name]}
    config.update(overrides)
    return config
