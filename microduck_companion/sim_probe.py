"""Read-only diagnostic against a running official duck-sim instance.

This probes IPC, not autonomy or physical safety. No robot.move, enable, or stop.
Usage: python -m microduck_companion.sim_probe --state-dir ~/.cache/duck-sim
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .sim_ipc import (
    ReadOnlyUnixRpc, TelemetryError, parse_health, parse_depth, parse_state,
)
import time


def collect(state_dir: Path, *, samples: int = 2, timeout_s: float = 3.) -> dict:
    """Gather limited readings from the simulator's daemon sockets."""
    if type(samples) is not int or not 1 <= samples <= 10:
        raise ValueError("samples must be in [1,10]")
    robot_socket = state_dir / "duck-a.sock"
    tof_socket = state_dir / "duck-a-tof.sock"
    with ReadOnlyUnixRpc(robot_socket, timeout_s=timeout_s) as reader:
        health = parse_health(reader.request("robot.health"), time.monotonic())
        ack = reader.request("robot.subscribe", hz=2)
        states = [parse_state(reader.next_notification()) for _ in range(samples)]
    with ReadOnlyUnixRpc(tof_socket, timeout_s=timeout_s) as reader:
        depth_ack = reader.request("tof.stream")
        depths = [parse_depth(reader.next_notification()) for _ in range(samples)]
    return {
        "diagnostic": "read-only-sim-telemetry",
        "robot_healthy": health.healthy,
        "battery_pct": health.battery_pct,
        "target_hz": health.target_hz,
        "health_achieved_hz": health.achieved_hz,
        "state_loop_hz": [s.achieved_hz for s in states],
        "state_missed_ticks": [s.missed_ticks for s in states],
        "fallen": [s.fallen for s in states],
        "limp": [s.limp for s in states],
        "tof_sensor": depth_ack.get("sensor"),
        "tof_unavailable": depth_ack.get("unavailable"),
        "tof_sequences": [d.seq for d in depths],
        "tof_frame_cells": [len(d.distance_mm) for d in depths],
        "floor_certified": False,
        "commands_sent": [],
        "caution": "No movement authorized; ToF does not certify floor clearance.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Microduck simulator IPC probe")
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".cache" / "duck-sim")
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=3.)
    args = parser.parse_args(argv)
    try:
        result = collect(args.state_dir, samples=args.samples, timeout_s=args.timeout)
    except (TelemetryError, ValueError, OSError) as exc:
        print(f"telemetry probe failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # Do not report success if robotd itself considers the simulated duck unhealthy.
    return 0 if result["robot_healthy"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
