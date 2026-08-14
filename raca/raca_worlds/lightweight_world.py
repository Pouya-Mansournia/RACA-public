"""Lightweight, platform-independent research world (master prompt PHASE 2).

No ROS 2. No Gazebo. No RViz. No SLAM. No physics rendering. A discrete-event
simulation: robots, stations, event-based movement (`arrival_time = now +
distance / speed`), battery drain, and the same claim/contention decision
cycle the ROS-coupled `decentralized_agent.py` used, driven by an unmodified
`raca_core.backends.deterministic.DeterministicBackend` (or any other
`ReasoningBackend`).

Constants below (`ROBOT_SPEED_MPS`, `CONTENTION_WINDOW_SEC`,
`PICKUP_DROPOFF_PAUSE_SEC`, `BATTERY_DISCHARGE_RATE_PER_SEC`) are calibration
parameters, not arbitrary - see `raca/docs/phase2_calibration.md` for where
each one comes from in the historical Gazebo/ROS data and how the calibration
comparison against that data was performed. This is the one place values are
allowed to reference the frozen Phase-I evidence (read-only), per the master
prompt's Phase 2 "Calibration" step.
"""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from raca_core.claim_book import ClaimBook
from raca_core.config import build_backend
from raca_core.contracts import ALLOWED_ACTIONS, ReasoningBackend, RobotObservation, StationCandidate
from raca_core.stations import OPPOSITE_SIDE, STATIONS_BY_SIDE

# Calibrated from docs/research_extension_plan.md's Phase 3-9 live-validation
# notes: observed steady forward velocity was consistently ~1.2-1.3 m/s.
ROBOT_SPEED_MPS = 1.2
# Matches decentralized_agent.py's CONTENTION_WINDOW_SEC exactly.
CONTENTION_WINDOW_SEC = 1.0
# Matches decentralized_agent.py's PICKUP_DROPOFF_PAUSE_SEC exactly.
PICKUP_DROPOFF_PAUSE_SEC = 2.0
# Calibrated from a genuinely ACTIVE decentralized robot, not an idle one:
# experiments/2026-08-12_milestone6_battery_degradation_001/summary.json,
# robot2 (undegraded - no fault injected on it), decentralized+rule, 2
# robots, seed 6, 60.027 simulated seconds: battery_soc_start=0.9999305...,
# battery_soc_end=0.9690334... -> real depletion rate 0.0005148/s while
# continuously task-cycling. This is ~3.7x the health_monitor's own
# documented idle-baseline `discharge_rate` field
# (0.00013888889225199819/s, sampled from a mostly-stationary run) - a real,
# reportable finding (see raca/docs/phase2_calibration.md): the historical
# platform's battery model drains faster under active task-cycling than its
# own published idle constant would suggest, likely from a workload-linked
# effect not isolated in that constant. Calibrated to the ACTIVE rate since
# this world only ever simulates active, task-cycling robots.
BATTERY_DISCHARGE_RATE_PER_SEC = 0.0005148
# Real per-robot retry backoff after losing contention, matching
# decentralized_agent.py's _resolve_contention.
CONTENTION_RETRY_DELAY_SEC = 0.3


@dataclass
class RobotRuntime:
    robot_id: str
    x: float = 0.0
    y: float = 0.0
    battery_soc: float = 1.0
    state: str = "IDLE"
    current_side: str = "output"
    backend: ReasoningBackend = None  # type: ignore[assignment]
    rng: random.Random = None  # type: ignore[assignment]
    contending: Optional[Tuple[str, str, float, float, float]] = None
    claimed: Optional[Tuple[str, str, float, float]] = None


