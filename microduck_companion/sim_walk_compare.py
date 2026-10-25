"""P0b: controlled stand/walk telemetry comparison in PINNED MuJoCo only.

A verified passive reference is collected before the unchanged, single J2e walk
trial. Extra reads observe body joints while robotd remains the sole motor
authority. No changes to OEM code, velocity, duration or deadman.

Observing a walking policy or moving legs does not establish foot contact,
traction, stability, or a walking gait. The OEM read protocol does not expose
contacts or individual joint targets. The diagnostic may report no cause.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys

from .sim_flat_zone import GroundTruthError, read_verified_body_state
from .sim_ipc import TelemetryError
from .sim_joint_trace import (
    JOINT_NAMES, _join_policy, _summarize, collect_joint_trace,
    parse_joint_observation,
)
from .sim_motion import SimMotionError
from .sim_policy_trace import PolicySample
from .sim_walk_trial import BASELINE_LIMIT_M, WALK_TICKS, WalkTrialResult, run_walk_trial

REST_SAMPLES = 16
SAMPLE_HZ = 10
LEG_JOINTS = tuple(name for name in JOINT_NAMES
                   if name.startswith(("left_", "right_")))
MOTION_EPS_RAD = 0.005


def _checked_reference(rest: dict) -> None:
    """Refuse a walk without a verified stable same-session stand baseline."""
    if (rest.get("source") != "pinned_official_mujoco_body_and_robotd"
            or rest.get("mode") != "passive_read_only"
            or rest.get("foot_contacts_available") is not False
            or rest.get("joint_targets_available") is not False):
        raise SimMotionError("unverified stand baseline provenance")
    observations = rest.get("observations")
    summary = rest.get("summary")
    if not isinstance(observations, list) or len(observations) != REST_SAMPLES:
        raise SimMotionError("incomplete stand baseline")
    if not isinstance(summary, dict):
        raise SimMotionError("missing stand baseline summary")
    policy = summary.get("robotd_policy")
    if not isinstance(policy, dict) or (
            policy.get("policy_samples") != REST_SAMPLES
            or policy.get("stand_policy_samples") != REST_SAMPLES
            or policy.get("walk_policy_samples") != 0
            or policy.get("max_applied_vx_mps") != 0.0):
        raise SimMotionError("stand baseline contained non-stand motion")
    displacement = summary.get("net_trunk_xy_displacement_m")
    if (type(displacement) not in (int, float)
            or not math.isfinite(displacement)
            or displacement < 0 or displacement > BASELINE_LIMIT_M):
        raise SimMotionError("unstable simulator stand baseline; walk refused")
    if any(observation.get("flat_scene_safe_area") is not True
           for observation in observations):
        raise SimMotionError("unsafe simulator pose during stand baseline")


def compare_observed_states(rest: dict, moving: list[dict],
                            policies: list[PolicySample],
                            trial: WalkTrialResult) -> dict:
    """Summarize measured values without inventing a locomotion root cause."""
    if not trial.stop_confirmed:
        raise SimMotionError("cannot compare without confirmed robot.stop")
    if (len(moving) != WALK_TICKS or len(policies) != WALK_TICKS
            or trial.commands_sent != WALK_TICKS):
        raise SimMotionError("incomplete walking trace")
    active = _summarize(moving, policies)
    baseline = rest["summary"]
    delta = {
        name: (active["joint_position_range_rad"][name]
               - baseline["joint_position_range_rad"][name])
        for name in LEG_JOINTS
    }
    legs_moved = any(active["joint_position_range_rad"][name] > MOTION_EPS_RAD
                     for name in LEG_JOINTS)
    walk_seen = active["robotd_policy"]["walk_policy_samples"] > 0
    return {
        "schema_version": 1,
        "environment": "pinned_official_mujoco_only",
        "comparison": "same_simulator_session_stand_then_single_bounded_walk",
        "read_only_joint_samples": REST_SAMPLES + len(moving),
        "motor_authority": "official_robotd",
        "motion_commands_sent_by_existing_j2e_trial": trial.commands_sent,
        "stop_confirmed": trial.stop_confirmed,
        "requested_walk_speed_mps": trial.requested_speed_mps,
        "rest_sampling_hz": SAMPLE_HZ,
        "walk_sampling_hz": SAMPLE_HZ,
        "rest_trace": rest,
        "walk_trace": {"observations": moving, "summary": active},
        "joint_leg_position_range_difference_rad": delta,
        "leg_joint_motion_sampled": legs_moved,
        "walk_policy_sampled": walk_seen,
        "measured_walk_displacement_m": trial.measured_displacement_m,
        "measured_walk_baseline_m": trial.baseline_displacement_m,
        "motion_memory_outcome": trial.outcome,
        "next_intention": trial.next_intention,
        "trial": asdict(trial),
        "foot_contacts_available": False,
        "joint_targets_available": False,
        "traction_proven": False,
        "gait_validated": False,
        "locomotion_root_cause": "unknown",
        "assessment": (
            "Measured joint ranges and trunk motion at identical requested "
            "sampling frequency. No foot contacts or joint targets exposed "
            "by pinned OEM body read API. Joint motion, walk label and applied "
            "vx cannot establish a walking gait."
        ),
    }


def run_comparison(
    state_dir: str | Path, rl_root: str | Path, memory_path: str | Path, *,
    port: int = 17801,
) -> dict:
    """One existing J2e trial after a passive reference, with fail-closed reads."""
    rest = collect_joint_trace(
        state_dir, rl_root, port=port, samples=REST_SAMPLES, hz=SAMPLE_HZ,
    )
    _checked_reference(rest)
    moving: list[dict] = []
    policies: list[PolicySample] = []
    previous_sim_time: float | None = None

    def observe(policy: PolicySample) -> None:
        nonlocal previous_sim_time
        payload, at = read_verified_body_state(state_dir, rl_root, port=port)
        frame = parse_joint_observation(payload, at)
        if frame["flat_scene_safe_area"] is not True:
            raise GroundTruthError("unsafe pose during walking joint diagnostic")
        if (previous_sim_time is not None
                and frame["sim_time_s"] <= previous_sim_time):
            raise GroundTruthError("stalled simulator clock in walking joint diagnostic")
        _join_policy(frame, policy)
        previous_sim_time = frame["sim_time_s"]
        moving.append(frame)
        policies.append(policy)

    trial = run_walk_trial(
        state_dir, rl_root, memory_path, port=port, on_policy_sample=observe,
    )
    return compare_observed_states(rest, moving, policies, trial)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0b opt-in single MuJoCo stand/walk comparison")
    parser.add_argument("--enable-once", action="store_true")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--rl-root", type=Path, required=True)
    parser.add_argument("--memory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=17801)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.enable_once or os.environ.get("MICRODUCK_SIM_WALK_COMPARE") != "YES":
        print("P0b walking comparison disabled: --enable-once and env=YES required",
              file=sys.stderr)
        return 2
    try:
        result = run_comparison(
            args.state_dir, args.rl_root, args.memory, port=args.port,
        )
        encoded = json.dumps(result, allow_nan=False, sort_keys=True, indent=2)
        args.output.write_text(encoded + "\n", encoding="utf-8")
        # Print concise measured evidence; full raw trace is a CI artifact.
        print(json.dumps({
            "environment": result["environment"],
            "motion_memory_outcome": result["motion_memory_outcome"],
            "measured_walk_displacement_m": result["measured_walk_displacement_m"],
            "rest_net_trunk_xy_displacement_m":
                result["rest_trace"]["summary"]["net_trunk_xy_displacement_m"],
            "walk_net_trunk_xy_displacement_m":
                result["walk_trace"]["summary"]["net_trunk_xy_displacement_m"],
            "rest_policy": result["rest_trace"]["summary"]["robotd_policy"],
            "walk_policy": result["walk_trace"]["summary"]["robotd_policy"],
            "leg_joint_motion_sampled": result["leg_joint_motion_sampled"],
            "stop_confirmed": result["stop_confirmed"],
            "locomotion_root_cause": result["locomotion_root_cause"],
            "gait_validated": False,
        }, allow_nan=False, sort_keys=True))
        if result["motion_memory_outcome"] == "no_progress_observed":
            return 3  # confirmed negative progress, NOT a failed safety test
        if (result["motion_memory_outcome"] != "translation_observed"
                or not result["walk_policy_sampled"]):
            return 4  # incomplete/unverified; CI MUST fail
        return 0
    except (GroundTruthError, TelemetryError, SimMotionError, ValueError, OSError) as exc:
        print(f"P0b comparison failed; locomotion NOT validated: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
