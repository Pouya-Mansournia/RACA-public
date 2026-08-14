"""Warehouse station table - ported from `fleet_coordination.stations` so
`raca_worlds` never needs to import anything under `src/`. Mirrors
`worlds/warehouse_fleet_world.sdf`'s real station layout exactly (see the
original module's docstring), which is what makes calibration against real
Gazebo/ROS runs (Phase 2's acceptance criterion) meaningful - the lightweight
world uses the SAME station geometry the historical runs used, not an
arbitrary one.
"""
from __future__ import annotations


def build_station_table(scale: float = 1.0):
    """Generate a station table using the same rule as the real (scale=1.0)
    layout above, scaled up spatially. `scale=5.0` means the aisle is 5x
    longer and has 5x as many stations per side, same 2m-equivalent
    spacing pattern - not a fabricated new layout, the same generator run
    with a bigger range. Used for scale-stress tests (many robots, a
    larger warehouse or a city-sized deployment); the scale=1.0 default
    below is the exact, unchanged, calibration-relevant layout.
    """
    x_offset = 6.9 * scale
    n = max(1, round(10 * scale))
    ys = [0.0] if n == 1 else [-9 * scale + i * (18 * scale) / (n - 1) for i in range(n)]
    stations = []
    for i, y in enumerate(ys, start=1):
        stations.append((f"input_station_{i}", "input", -x_offset, float(y)))
    for i, y in enumerate(ys, start=1):
        stations.append((f"output_station_{i}", "output", x_offset, float(y)))
    stations_by_side = {
        "input": [s for s in stations if s[1] == "input"],
        "output": [s for s in stations if s[1] == "output"],
    }
    return stations, stations_by_side


STATIONS, STATIONS_BY_SIDE = build_station_table(1.0)
OPPOSITE_SIDE = {"input": "output", "output": "input"}
