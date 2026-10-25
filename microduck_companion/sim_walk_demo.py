"""Explicitly authorize ONE measured simulator walk trial and report memory.

This cannot run on the physical robot: only the pinned empty headless MuJoCo
body can pass the simulator provenance checks. No background operation.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from .sim_motion import SimMotionError
from .sim_walk_trial import run_walk_trial


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One measured MuJoCo translation trial with local SQLite memory",
    )
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".cache/duck-sim-companion")
    parser.add_argument("--rl-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "upstream/microduck_rl")
    parser.add_argument("--memory", type=Path,
                        default=Path.home() / ".local/share/microduck-companion/sim-motion.sqlite")
    parser.add_argument("--port", type=int, default=17801)
    parser.add_argument("--enable-once", action="store_true")
    args = parser.parse_args(argv)

    if not args.enable_once or os.environ.get("MICRODUCK_SIM_WALK_TEST") != "YES":
        print("Simulator walk trial disabled: pass --enable-once and "
              "MICRODUCK_SIM_WALK_TEST=YES.", file=sys.stderr)
        return 2
    try:
        result = run_walk_trial(
            args.state_dir, args.rl_root, args.memory, port=args.port,
        )
    except (SimMotionError, ValueError, OSError) as exc:
        print(f"MuJoCo walk trial refused or incomplete: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "simulation_only": True,
        "learning_is_memory_update_not_model_training": True,
        "walking_gait_verified": False,
        **asdict(result),
    }, indent=2, ensure_ascii=False))
    # A confirmed stop alone is not a successful walking/translation test.
    return 0 if result.outcome == "translation_observed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
