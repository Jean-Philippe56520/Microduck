"""Explicitly opt in to ONE short MuJoCo-only robotd movement.

This tool is never invoked by the autonomous decision loop, and does not
work with a physical robot or another MuJoCo scene. It only sends a fixed
0.05 m/s forward intent for four ticks with stop acknowledgment.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from .sim_motion import SimMotionError, move_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One bounded MuJoCo motion via robotd")
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".cache/duck-sim-companion")
    parser.add_argument("--rl-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "upstream/microduck_rl")
    parser.add_argument("--port", type=int, default=17801)
    parser.add_argument("--enable-once", action="store_true")
    opts = parser.parse_args(argv)
    if not opts.enable_once or os.environ.get("MICRODUCK_SIM_MOTION_TEST") != "YES":
        print("Simulation-only motion is disabled; --enable-once and "
              "MICRODUCK_SIM_MOTION_TEST=YES are required.", file=sys.stderr)
        return 2
    try:
        result = move_once(opts.state_dir, opts.rl_root, port=opts.port)
    except (SimMotionError, ValueError) as exc:
        print(f"simulated impulse refused or incomplete: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "simulation_only": True,
        "robotd_methods": ["robot.move", "robot.stop"],
        "no_physical_robot": True,
        **asdict(result),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
