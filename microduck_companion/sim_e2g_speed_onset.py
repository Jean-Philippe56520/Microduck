"""SIM-E2G: ONE pinned-OEM, simulated-only 0.30 m/s onset diagnostic.

A new motor policy, arbitrary velocity, robot hardware, real SQLite, and
causal learning are NOT provided. Reuse the J2e 24-tick/stop-protected run and
P0i's exact ONNX/gitlink/live-daemon authentication. This is a bounded
experimental fixture interface that runs only behind two explicit opt-ins in
a dedicated GitHub Actions branch. Low-speed historical P0i uses DIFFERENT
runs and is not a randomized paired control.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
import sys

from .sim_motion import SimMotionError
from .sim_flat_zone import GroundTruthError, verify_body_process
from .sim_policy_contract import verify_oem_sources
from .sim_policy_lineage import read_sources
from .sim_policy_pair import (
    PINNED_V8_SHA256, verify_active_arm,
)
from .sim_walk_trial import (
    WALK_TICKS, ONSET_PROBE_SPEED_MPS, run_walk_trial,
)

TRIAL_THRESHOLD_M = 0.010
SIM_PORT = 17801
RUN_OPT_IN = "MICRODUCK_SIM_E2G"


def run_probe(state_dir: Path, robot_root: Path, rl_root: Path,
              memory_path: Path, *, port: int = SIM_PORT) -> dict:
    """Run at most one commanded 0.30 trial after verified OEM preflight.

    Validated data is a simulator pose displacement, never a gait, model
    quality, reward, autonomous behavior, or proof of physical robot motion.
    """
    if type(port) is not int or port != SIM_PORT:
        raise SimMotionError("SIM-E2G requires only official isolated simulator port")
    state, robot, rl = (
        state_dir.resolve(strict=True),
        robot_root.resolve(strict=True),
        rl_root.resolve(strict=True),
    )
    verify_oem_sources(robot, rl)
    read_sources(robot, rl)  # immutable official policy-slot lineage
    verify_body_process(state, rl, port)
    active = verify_active_arm(state, robot, "alpha")
    if (active.get("walk_model") != "alpha_walking.onnx"
            or active.get("stand_model") != "alpha_stand.onnx"
            or active.get("selected_from_live_robotd_policy_list") is not True
            or active.get("bundle_sha256") != PINNED_V8_SHA256):
        raise SimMotionError("active simulator model identity unverified")

    # Local fixture journal only, in the ephemeral CI simulator directory.
    # This does not modify Kwipi's persistent ExperienceMemory or reward model.
    if not memory_path.parent.resolve(strict=True) == state:
        raise SimMotionError("diagnostic SQLite must remain in isolated sim state")
    if memory_path.name != "sim-e2g-disposable.sqlite3":
        raise SimMotionError("diagnostic SQLite must have approved throwaway name")
    if memory_path.is_symlink() or memory_path.exists():
        raise SimMotionError("refuse stale or linked simulator memory state")

    trial = run_walk_trial(
        state, rl, memory_path, port=port,
        speed_mps=ONSET_PROBE_SPEED_MPS,
    )
    if (trial.stop_confirmed is not True
            or trial.commands_sent != WALK_TICKS
            or trial.requested_speed_mps != ONSET_PROBE_SPEED_MPS):
        raise SimMotionError("incomplete trial/stop or changed speed")
    policy = trial.policy_diagnostics
    if (not isinstance(policy, dict)
            or policy.get("policy_samples") != WALK_TICKS):
        raise SimMotionError("incomplete published OEM policy telemetry")

    limits = policy.get("limited_by")
    eligible_control = (
        policy.get("walk_policy_samples", 0) >= WALK_TICKS - 4
        and policy.get("max_applied_vx_mps", 0) >= 0.25
        and isinstance(limits, list) and not limits
    )
    displacement = trial.measured_displacement_m
    candidate = eligible_control and displacement >= TRIAL_THRESHOLD_M
    return {
        "experiment": "SIM-E2G_one_fixed_speed_onset_pinned_OEM_sim_only",
        "question": "Does a 0.30 m/s from-rest request cause >=10mm measured trunk translation in this pinned empty simulation?",
        "network_slots_verified_from_live_robotd": True,
        "pinned_v8_sha256": dict(PINNED_V8_SHA256),
        "active_gait": {
            "walk": active["walk_model"], "stand": active["stand_model"],
        },
        "speed_mps": ONSET_PROBE_SPEED_MPS,
        "low_speed_historical_reference_same_session": False,
        "historical_p0i_rerun_this_trial": False,
        "control_eligible": eligible_control,
        "commands_sent": trial.commands_sent,
        "stop_confirmed": trial.stop_confirmed,
        "sampled_policy": policy,
        "baseline_drift_m": trial.baseline_displacement_m,
        "net_xy_displacement_m": displacement,
        "forward_x_m": trial.measured_forward_x_m,
        "lateral_y_m": trial.measured_lateral_y_m,
        "simulated_duration_s": trial.simulated_duration_s,
        "over_10mm_signal": candidate,
        "verdict": (
            "simulated_translation_above_10mm_not_gait"
            if candidate else
            "control_inconclusive" if not eligible_control else
            "no_10mm_translation_observed"
        ),
        "simulated_reward_not_evidence_of_causality": True,
        "disposable_memory_only_not_product_experience": True,
        "root_cause_proven": False,
        "gait_validated": False,
        "physical_robot_validated": False,
        "robotd_only_motor_authority": True,
        "gitlinks_modified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--robot-root", required=True, type=Path)
    parser.add_argument("--rl-root", required=True, type=Path)
    parser.add_argument("--memory", required=True, type=Path)
    parser.add_argument("--port", type=int, default=SIM_PORT)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--enable-once", action="store_true")
    args = parser.parse_args(argv)
    if (args.enable_once is not True
            or os.environ.get(RUN_OPT_IN) != "YES"):
        print("SIM-E2G refused: explicit isolated simulation opt-in required", file=sys.stderr)
        return 2
    try:
        # Validate every output path BEFORE entering a motor-controlled trial.
        if args.output.parent.resolve(strict=True) != args.state_dir.resolve(strict=True):
            raise SimMotionError("report must remain inside isolated simulator state")
        if args.output.name != "sim-e2g-report.json":
            raise SimMotionError("report name not in approved allowlist")
        if args.output.exists() or args.output.is_symlink():
            raise SimMotionError("refuse existing/linked diagnostic report")
        report = run_probe(
            args.state_dir, args.robot_root, args.rl_root,
            args.memory, port=args.port,
        )
        # No report is written after a refused/incomplete OEM trial.
        args.output.write_text(
            json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        # Report only a compact measured outcome in log; no media, identity,
        # raw body pose data, or full SQLite.
        print(json.dumps({
            "verdict": report["verdict"],
            "vx_mps": report["speed_mps"],
            "net_xy_mm": round(report["net_xy_displacement_m"] * 1000, 3),
            "forward_x_mm": round(report["forward_x_m"] * 1000, 3),
            "baseline_mm": round(report["baseline_drift_m"] * 1000, 3),
            "policy_samples": report["sampled_policy"]["policy_samples"],
            "walk_policy_samples": report["sampled_policy"]["walk_policy_samples"],
            "max_applied_vx_mps": report["sampled_policy"]["max_applied_vx_mps"],
            "limited_by": report["sampled_policy"]["limited_by"],
            "stop_confirmed": report["stop_confirmed"],
            "gait_validated": False, "root_cause_proven": False,
        }, sort_keys=True))
        return 0
    except (OSError, SimMotionError, GroundTruthError, ValueError,
            TypeError, KeyError, RuntimeError) as exc:
        print("SIM-E2G refused or incomplete: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
