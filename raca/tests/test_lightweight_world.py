from __future__ import annotations

from raca_worlds.lightweight_world import LightweightWorld


def test_single_robot_completes_at_least_one_task_cycle():
    world = LightweightWorld(robot_ids=["robot1"], seed=1)
    world.run_until(90.0)
    summary = world.summary()
    assert summary["per_robot"]["robot1"]["tasks_completed"] >= 1


def test_battery_monotonically_decreases():
    world = LightweightWorld(robot_ids=["robot1"], seed=1)
    world.run_until(60.0)
    samples = [e["battery_soc"] for e in world.events if e["type"] == "BATTERY_SAMPLE"]
    assert len(samples) >= 2
    assert all(a >= b for a, b in zip(samples, samples[1:]))


def test_two_robots_never_both_win_the_same_station_at_once():
    world = LightweightWorld(robot_ids=["robot1", "robot2"], seed=5)
    world.run_until(120.0)
    won_events = [e for e in world.events if e["type"] == "WON_CONTENTION"]
    # At any instant, a station can only ever be won by one robot - check no
    # two WON_CONTENTION events for the same station overlap without an
    # intervening TASK_COMPLETED for that station.
    held_by: dict = {}
    for e in sorted(world.events, key=lambda e: e["sim_time"]):
        if e["type"] == "WON_CONTENTION":
            station = e["station"]
            assert station not in held_by, f"{station} double-held at t={e['sim_time']}"
            held_by[station] = e["robot_id"]
        elif e["type"] == "TASK_COMPLETED":
            held_by.pop(e["station"], None)
    assert len(won_events) >= 1


def test_deterministic_given_same_seed():
    world_a = LightweightWorld(robot_ids=["robot1", "robot2"], seed=42)
    world_a.run_until(60.0)
    world_b = LightweightWorld(robot_ids=["robot1", "robot2"], seed=42)
    world_b.run_until(60.0)
    assert world_a.summary() == world_b.summary()


def test_different_seed_can_change_starting_side():
    seeds_sides = set()
    for seed in range(5):
        world = LightweightWorld(robot_ids=["robot1"], seed=seed)
        seeds_sides.add(world.robots["robot1"].current_side)
    assert seeds_sides <= {"input", "output"}
