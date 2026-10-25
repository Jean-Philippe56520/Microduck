"""P0e: audit *effective* native MuJoCo position actuator dynamics.

Strictly OFFLINE: validates stopped P0b and P0d observations, then compares
the actuator's actual input state BEFORE mj_step with its force calculated
by the original solver. No motor APIs, writes or MuJoCo physics steps here.

For the pinned position-actuator model (gear=1) the unclamped scalar force is:
    gain[0] * ctrl + bias[1] * qpos_before + bias[2] * qvel_before
then MuJoCo's configured actuator force range is applied. We separately
report actual gains, position tracking ranges, contact loads and residuals.

Even a perfect match does NOT establish a gait, suitable gains, traction,
or hardware validity. This is a narrow consistency test, not calibration.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path
import statistics
import sys

from .sim_contact_replay import _validated_frames
from .sim_flat_zone import GroundTruthError
from .sim_live_solver_analyze import (
    MIN_PHASE_FRAMES, _read_solver_trace, analyze_live_solver,
)
from .sim_live_solver_tap import EXPECTED_TIMESTEP_S, JOINT_NAMES

NOMINAL_WALK_GAIN = 0.55  # pinned RL chosen_actuator kp, NOT a physical setting
NOMINAL_STAND_RATIO = 0.8  # pinned robotd default standing_gain_ratio
EXPECTED_FORCERANGE = (-0.96, 0.96)
RESIDUAL_TOLERANCE_NM = 0.002
GAIN_TOLERANCE = 0.003


def _finite(value: object, context: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise GroundTruthError(f"P0e missing or invalid {context}")
    return float(value)


def validate_pre_step_audit(path: Path) -> list[dict]:
    """Fail closed on legacy P0d streams and inconsistent integration epochs."""
    with path.open(encoding="utf-8") as fh:
        first = fh.readline(16000)
    try:
        header = json.loads(first)
    except (ValueError, TypeError) as exc:
        raise GroundTruthError("missing P0e header") from exc
    if (not isinstance(header, dict)
            or header.get("p0e_active_gain_pre_step") is not True):
        raise GroundTruthError("legacy P0d trace has no pre-step actuator audit")

    frames = _read_solver_trace(path)  # provenance, continuous time, contacts
    for row in frames:
        pre = row.get("pre_step_actuators")
        if not isinstance(pre, dict):
            raise GroundTruthError("P0e missing pre-step capture")
        t = _finite(pre.get("time_before_step_s"), "pre-step clock")
        if abs(row["sim_time_s"] - t - EXPECTED_TIMESTEP_S) > 1e-6:
            raise GroundTruthError("P0e pre/post solver clock mismatch")
        actuators = pre.get("actuators")
        if not isinstance(actuators, dict) or set(actuators) != set(JOINT_NAMES):
            raise GroundTruthError("P0e missing or extra actuator model entries")
        for name, data in actuators.items():
            if not isinstance(data, dict):
                raise GroundTruthError(f"P0e malformed actuator {name}")
            expected_keys = {
                "control_rad", "position_rad", "velocity_rad_s",
                "gain_p_nm_per_rad", "bias_position_nm_per_rad",
                "bias_velocity_nm_s_per_rad", "gear", "force_limited",
                "force_min_nm", "force_max_nm",
                "joint_damping_nm_s", "joint_frictionloss_nm",
            }
            if set(data) != expected_keys:
                raise GroundTruthError(f"P0e altered actuator model fields: {name}")
            for key in expected_keys - {"force_limited"}:
                _finite(data[key], f"{name}/{key}")
            if data["force_limited"] is not True:
                raise GroundTruthError(f"P0e force limiting missing: {name}")
            if abs(data["gear"] - 1.0) > 1e-8:
                raise GroundTruthError(f"P0e unsupported non-unit actuator gear: {name}")
            if (data["force_min_nm"] >= data["force_max_nm"]
                    or abs(data["force_min_nm"] - EXPECTED_FORCERANGE[0]) > 1e-6
                    or abs(data["force_max_nm"] - EXPECTED_FORCERANGE[1]) > 1e-6):
                raise GroundTruthError(f"P0e unexpected OEM actuator force limits: {name}")
            if (data["gain_p_nm_per_rad"] < 0
                    or abs(data["bias_position_nm_per_rad"] +
                           data["gain_p_nm_per_rad"]) > 1e-7
                    or abs(data["bias_velocity_nm_s_per_rad"]) > 1e-7):
                raise GroundTruthError(f"P0e unexpected position-actuator dynamics: {name}")
            if abs(data["control_rad"] -
                   row["actuator_position_controls_rad"][name]) > 1e-9:
                raise GroundTruthError(f"P0e ctrl changed during native mj_step: {name}")
    return frames


def _percentile(series: list[float], fraction: float) -> float:
    numbers = sorted(series)
    index = min(len(numbers) - 1, max(0, math.ceil(fraction * len(numbers)) - 1))
    return numbers[index]


def _force_expectation(row: dict, name: str) -> tuple[float, float, bool]:
    data = row["pre_step_actuators"]["actuators"][name]
    gear = data["gear"]
    free = (data["gain_p_nm_per_rad"] * data["control_rad"]
            + data["bias_position_nm_per_rad"] * gear * data["position_rad"]
            + data["bias_velocity_nm_s_per_rad"] * gear * data["velocity_rad_s"])
    predicted = max(data["force_min_nm"], min(data["force_max_nm"], free))
    measured = row["actuator_force_simulated_nm"][name]
    clipped = abs(free - predicted) > 1e-9
    return predicted, measured, clipped


def _phase_audit(rows: list[dict], expected_gain: float) -> dict:
    if len(rows) < MIN_PHASE_FRAMES:
        raise GroundTruthError("P0e phase missing sufficient native solver frames")
    joints = {}
    for name in JOINT_NAMES:
        inputs = [row["pre_step_actuators"]["actuators"][name] for row in rows]
        gains = [x["gain_p_nm_per_rad"] for x in inputs]
        errors = []
        clipped = 0
        measured_near_limit = 0
        for row in rows:
            predicted, measured, saturation = _force_expectation(row, name)
            errors.append(abs(predicted - measured))
            clipped += int(saturation)
            measured_near_limit += int(abs(measured) >=
                                       EXPECTED_FORCERANGE[1] - 0.001)
        controls = [x["control_rad"] for x in inputs]
        positions = [x["position_rad"] for x in inputs]
        joints[name] = {
            "active_gain_min_nm_per_rad": min(gains),
            "active_gain_max_nm_per_rad": max(gains),
            "active_gain_median_nm_per_rad": statistics.median(gains),
            "frames_gain_matches_expected": sum(
                abs(g - expected_gain) <= GAIN_TOLERANCE for g in gains),
            "frames_gain_zero": sum(abs(g) < 1e-10 for g in gains),
            "frames_force_clamped_by_model": clipped,
            "frames_observed_force_near_limit": measured_near_limit,
            "force_formula_abs_residual_max_nm": max(errors),
            "force_formula_abs_residual_p95_nm": _percentile(errors, .95),
            "force_formula_residual_rms_nm": math.sqrt(
                statistics.fmean(e * e for e in errors)),
            "frames_residual_within_2_mNm": sum(
                e <= RESIDUAL_TOLERANCE_NM for e in errors),
            "pre_step_control_range_rad": max(controls) - min(controls),
            "pre_step_joint_angle_range_rad": max(positions) - min(positions),
            "joint_damping_nm_s_min": min(x["joint_damping_nm_s"] for x in inputs),
            "joint_damping_nm_s_max": max(x["joint_damping_nm_s"] for x in inputs),
            "joint_frictionloss_nm_min": min(x["joint_frictionloss_nm"] for x in inputs),
            "joint_frictionloss_nm_max": max(x["joint_frictionloss_nm"] for x in inputs),
        }
    return {
        "frames": len(rows),
        "expected_pinned_oem_gain_nm_per_rad": expected_gain,
        "joints": joints,
        "total_actuator_force_formula_samples": len(rows) * len(JOINT_NAMES),
        "total_force_clamped_samples": sum(
            x["frames_force_clamped_by_model"] for x in joints.values()),
        "total_observed_force_near_limit_samples": sum(
            x["frames_observed_force_near_limit"] for x in joints.values()),
        "max_force_formula_residual_nm": max(
            x["force_formula_abs_residual_max_nm"] for x in joints.values()),
        "all_force_samples_within_2_mNm": all(
            x["frames_residual_within_2_mNm"] == len(rows)
            for x in joints.values()),
    }


def audit_native_actuators(p0b: dict, rows: list[dict]) -> dict:
    """Validate OEM native contacts/trial and compare phase-by-phase gains."""
    reference = analyze_live_solver(p0b, rows)
    stand, walk = _validated_frames(p0b)
    windows = {
        "stand": (stand[0]["sim_time_s"], stand[-1]["sim_time_s"]),
        "walk": (walk[0]["sim_time_s"], walk[-1]["sim_time_s"]),
    }
    groups = {
        phase: [r for r in rows if start <= r["sim_time_s"] <= end]
        for phase, (start, end) in windows.items()
    }
    stand_data = _phase_audit(groups["stand"],
                              NOMINAL_WALK_GAIN * NOMINAL_STAND_RATIO)
    walk_data = _phase_audit(groups["walk"], NOMINAL_WALK_GAIN)
    return {
        "schema_version": 1,
        "source": "native_pre_step_actuator_gain_and_post_solver_force",
        "pinned_oem": {
            "microduck_rl_sha": reference["provenance"]["rl_commit"],
            "flat_scene_git_blob": reference["provenance"]["flat_scene_git_blob"],
            "nominal_position_gain_nm_per_rad": NOMINAL_WALK_GAIN,
            "default_robotd_gain_register": 200,
            "default_standing_ratio": NOMINAL_STAND_RATIO,
            "expected_stand_gain_nm_per_rad":
                NOMINAL_WALK_GAIN * NOMINAL_STAND_RATIO,
            "expected_walk_gain_nm_per_rad": NOMINAL_WALK_GAIN,
            "nominal_force_range_nm": list(EXPECTED_FORCERANGE),
            "gain_source": "pinned_MJCF_chosen_actuator_and_robotd_default_tuning",
        },
        "original_live_solver": True,
        "pre_step_snapshot_precedes_oem_mj_step": True,
        "no_motor_commands_or_parameter_changes": True,
        "p0b_stop_confirmed": True,
        "p0b_displacement_m": reference["measured_p0b_displacement_m"],
        "double_foot_loading": {
            "stand_frames": reference["stand"]
                ["both_feet_with_force_gt_0_1n_frames"],
            "walk_frames": reference["walk"]
                ["both_feet_with_force_gt_0_1n_frames"],
            "walk_total_frames": reference["walk"]["frames"],
        },
        "stand": stand_data,
        "walk": walk_data,
        "gait_validated": False,
        "motor_hardware_validated": False,
        "locomotion_root_cause": "unknown",
        "limits": (
            "Gain/force consistency is not proof that the OEM gain is suited "
            "to the ONNX gait; foot loads are sampled 50 Hz, not continuous; "
            "contact/force caches refer to a solver step, not the integrated "
            "post-step position; active pre-step control and position use the "
            "same epoch. Probe adds overhead, and real robot was not tested."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="P0e audit native OEM position gains and force formula (offline)"
    )
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--p0b", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        p0b = json.loads(
            args.p0b.read_text(encoding="utf-8"),
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        frames = validate_pre_step_audit(args.input)
        result = audit_native_actuators(p0b, frames)
        args.output.write_text(json.dumps(
            result, indent=2, sort_keys=True, allow_nan=False
        ) + "\n", encoding="utf-8")
        legs = ("left_hip_roll", "right_hip_roll", "left_knee", "right_knee")
        print(json.dumps({
            "p0b_displacement_m": result["p0b_displacement_m"],
            "double_foot_loading": result["double_foot_loading"],
            "stand_frames": result["stand"]["frames"],
            "walk_frames": result["walk"]["frames"],
            "stand_all_force_samples_within_2_mNm":
                result["stand"]["all_force_samples_within_2_mNm"],
            "walk_all_force_samples_within_2_mNm":
                result["walk"]["all_force_samples_within_2_mNm"],
            "stand_force_formula_residual_max_nm":
                result["stand"]["max_force_formula_residual_nm"],
            "walk_force_formula_residual_max_nm":
                result["walk"]["max_force_formula_residual_nm"],
            "walk_clamped_actuator_samples":
                result["walk"]["total_force_clamped_samples"],
            "stand_active_gains": {
                n: result["stand"]["joints"][n]["active_gain_median_nm_per_rad"]
                for n in legs
            },
            "walk_active_gains": {
                n: result["walk"]["joints"][n]["active_gain_median_nm_per_rad"]
                for n in legs
            },
            "gait_validated": False,
            "locomotion_root_cause": "unknown",
        }, allow_nan=False, sort_keys=True))
    except (GroundTruthError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"P0e native actuator audit rejected: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
