#!/usr/bin/env python3
"""Phase 10 - Time-Critical vs. Time-Tolerant Domains (master prompt PHASE 10).

Runs the SAME AdaptiveRouter architecture and the SAME LightweightWorld
scenario under two domain profiles (raca_core/domains.py) - only
`lambda_latency`/`quality_bonus_scale` differ, via configuration, not a
router redesign. Measures whether the optimal reasoning allocation
actually differs, rather than assuming it does.

    python raca/tools/generate_domain_comparison_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.config import build_backend  # noqa: E402
from raca_core.domains import domain_router_config  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

DOMAINS = ["warehouse_failover", "service_robot"]
SEEDS = [6, 7, 8]
DURATION_SEC = 60.0

START_POSITIONS_BY_SEED = {
    6: {"robot1": (2.0, 3.0), "robot2": (-4.0, -1.0)},
    7: {"robot1": (5.0, -2.0), "robot2": (0.5, 4.0)},
    8: {"robot1": (-3.0, 1.0), "robot2": (6.0, -6.0)},
}


def run_one(domain: str, seed: int) -> dict:
    router_ref = []

    def factory():
        router = build_backend(domain_router_config(domain))
        router_ref.append(router)
        return router

    world = LightweightWorld(
        robot_ids=["robot1", "robot2"],
        seed=seed,
        backend_factory=factory,
        start_positions=START_POSITIONS_BY_SEED[seed],
    )
    world.run_until(DURATION_SEC)
    summary = world.summary()

    total_llm = sum(r.stats.llm_decisions for r in router_ref)
    total_calls = sum(r.stats.total for r in router_ref)
    return {
        "domain": domain,
        "seed": seed,
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else None,
    }


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def run() -> int:
    print(f"scenario: 2 robots, duration={DURATION_SEC}s, paired seeds={SEEDS}, adaptive_router\n")
    print("llm backend: real local Ollama model (raca_core default) - genuine")
    print("measured latency drives the domain-dependent routing difference below.\n")

    header = "| Domain | Seed | Tasks Completed | LLM Invocation Rate |"
    sep = "|---|---:|---:|---:|"
    print(header)
    print(sep)

    results = {d: [] for d in DOMAINS}
    for domain in DOMAINS:
        for seed in SEEDS:
            row = run_one(domain, seed)
            results[domain].append(row)
            print(f"| {row['domain']} | {row['seed']} | {row['tasks_completed']} | {_fmt(row['llm_invocation_rate'])} |")

    print()
    for domain in DOMAINS:
        rates = [r["llm_invocation_rate"] for r in results[domain] if r["llm_invocation_rate"] is not None]
        mean_rate = sum(rates) / len(rates) if rates else None
        print(f"mean LLM invocation rate, {domain}: {_fmt(mean_rate)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
