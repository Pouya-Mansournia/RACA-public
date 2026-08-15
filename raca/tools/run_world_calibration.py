#!/usr/bin/env python3
"""Phase 2 calibration check: LightweightWorld vs. a real Gazebo/ROS run.

Tolerances are defined and committed in `raca/docs/phase2_calibration.md`
BEFORE this script's numbers are read as pass/fail - see that file for the
reference run and the reasoning behind each tolerance band.

Runs with plain `python3`, no ROS 2 / Gazebo needed:

    python raca/tools/run_world_calibration.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_worlds.lightweight_world import LightweightWorld  # noqa: E402

# Real reference numbers, transcribed from
# experiments/2026-08-12_milestone6_battery_degradation_001/summary.json
# (robot2, undegraded) - see phase2_calibration.md.
REAL_DURATION_SEC = 60.027
REAL_TASKS_COMPLETED_ROBOT2 = 3
REAL_MEAN_TASK_DURATION_SEC = 14.4
REAL_BATTERY_START = 0.9999305605888367
REAL_BATTERY_END = 0.9690334796905518
REAL_BATTERY_DROP = REAL_BATTERY_START - REAL_BATTERY_END

TOLERANCES = {
    "tasks_completed": (2, 5),  # inclusive band, see phase2_calibration.md
    "mean_task_duration_frac": 0.5,  # +/-50%
    "battery_drop_frac": 0.3,  # +/-30%
}


def _task_durations_sec(world: LightweightWorld, robot_id: str) -> list[float]:
    won = [e for e in world.events if e["type"] == "WON_CONTENTION" and e["robot_id"] == robot_id]
    done = [e for e in world.events if e["type"] == "TASK_COMPLETED" and e["robot_id"] == robot_id]
    return [d["sim_time"] - w["sim_time"] for w, d in zip(won, done)]


def run() -> int:
    world = LightweightWorld(robot_ids=["robot1", "robot2"], seed=6)
    world.run_until(REAL_DURATION_SEC)
    summary = world.summary()

    robot2 = summary["per_robot"]["robot2"]
    tasks_completed = robot2["tasks_completed"]
    durations = _task_durations_sec(world, "robot2")
    mean_duration = sum(durations) / len(durations) if durations else float("nan")
    battery_drop = 1.0 - robot2["final_battery_soc"]

    checks = []

    lo, hi = TOLERANCES["tasks_completed"]
    checks.append(("tasks_completed (robot2)", tasks_completed, f"[{lo}, {hi}]", lo <= tasks_completed <= hi))

    frac = TOLERANCES["mean_task_duration_frac"]
    lo_d, hi_d = REAL_MEAN_TASK_DURATION_SEC * (1 - frac), REAL_MEAN_TASK_DURATION_SEC * (1 + frac)
    checks.append(
        (
            "mean_task_duration_sec (robot2)",
            round(mean_duration, 2),
            f"[{lo_d:.2f}, {hi_d:.2f}] (real={REAL_MEAN_TASK_DURATION_SEC})",
            lo_d <= mean_duration <= hi_d,
        )
    )

    frac = TOLERANCES["battery_drop_frac"]
    lo_b, hi_b = REAL_BATTERY_DROP * (1 - frac), REAL_BATTERY_DROP * (1 + frac)
    checks.append(
        (
            "battery_drop_over_60s (robot2)",
            round(battery_drop, 5),
            f"[{lo_b:.5f}, {hi_b:.5f}] (real={REAL_BATTERY_DROP:.5f})",
            lo_b <= battery_drop <= hi_b,
        )
    )

    print(f"reference run: experiments/2026-08-12_milestone6_battery_degradation_001/")
    print(f"lightweight world: 2 robots, seed=6, duration={REAL_DURATION_SEC}s\n")

    all_pass = True
    for name, value, tolerance, passed in checks:
        status = "PASS" if passed else "FAIL"
        all_pass = all_pass and passed
        print(f"  [{status}] {name}: {value}  (tolerance: {tolerance})")

    print()
    print("RESULT:", "PASS - within all defined tolerances" if all_pass else "FAIL - see above")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(run())
