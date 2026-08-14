# Phase 2 Calibration: LightweightWorld vs. historical Gazebo/ROS run

Per the master prompt's Phase 2 requirement to "define tolerances before
comparison." This document is written and committed to before the
comparison numbers below were accepted as pass/fail, not adjusted after
the fact.

## Reference (real) run

`experiments/2026-08-12_milestone6_battery_degradation_001/` (read-only,
frozen Phase-I evidence): 2 robots, `--coordination decentralized
--agent-backend rule`, seed 6, `simulation_duration_sec: 60.027`. Chosen
because it is a decentralized, `RuleAgent`-backed run with real,
live-validated task-completion and battery data (see
`docs/current_limitations.md`, Milestone 6), i.e. the same decision logic
(`DeterministicBackend` is a faithful Phase 1 port of the same `RuleAgent`)
this lightweight world also uses.

`robot2` in that run had no fault injected (`robot1` was the deliberately
degraded one) and is therefore the correct calibration source for baseline
battery drain and task timing.

## What is NOT being claimed

Per the master prompt's own Phase 2 framing: "The lightweight world should
reproduce high-level patterns relevant to decision research. Not exact
physical trajectories." This is not a physics-accurate replica of Gazebo -
no SLAM noise, no Nav2 planner variance, no collision dynamics, no
per-timestep controller behavior. It reproduces the same high-level
event structure (claim -> contend -> navigate -> pickup/dropoff -> release,
side alternation) and the same decision logic, over the same station
geometry, at the same nominal travel speed.

## Tolerances, defined before running the comparison

| Metric | Real (robot2, undegraded) | Tolerance | Rationale |
|---|---:|---|---|
| Tasks completed in 60s (per robot) | 3 | within [2, 5] | N=1 real sample; wide band since task count is highly sensitive to exact travel distances, which differ between Gazebo's real path-planned routes and this world's straight-line distance model |
| Mean task duration (sec) | 14.4 | within ±50% (7.2 - 21.6s) | straight-line distance is a lower bound on Nav2's real planned-path distance; ±50% accounts for that without asserting exact match |
| Battery drop over 60s (undegraded robot) | 0.0309 (0.9999 -> 0.9690) | within ±30% | this world's battery model is deliberately calibrated to this exact number (see `BATTERY_DISCHARGE_RATE_PER_SEC`'s docstring) - the tolerance here is a sanity check that the constant was transcribed and applied correctly, not an independent validation |
| Task ordering / station assignment sequence | not compared exactly | N/A - explicitly out of scope | different RNG streams (seed semantics differ between the ROS agent's `random.Random(seed*1000+robot_index)` used for `current_side` only, vs. Gazebo's own SLAM/Nav2 nondeterminism) make an exact sequence match meaningless; only aggregate outcome (task count, timing, battery) is compared, per Phase 2's own "approximate consistency" framing |
| Failover behavior | not compared | deferred | Phase 2 scope is the base task-cycling loop only; `LightweightWorld` does not yet model a central-manager kill / failover transition (Milestone 2/9 territory) - this is a documented, explicit gap, not a silent omission |

## Result

See `raca/tools/run_world_calibration.py` output, reproduced in the Phase 2
report. Any metric outside its stated tolerance is reported as a FAIL for
that metric, not silently excluded or re-tolerated after the fact.
