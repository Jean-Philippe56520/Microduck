"""F4-B demonstration: two processes, one local SQLite, mock-only disks.

Shows persisted *historical* toy-marker coordinates in two mock sessions,
and an absent location in a second fake zone. Never captures a sensor,
builds a room map, opens a network socket or drives the robot.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from .episodic_memory import ExperienceMemory
from .uncertain_spatial_memory import MockSpatialObservation, UncertainSpatialMemory


def run_demo(path: Path, *, session: str) -> dict:
    if session not in ("first", "second"):
        raise ValueError("only two named fictitious demo processes")
    memory = ExperienceMemory(path)
    try:
        spatial = UncertainSpatialMemory(memory)
        now_wall = time.time()
        now_mono = time.monotonic()
        # Different, overlapping positions across processes: no averaging
        # into an invented precise position. Radius must stay conservative.
        x = 0.0 if session == "first" else 0.15
        radius = 0.4 if session == "first" else 0.45
        observation = MockSpatialObservation(
            "mock_zone_a", "toy", x, 0.0, radius, 0.90, now_mono,
            now_wall, 1,
        )
        assert spatial.append(
            observation, now_monotonic_s=now_mono+0.05,
            now_wall_epoch_s=now_wall+0.05,
        )
        recorded = spatial.recall(
            frame="mock_zone_a", landmark="toy", now_wall_epoch_s=now_wall+0.1,
        )
        absent = spatial.recall(
            frame="mock_zone_b", landmark="toy", now_wall_epoch_s=now_wall+0.1,
        )
        expected_count = 1 if session == "first" else 2
        if (recorded.observations != expected_count or
                recorded.status != "bounded_historical_mock_only" or
                not recorded.historical_only or
                recorded.navigation_authorized or
                recorded.real_sensor_authenticated or
                recorded.real_reference_frame_verified or
                recorded.floor_clearance_verified or
                recorded.motor_commands_issued or
                absent.status != "no_historical_fixture"):
            raise RuntimeError("fixture memory cannot authorize navigation")
        return {
            "scope": "two_processes_mock_spatial_memory_only",
            "session": session,
            "spatial_recall": asdict(recorded),
            "independent_frame": asdict(absent),
            "sqlite_reopened_across_processes": session == "second",
            "real_map_constructed": False,
            "actual_obstacles_measured": 0,
            "physical_sensor_authenticated": False,
            "motor_commands_issued": 0,
            "physical_robot_validated": False,
        }
    finally:
        memory.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database", required=True, type=Path)
    p.add_argument("--session", required=True, choices=("first", "second"))
    args = p.parse_args(argv)
    print(json.dumps(run_demo(args.database, session=args.session),
                     sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
