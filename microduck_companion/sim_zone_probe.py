"""Read verified MuJoCo flat-floor ground truth and produce a local intention.

Only the exact pinned flat-floor simulator is accepted. No actuator, look,
move or stop RPC is issued. This is not a physical robot safety estimator.

Usage: python -m microduck_companion.sim_zone_probe --state-dir /tmp/duck-sim-companion
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .sim_bridge import read_simulator_telemetry
from .sim_flat_zone import (
    GroundTruthError, RL_COMMIT, flat_zone_snapshot,
    read_verified_flat_ground,
)


def observe_zone(state_dir: Path, rl_root: Path, *, port: int = 17801,
                 timeout_s: float = .5) -> dict:
    telemetry = read_simulator_telemetry(state_dir, timeout_s=3.)
    ground = None
    error = None
    try:
        ground = read_verified_flat_ground(
            state_dir, rl_root, port=port, timeout_s=timeout_s
        )
    except GroundTruthError as exc:
        error = str(exc)
    now = time.monotonic()
    snapshot = flat_zone_snapshot(telemetry, ground, now=now)
    memory = ExperienceMemory()
    try:
        plan = AutonomyBrain(memory).choose_from_snapshot(snapshot, now=now)
    finally:
        memory.close()
    floor = snapshot.to_scene(now=now).floor_clear
    area = snapshot.to_scene(now=now).safe_area
    return {
        "diagnostic": "pinned-simulator-flat-zone-read-only",
        "official_rl_revision": RL_COMMIT,
        "scene_verified": ground is not None,
        "zone_safe": area,
        "floor_clear": floor,
        "sim_time_s": ground.sim_time_s if ground else None,
        "trunk_xyz_m": [ground.x_m, ground.y_m, ground.z_m] if ground else None,
        "virtual_boundary_clearance_m": (
            ground.boundary_clearance_m if ground else None
        ),
        "telemetry_errors": list(telemetry.errors),
        "ground_error": error,
        "intention": plan.intention,
        "motor_commands_sent": [],
        "physical_robot_applicable": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pinned MuJoCo flat-zone read-only probe")
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".cache/duck-sim-companion")
    parser.add_argument("--rl-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "upstream/microduck_rl")
    parser.add_argument("--port", type=int, default=17801)
    args = parser.parse_args(argv)
    try:
        result = observe_zone(args.state_dir, args.rl_root, port=args.port)
    except ValueError as exc:
        print(f"invalid configuration: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if (
        result["scene_verified"] and result["zone_safe"]
        and result["floor_clear"] and not result["telemetry_errors"]
        and result["intention"] == "explore"
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
