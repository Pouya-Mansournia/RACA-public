"""Pure, ROS-free conflict-resolution logic for decentralized station claiming.

Faithful port of `fleet_coordination.claim_book.ClaimBook` (Phase 5 of the
prior research line) - identical deterministic rule (lowest cost wins,
robot_id string tiebreak), ported here so `raca_worlds` never has to import
anything under `src/`. See that module's original docstring
(`src/fleet_coordination/fleet_coordination/claim_book.py`) for the full
design rationale; unchanged here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class _Holder:
    robot_id: str
    cost: float


class ClaimBook:
    def __init__(self) -> None:
        self._holders: Dict[str, _Holder] = {}

    def observe(self, station_name: str, robot_id: str, cost: float, release: bool) -> None:
        if release:
            current = self._holders.get(station_name)
            if current is not None and current.robot_id == robot_id:
                del self._holders[station_name]
            return

        candidate = _Holder(robot_id=robot_id, cost=cost)
        current = self._holders.get(station_name)
        if current is None or _beats(candidate, current):
            self._holders[station_name] = candidate

    def winner_of(self, station_name: str) -> Optional[str]:
        holder = self._holders.get(station_name)
        return holder.robot_id if holder is not None else None

    def is_free(self, station_name: str) -> bool:
        return station_name not in self._holders

    def free_stations(self, candidates) -> list:
        """`candidates`: iterable of (name, side, x, y) tuples. Returns the
        subset currently believed free."""
        return [c for c in candidates if self.is_free(c[0])]


def _beats(candidate: _Holder, current: _Holder) -> bool:
    if candidate.cost != current.cost:
        return candidate.cost < current.cost
    return candidate.robot_id < current.robot_id
