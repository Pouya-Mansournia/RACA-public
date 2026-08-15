#!/usr/bin/env python3
"""Phase 1 output-equivalence validation (master prompt, PHASE 1's "Required
Validation" section).

Runs from plain `python3`, without ROS 2 / Gazebo / Nav2 / WSL2 / Ubuntu:

    python raca/tools/run_decision_test.py

Replays real historical robot telemetry (read-only; from
`experiments/*/robot_*.csv` and `experiments/*/health_*.csv`, produced by the
frozen Phase-I research line - see docs/research_lineage.md) through:

    old = src/agent_core/agent_core/rule_agent.RuleAgent   (ROS-coupled repo,
          but this specific module has zero rclpy import itself)
    new = raca/raca_core/backends/deterministic.DeterministicBackend

and asserts the two produce byte-identical decisions (action, station_name,
cost) for every sampled observation, against the fixed station table in
`src/fleet_coordination/fleet_coordination/stations.py` (also ROS-free).

This does not modify or write to anything under `experiments/`.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_AGENT_CORE_PATH = REPO_ROOT / "src" / "agent_core"
OLD_FLEET_COORDINATION_PATH = REPO_ROOT / "src" / "fleet_coordination"
NEW_RACA_PATH = REPO_ROOT / "raca"

for path in (OLD_AGENT_CORE_PATH, OLD_FLEET_COORDINATION_PATH, NEW_RACA_PATH):
    sys.path.insert(0, str(path))

from agent_core.interfaces import Observation as OldObservation  # noqa: E402
from agent_core.interfaces import StationCandidate as OldStationCandidate  # noqa: E402
from agent_core.rule_agent import RuleAgent as OldRuleAgent  # noqa: E402
from fleet_coordination.stations import STATIONS_BY_SIDE  # noqa: E402

from raca_core.backends.deterministic import DeterministicBackend  # noqa: E402
from raca_core.contracts import ALLOWED_ACTIONS as NEW_ALLOWED_ACTIONS  # noqa: E402
from raca_core.contracts import RobotObservation as NewObservation  # noqa: E402
from raca_core.contracts import StationCandidate as NewStationCandidate  # noqa: E402

OLD_ALLOWED_ACTIONS = frozenset({"BID_FOR_TASK", "WAIT"})

# A handful of real Phase-I runs known-good from docs/research_extension_plan.md
# / docs/current_limitations.md (real motion + real health samples, not the
# earlier flaky/empty-CSV runs those documents flag).
CANDIDATE_RUNS = [
    "experiments/2026-08-11_phase2_validation_003",
    "experiments/2026-08-11_centralized_baseline_001",
]


def _find_usable_run() -> Path:
    for rel in CANDIDATE_RUNS:
        run_dir = REPO_ROOT / rel
        robot_csv = run_dir / "robot_robot1.csv"
        health_csv = run_dir / "health_robot1.csv"
        if robot_csv.exists() and health_csv.exists():
            return run_dir
    raise SystemExit("no usable historical run found under experiments/ (read-only lookup)")


def _load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sample_indices(n: int, count: int) -> list[int]:
    if n <= count:
        return list(range(n))
    step = n // count
    return [i * step for i in range(count)]


def build_sample_observations(run_dir: Path, sample_count: int = 25):
    robot_rows = _load_rows(run_dir / "robot_robot1.csv")
    health_rows = _load_rows(run_dir / "health_robot1.csv")
    if not robot_rows or not health_rows:
        raise SystemExit(f"{run_dir} has no usable rows (should have been filtered out)")

    candidates = STATIONS_BY_SIDE["output"]
    samples = []
    for idx in _sample_indices(len(robot_rows), sample_count):
        robot_row = robot_rows[idx]
        # Nearest health sample by position in the file - both are ~1Hz/steady
        # samplers from the same run, close enough for a decision-equivalence
        # check (this harness is not trying to reconstruct exact simulation
        # timing, only realistic (x, y, battery_soc) triples).
        health_idx = min(idx, len(health_rows) - 1)
        health_row = health_rows[health_idx]
        samples.append(
            {
                "x": float(robot_row["x"]),
                "y": float(robot_row["y"]),
                "battery_soc": float(health_row["battery_soc"]),
                "candidates": candidates,
            }
        )
    return samples


def run() -> int:
    run_dir = _find_usable_run()
    samples = build_sample_observations(run_dir)

    old_backend = OldRuleAgent()
    new_backend = DeterministicBackend()

    mismatches = []
    for i, sample in enumerate(samples):
        old_obs = OldObservation(
            robot_id="robot1",
            x=sample["x"],
            y=sample["y"],
            battery_soc=sample["battery_soc"],
            degradation_risk=0.0,
            utilization=0.0,
            candidate_stations=tuple(
                OldStationCandidate(name=c[0], side=c[1], x=c[2], y=c[3])
                for c in sample["candidates"]
            ),
        )
        new_obs = NewObservation(
            robot_id="robot1",
            x=sample["x"],
            y=sample["y"],
            battery_soc=sample["battery_soc"],
            degradation_risk=0.0,
            utilization=0.0,
            candidate_stations=tuple(
                NewStationCandidate(name=c[0], side=c[1], x=c[2], y=c[3])
                for c in sample["candidates"]
            ),
        )

        old_action = old_backend.decide(old_obs, OLD_ALLOWED_ACTIONS)
        new_action = new_backend.decide(new_obs, NEW_ALLOWED_ACTIONS)

        if (
            old_action.action != new_action.action
            or old_action.station_name != new_action.station_name
            or old_action.cost != new_action.cost
        ):
            mismatches.append((i, sample, old_action, new_action))

    print(f"source run: {run_dir.relative_to(REPO_ROOT)}")
    print(f"samples compared: {len(samples)}")
    print(f"mismatches: {len(mismatches)}")
    for i, sample, old_action, new_action in mismatches:
        print(f"  [{i}] x={sample['x']:.3f} y={sample['y']:.3f} soc={sample['battery_soc']:.3f}")
        print(f"      old: action={old_action.action} station={old_action.station_name} cost={old_action.cost}")
        print(f"      new: action={new_action.action} station={new_action.station_name} cost={new_action.cost}")

    if mismatches:
        print("RESULT: FAIL - output equivalence broken")
        return 1
    print("RESULT: PASS - 100% output equivalence for identical inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
