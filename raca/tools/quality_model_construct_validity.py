#!/usr/bin/env python3
"""Construct-validity check for the ambiguity signal (final pre-submission
checklist item 6): does ambiguity predict ANY observable downstream
variable, using only what this codebase can actually measure?

No per-decision LLM-quality ground truth exists anywhere in this project
(disclosed repeatedly in Limitations/Threats to Validity), so this cannot
test "does ambiguity predict when the LLM gives a BETTER answer." What it
CAN test, honestly: does ambiguity predict BACKEND DISAGREEMENT, i.e. does
a naive alternative policy (MockBackend, which always bids for the first
candidate station regardless of cost) pick a DIFFERENT station than
DeterministicBackend's cost-ranked choice more often when ambiguity is
high? If ambiguity is a meaningless number, disagreement rate should be
flat across ambiguity levels. If it's measuring something real about
decision structure, disagreement should correlate with ambiguity in some
way (not necessarily monotonic - see interpretation below).

    python raca/tools/quality_model_construct_validity.py
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "raca"))

from raca_core.backends.deterministic import DeterministicBackend  # noqa: E402
from raca_core.backends.mock import MockBackend  # noqa: E402
from raca_core.contracts import RobotObservation, StationCandidate  # noqa: E402
from raca_core.difficulty import DifficultyEstimator  # noqa: E402
from raca_core.stations import build_station_table  # noqa: E402

N_SAMPLES = 3000
GEOM_SCALE = 1.0  # the original, real-calibration geometry
SCALE = 0.04

BUCKETS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]


def run() -> int:
    _, stations_by_side = build_station_table(GEOM_SCALE)
    estimator = DifficultyEstimator(ambiguity_margin_scale=SCALE)
    deterministic = DeterministicBackend()
    mock = MockBackend(fixed_cost=0.5)
    rng = random.Random(0)

    bucket_counts = {b: 0 for b in BUCKETS}
    bucket_disagreements = {b: 0 for b in BUCKETS}

    for _ in range(N_SAMPLES):
        side = rng.choice(["input", "output"])
        x = rng.uniform(-6.5, 6.5)
        y = rng.uniform(-8.5, 8.5)
        candidates = tuple(
            StationCandidate(name=c[0], side=c[1], x=c[2], y=c[3]) for c in stations_by_side[side]
        )
        observation = RobotObservation(
            robot_id="probe", x=x, y=y, battery_soc=1.0, degradation_risk=0.0,
            utilization=0.0, candidate_stations=candidates,
        )
        context = estimator.estimate(observation)
        ambiguity = context.ambiguity

        det_action = deterministic.decide(observation, frozenset({"BID_FOR_TASK", "WAIT"}))
        mock_action = mock.decide(observation, frozenset({"BID_FOR_TASK", "WAIT"}))
        disagree = det_action.station_name != mock_action.station_name

        for lo, hi in BUCKETS:
            if (lo <= ambiguity < hi) or (hi == 1.0 and ambiguity == 1.0):
                bucket_counts[(lo, hi)] += 1
                if disagree:
                    bucket_disagreements[(lo, hi)] += 1
                break

    print(f"Construct-validity check: does ambiguity predict backend disagreement? N={N_SAMPLES} sampled decisions\n")
    print("Backend disagreement = DeterministicBackend's cost-ranked choice differs from")
    print("MockBackend's naive 'always pick the first candidate' choice.\n")
    print("| Ambiguity bucket | N | Disagreement rate |")
    print("|---|---:|---:|")
    for lo, hi in BUCKETS:
        n = bucket_counts[(lo, hi)]
        rate = (bucket_disagreements[(lo, hi)] / n) if n else None
        rate_str = f"{rate:.3f}" if rate is not None else "n/a (0 samples)"
        print(f"| [{lo:.1f}, {hi:.1f}{']' if hi == 1.0 else ')'} | {n} | {rate_str} |")

    print()
    print("Interpretation: this tests whether ambiguity correlates with a MEASURABLE structural")
    print("property (would a naive alternative policy choose differently), not whether an LLM would")
    print("give a BETTER answer at high ambiguity - no per-decision quality ground truth exists in")
    print("this codebase to test that stronger claim, and this script does not claim otherwise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
