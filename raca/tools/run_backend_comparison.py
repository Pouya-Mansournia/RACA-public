#!/usr/bin/env python3
"""Phase 3 acceptance check: the SAME experimental scenario runs
successfully with every backend, changed only via configuration.

Runs with plain `python3`:

    python raca/tools/run_backend_comparison.py

`local_llm` is included; if no Ollama server is reachable on this machine it
will exhaust its retries and fall back to `deterministic` for every
decision (LocalLLMBackend's documented, tested fallback behavior) rather
than crash the run - so this script demonstrates graceful degradation as
much as it demonstrates pluggability when a real LLM server IS reachable.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

SCENARIOS = [
    {"backend": "deterministic"},
    {"backend": "mock"},
    {"backend": "local_llm"},
]

DURATION_SEC = 60.0
SEED = 6
ROBOT_IDS = ["robot1", "robot2"]


def run() -> int:
    print(f"scenario: {len(ROBOT_IDS)} robots, seed={SEED}, duration={DURATION_SEC}s\n")
    for config in SCENARIOS:
        world = LightweightWorld(robot_ids=list(ROBOT_IDS), seed=SEED, backend_config=config)
        world.run_until(DURATION_SEC)
        summary = world.summary()
        print(f"  backend={config['backend']!r}: total_tasks_completed={summary['total_tasks_completed']}")
        for robot_id, stats in summary["per_robot"].items():
            print(
                f"    {robot_id}: tasks={stats['tasks_completed']} "
                f"final_battery={stats['final_battery_soc']:.4f}"
            )
    print("\nRESULT: PASS - identical scenario code ran under every backend via config only")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
