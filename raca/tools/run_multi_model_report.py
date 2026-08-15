#!/usr/bin/env python3
"""Phase 9 - Multi-Model Experiment (master prompt PHASE 9).

NOT framed as "which model is best" - framed as "how robust is RACA to
different reasoning-engine characteristics?" Runs the IDENTICAL Phase 7
scenario (AdaptiveRouter, non-symmetric start positions, same paired seeds)
with two different local models, swapped via configuration only
(`{"model": "..."}` inside the `local_llm` sub-config) - zero code change,
zero vendor-specific logic anywhere in `raca_core` (grep-verifiable: no
model name string appears outside this script and `raca_core/config.py`'s
own default).

    python raca/tools/run_multi_model_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.config import build_backend  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

MODELS = ["qwen2.5:7b", "llama3.2:3b"]
SEEDS = [6, 7, 8]
DURATION_SEC = 60.0

START_POSITIONS_BY_SEED = {
    6: {"robot1": (2.0, 3.0), "robot2": (-4.0, -1.0)},
    7: {"robot1": (5.0, -2.0), "robot2": (0.5, 4.0)},
    8: {"robot1": (-3.0, 1.0), "robot2": (6.0, -6.0)},
}


def run_one(model: str, seed: int) -> dict:
    router_ref = []

    def factory():
        router = build_backend(
            {
                "backend": "adaptive_router",
                "llm_config": {"backend": "local_llm", "model": model},
            }
        )
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
    total_failures = sum(r.failure_rate("llm") * r._attempts["llm"] for r in router_ref)
    total_llm_attempts = sum(r._attempts["llm"] for r in router_ref)

    return {
        "model": model,
        "seed": seed,
        "tasks_completed": summary["total_tasks_completed"],
        "llm_invocation_rate": (total_llm / total_calls) if total_calls else None,
        "llm_failures": total_failures,
        "llm_attempts": total_llm_attempts,
    }


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def run() -> int:
    print(f"scenario: 2 robots, duration={DURATION_SEC}s, paired seeds={SEEDS}, adaptive_router\n")
    header = "| Model | Seed | Tasks Completed | LLM Invocation Rate | LLM Failures/Attempts |"
    sep = "|---|---:|---:|---:|---:|"
    print(header)
    print(sep)
    for model in MODELS:
        for seed in SEEDS:
            row = run_one(model, seed)
            print(
                f"| {row['model']} | {row['seed']} | {row['tasks_completed']} | "
                f"{_fmt(row['llm_invocation_rate'])} | {row['llm_failures']:.0f}/{row['llm_attempts']} |"
            )
    print("\nRESULT: identical raca_core code, identical scenario, ran successfully under both models via config only")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
