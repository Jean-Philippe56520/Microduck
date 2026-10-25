"""Observe official simulated daemon telemetry and make a SAFE local decision.

No intent RPC is implemented. The brain will halt except that it can select
rest for a verified low battery. No fake clearance is injected for the floor.

Usage: python -m microduck_companion.sim_observer --state-dir ~/.cache/duck-sim
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


def observe_once(state_dir: str | Path, *, timeout_s: float = 3.0) -> dict:
    telemetry = read_simulator_telemetry(state_dir, timeout_s=timeout_s)
    now = time.monotonic()
    snapshot = telemetry.to_snapshot(now)
    with_memory = ExperienceMemory()
    try:
        brain = AutonomyBrain(with_memory)
        plan = brain.choose_from_snapshot(snapshot, now=now)
    finally:
        with_memory.close()
    return {
        "environment": snapshot.environment,
        "intention": plan.intention,
        "explanation": plan.explanation,
        "health_received": telemetry.health is not None,
        "robot_healthy": telemetry.health.healthy if telemetry.health else None,
        "state_received": telemetry.state is not None,
        "depth_received": telemetry.depth is not None,
        "errors": list(telemetry.errors),
        "perception_events": [
            {"kind": e.kind, "source": e.source, "value": e.value}
            for e in snapshot.events
        ],
        "floor_certified": False,
        "movement_rpc_enabled": False,
        "note": "Read-only diagnostic, not MuJoCo autonomy validation.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Microduck sim observer")
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".cache" / "duck-sim")
    parser.add_argument("--timeout", type=float, default=3.0)
    options = parser.parse_args(argv)
    try:
        result = observe_once(options.state_dir, timeout_s=options.timeout)
    except ValueError as exc:
        print(f"invalid configuration: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # Nonzero if any daemon is missing or the robot has incomplete telemetry.
    return 0 if not result["errors"] and result["robot_healthy"] and all(
        result[field] for field in
        ("health_received", "state_received", "depth_received")
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
