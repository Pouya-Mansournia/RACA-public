"""Config-driven backend construction (master prompt Phase 3).

"Changing a backend should require only configuration... no environment
logic should change." `build_backend(config)` is the single place a
backend name string turns into a live `ReasoningBackend` instance -
`LightweightWorld` (and any future adapter) only ever needs to call this,
never import a concrete backend class directly.
"""
from __future__ import annotations

from typing import Any, Dict

from raca_core.contracts import ReasoningBackend

_KNOWN_BACKENDS = frozenset(
    {
        "deterministic",
        "replay",
        "mock",
        "local_llm",
        "always_deterministic",
        "always_llm",
        "fixed_ambiguity_threshold",
        "random_router",
        "simple_rule_router",
        "adaptive_router",
    }
)


def build_backend(config: Dict[str, Any]) -> ReasoningBackend:
    """`config` example: `{"backend": "deterministic"}` or
    `{"backend": "local_llm", "model": "llama3.2:1b", "fallback": "deterministic"}`.
    """
    name = config.get("backend", "deterministic")
    if name not in _KNOWN_BACKENDS:
        raise ValueError(f"unknown backend {name!r}, known: {sorted(_KNOWN_BACKENDS)}")

    if name == "deterministic":
        from raca_core.backends.deterministic import DeterministicBackend

        return DeterministicBackend()

    if name == "replay":
        from raca_core.backends.replay import ReplayBackend

        return ReplayBackend(script=list(config.get("script", [])))

    if name == "mock":
        from raca_core.backends.mock import MockBackend

        return MockBackend(fixed_cost=config.get("fixed_cost", 0.5))

    if name == "local_llm":
        from raca_core.backends.local_llm import LocalLLMBackend
        from raca_core.ollama_client import OllamaClient

        fallback_name = config.get("fallback", "deterministic")
        fallback_backend = (
            build_backend({"backend": fallback_name}) if fallback_name is not None else None
        )
        client = OllamaClient(model=config.get("model", "qwen2.5:7b"))
        return LocalLLMBackend(
            client=client,
            max_retries=config.get("max_retries", 2),
            fallback=fallback_backend,
        )

    # Static routing baselines (Phase 6): all take an inner "deterministic"
    # and "llm" backend pair, built from their own sub-configs so a router
    # can itself be pointed at, e.g., a MockBackend in tests without
    # touching this function.
    det_config = config.get("deterministic_config", {"backend": "deterministic"})
    llm_config = config.get("llm_config", {"backend": "local_llm"})
    deterministic_backend = build_backend(det_config)
    llm_backend = build_backend(llm_config)

    if name == "always_deterministic":
        from raca_core.router.static import AlwaysDeterministicRouter

        return AlwaysDeterministicRouter(deterministic=deterministic_backend, llm=llm_backend)

    if name == "always_llm":
        from raca_core.router.static import AlwaysLLMRouter

        return AlwaysLLMRouter(deterministic=deterministic_backend, llm=llm_backend)

    if name == "fixed_ambiguity_threshold":
        from raca_core.router.static import FixedAmbiguityThresholdRouter

        return FixedAmbiguityThresholdRouter(
            deterministic=deterministic_backend,
            llm=llm_backend,
            ambiguity_threshold=config.get("ambiguity_threshold", 0.0),
        )

    if name == "random_router":
        from raca_core.router.static import RandomRouter

        return RandomRouter(
            deterministic=deterministic_backend,
            llm=llm_backend,
            llm_probability=config.get("llm_probability", 0.5),
            seed=config.get("seed", 0),
        )

    if name == "simple_rule_router":
        from raca_core.router.static import SimpleRuleRouter

        return SimpleRuleRouter(
            deterministic=deterministic_backend,
            llm=llm_backend,
            urgency_threshold=config.get("urgency_threshold", 0.7),
            ambiguity_threshold=config.get("ambiguity_threshold", 0.5),
        )

    # name == "adaptive_router" (RACA V1, Phase 7)
    from raca_core.difficulty import AMBIGUITY_MARGIN_SCALE, DifficultyEstimator
    from raca_core.router.adaptive import LATENCY_PRIORS_SEC, AdaptiveRouter

    kwargs = dict(
        deterministic=deterministic_backend,
        llm=llm_backend,
        lambda_latency=config.get("lambda_latency", 0.1),
        quality_bonus_scale=config.get("quality_bonus_scale", 0.5),
        lambda_reliability=config.get("lambda_reliability", 2.0),
        urgency_aware=config.get("urgency_aware", True),
        latency_priors_sec=config.get("latency_priors_sec", dict(LATENCY_PRIORS_SEC)),
    )
    if "ambiguity_margin_scale" in config:
        kwargs["estimator"] = DifficultyEstimator(
            ambiguity_margin_scale=config.get("ambiguity_margin_scale", AMBIGUITY_MARGIN_SCALE)
        )
    return AdaptiveRouter(**kwargs)
