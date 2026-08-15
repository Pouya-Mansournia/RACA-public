#!/usr/bin/env python3
"""Phase 4 - Baseline Cost Characterization (master prompt PHASE 4).

Measures each reasoning backend independently on the SAME experimental
scenario - no adaptive routing yet, that is Phase 7. Runs with plain
`python3`:

    python raca/tools/generate_backend_report.py

Every number in the printed table is measured live from this run, never
estimated - a column stays blank rather than being filled with a guess (the
same research-integrity rule the prior research line's
`analysis/scripts/generate_report.py` follows).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.backends.instrumentation import TimingWrapperBackend  # noqa: E402
from raca_core.config import build_backend  # noqa: E402
from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

SCENARIOS = [
    {"backend": "deterministic"},
    {"backend": "mock"},
    {"backend": "local_llm"},
]

DURATION_SEC = 60.0
SEED = 6
ROBOT_IDS = ["robot1", "robot2"]


def _fmt(value, digits=4):
    return "n/a" if value is None else f"{value:.{digits}f}"


def run() -> int:
    rows = []
    for config in SCENARIOS:
        wrappers = []

        def factory(config=config):
            wrapper = TimingWrapperBackend(inner=build_backend(config))
            wrappers.append(wrapper)
            return wrapper

        world = LightweightWorld(robot_ids=list(ROBOT_IDS), seed=SEED, backend_factory=factory)
        world.run_until(DURATION_SEC)
        summary = world.summary()

        # Merge per-robot instrumentation records (one TimingWrapperBackend
        # instance per robot - each robot gets its own backend instance).
        all_records = [record for wrapper in wrappers for record in wrapper.records]
        merged_latencies = sorted(r.latency_sec for r in all_records)
        n = len(merged_latencies)
        mean_latency = sum(merged_latencies) / n if n else None
        p95_index = min(n - 1, int(round(0.95 * (n - 1)))) if n else None
        p95_latency = merged_latencies[p95_index] if n else None
        validity_rate = (sum(1 for r in all_records if r.valid) / n) if n else None
        fallback_rate = (sum(1 for r in all_records if r.fallback_used) / n) if n else None

        rows.append(
            {
                "backend": config["backend"],
                "decisions": n,
                "mean_latency_ms": mean_latency * 1000 if mean_latency is not None else None,
                "p95_latency_ms": p95_latency * 1000 if p95_latency is not None else None,
                "validity_rate": validity_rate,
                "fallback_rate": fallback_rate,
                "tasks_completed": summary["total_tasks_completed"],
            }
        )

    print(f"scenario: {len(ROBOT_IDS)} robots, seed={SEED}, duration={DURATION_SEC}s, no adaptive routing\n")
    header = "| Backend | Decisions | Mean Latency (ms) | P95 Latency (ms) | Validity Rate | Fallback Rate | Tasks Completed |"
    sep = "|---|---:|---:|---:|---:|---:|---:|"
    print(header)
    print(sep)
    for row in rows:
        print(
            f"| {row['backend']} | {row['decisions']} | {_fmt(row['mean_latency_ms'])} | "
            f"{_fmt(row['p95_latency_ms'])} | {_fmt(row['validity_rate'])} | "
            f"{_fmt(row['fallback_rate'])} | {row['tasks_completed']} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