class LightweightWorld:
    """Discrete-event simulation of N robots contending for warehouse stations.

    Mirrors `decentralized_agent.py`'s state machine (IDLE -> contend ->
    NAVIGATING -> PAUSED -> IDLE, side alternates input/output) using the
    SAME `ClaimBook` conflict-resolution rule and the SAME station table, but
    with simulated time advanced by a plain event heap instead of ROS timers
    - no wall-clock/wall-time coupling, no Gazebo, no realtime-factor
    penalty.
    """

    def __init__(
        self,
        robot_ids: List[str],
        seed: int = 0,
        backend_factory: Callable[[], ReasoningBackend] = None,  # type: ignore[assignment]
        backend_config: Optional[dict] = None,
        start_positions: Optional[Dict[str, Tuple[float, float]]] = None,
        stations_by_side: Optional[Dict[str, list]] = None,
    ) -> None:
        """`backend_factory` (a callable returning a fresh `ReasoningBackend`
        per robot) takes precedence if given. Otherwise `backend_config` (a
        plain dict, e.g. `{"backend": "mock"}`) is passed to
        `raca_core.config.build_backend` - the config-only pluggability path
        master prompt Phase 3 requires: swapping which reasoning engine every
        robot in this world uses needs only a different `backend_config`,
        never a code change here or in any calling script.

        `start_positions` (default: every robot at the origin, unchanged
        behavior from Phase 2-6) lets a caller spawn robots at distinct
        coordinates. This exists because the default all-at-origin spawn is
        exactly symmetric with this warehouse's station geometry, making
        early decisions near-perfectly ambiguous by construction (see
        docs/research_journal.md's Phase 6 entry) - a real finding, not a
        bug, but one that makes an adaptive router's selectivity impossible
        to observe without varying starting positions.
        """
        if backend_factory is None:
            config = backend_config or {"backend": "deterministic"}
            backend_factory = lambda: build_backend(config)  # noqa: E731
        self.stations_by_side = stations_by_side or STATIONS_BY_SIDE
        self.sim_time: float = 0.0
        self._heap: List[Tuple[float, int, Callable[[], None]]] = []
        self._seq = 0
        self.events: List[dict] = []
        self.robots: Dict[str, RobotRuntime] = {}
        start_positions = start_positions or {}

        for index, robot_id in enumerate(robot_ids, start=1):
            rng = random.Random(seed * 1000 + index)
            x, y = start_positions.get(robot_id, (0.0, 0.0))
            self.robots[robot_id] = RobotRuntime(
                robot_id=robot_id,
                x=x,
                y=y,
                current_side=rng.choice(["input", "output"]),
                backend=backend_factory(),
                rng=rng,
            )

        self.claim_book = ClaimBook()
        for robot_id in self.robots:
            self.schedule(1.0, lambda robot_id=robot_id: self._attempt_claim(robot_id))
            self.schedule(1.0, lambda robot_id=robot_id: self._battery_tick(robot_id))

    # ------------------------------------------------------------ scheduling

    def schedule(self, delay_sec: float, fn: Callable[[], None]) -> None:
        heapq.heappush(self._heap, (self.sim_time + delay_sec, self._seq, fn))
        self._seq += 1

    def run_until(self, duration_sec: float) -> None:
        while self._heap and self._heap[0][0] <= duration_sec:
            due_time, _, fn = heapq.heappop(self._heap)
            self.sim_time = due_time
            fn()
        self.sim_time = duration_sec

    def _log(self, event_type: str, robot_id: str, **fields) -> None:
        self.events.append(
            {"type": event_type, "sim_time": self.sim_time, "robot_id": robot_id, **fields}
        )

    # ------------------------------------------------------------ battery

    def _battery_tick(self, robot_id: str) -> None:
        robot = self.robots[robot_id]
        robot.battery_soc = max(0.0, robot.battery_soc - BATTERY_DISCHARGE_RATE_PER_SEC)
        self._log("BATTERY_SAMPLE", robot_id, battery_soc=robot.battery_soc)
        self.schedule(1.0, lambda: self._battery_tick(robot_id))

    # ------------------------------------------------------------ task cycle

    def _attempt_claim(self, robot_id: str) -> None:
        robot = self.robots[robot_id]
        candidates = self.claim_book.free_stations(self.stations_by_side[robot.current_side])
        observation = RobotObservation(
            robot_id=robot_id,
            x=robot.x,
            y=robot.y,
            battery_soc=robot.battery_soc,
            degradation_risk=0.0,
            utilization=0.0,
            candidate_stations=tuple(
                StationCandidate(name=c[0], side=c[1], x=c[2], y=c[3]) for c in candidates
            ),
        )
        try:
            action = robot.backend.decide(observation, ALLOWED_ACTIONS)
        except Exception as exc:
            # Master prompt Phase 12: "no reasoning backend failure may
            # directly break the entire robotic system." AdaptiveRouter
            # already survives a SINGLE backend failing (Phase 8's
            # try/except + fallback); this is the remaining case - BOTH of
            # a robot's backends failing at once, or a router with no
            # internal safety net at all (Phase 11's static-router finding).
            # In the real ROS-coupled system each robot is its own OS
            # process, so one robot's crash can never take down its peers;
            # this single-process discrete-event world has no such natural
            # isolation, so it must provide the equivalent explicitly - one
            # robot's total decision failure logs an event and retries
            # later, it does not stop the simulation for every other robot.
            self._log("ROBOT_DECISION_FAILED", robot_id, error=f"{type(exc).__name__}: {exc}")
            self.schedule(1.0, lambda: self._attempt_claim(robot_id))
            return

        if action.action == "WAIT":
            self._log("WAIT", robot_id)
            self.schedule(1.0, lambda: self._attempt_claim(robot_id))
            return

        name = action.station_name
        side, x, y = next((c[1], c[2], c[3]) for c in candidates if c[0] == name)
        robot.contending = (name, side, x, y, action.cost)
        self.claim_book.observe(name, robot_id, action.cost, release=False)
        self._log("CONTENDING", robot_id, station=name, cost=action.cost)
        self.schedule(CONTENTION_WINDOW_SEC, lambda: self._resolve_contention(robot_id))

    def _resolve_contention(self, robot_id: str) -> None:
        robot = self.robots[robot_id]
        name, side, x, y, _cost = robot.contending
        winner = self.claim_book.winner_of(name)
        robot.contending = None
        if winner != robot_id:
            self._log("LOST_CONTENTION", robot_id, station=name, winner=winner)
            self.schedule(CONTENTION_RETRY_DELAY_SEC, lambda: self._attempt_claim(robot_id))
            return

        robot.claimed = (name, side, x, y)
        robot.state = "NAVIGATING"
        self._log("WON_CONTENTION", robot_id, station=name)
        self._send_nav_goal(robot_id, x, y)

    def _send_nav_goal(self, robot_id: str, x: float, y: float) -> None:
        robot = self.robots[robot_id]
        distance_m = ((robot.x - x) ** 2 + (robot.y - y) ** 2) ** 0.5
        travel_time_sec = distance_m / ROBOT_SPEED_MPS
        self._log("NAV_GOAL_SENT", robot_id, distance_m=distance_m, travel_time_sec=travel_time_sec)
        self.schedule(travel_time_sec, lambda: self._on_arrival(robot_id, x, y))

    def _on_arrival(self, robot_id: str, x: float, y: float) -> None:
        robot = self.robots[robot_id]
        robot.x, robot.y = x, y
        robot.state = "PAUSED"
        self._log("ARRIVED", robot_id, station=robot.claimed[0])
        self.schedule(PICKUP_DROPOFF_PAUSE_SEC, lambda: self._on_pause_complete(robot_id))

    def _on_pause_complete(self, robot_id: str) -> None:
        robot = self.robots[robot_id]
        name, side, _x, _y = robot.claimed
        self.claim_book.observe(name, robot_id, 0.0, release=True)
        self._log("TASK_COMPLETED", robot_id, station=name)
        robot.claimed = None
        robot.current_side = OPPOSITE_SIDE[side]
        robot.state = "IDLE"
        self._attempt_claim(robot_id)

    # ------------------------------------------------------------ summary

    def summary(self) -> dict:
        per_robot = {}
        for robot_id, robot in self.robots.items():
            completed = [e for e in self.events if e["type"] == "TASK_COMPLETED" and e["robot_id"] == robot_id]
            per_robot[robot_id] = {
                "tasks_completed": len(completed),
                "final_battery_soc": robot.battery_soc,
                "final_position": (robot.x, robot.y),
            }
        return {
            "sim_duration_sec": self.sim_time,
            "total_tasks_completed": sum(r["tasks_completed"] for r in per_robot.values()),
            "per_robot": per_robot,
        }
