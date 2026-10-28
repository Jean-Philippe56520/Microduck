"""SIM-E2-C: signed joint tracking from the ORIGINAL archived P0e solver.

OFFLINE ONLY. Reuses P0j's exact SHA-256, full 888-frame provenance, phase
windows and confirmed OEM stop; P0e's pre-step gain/actuator validator is reused.
Does not connect to a daemon, simulate a step or send a motor command.

The samples are original MuJoCo control/angle observations, NOT raw ONNX inputs,
actions, hardware servo readings, signed floor traction or gait validation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import sys

from .sim_actuator_gain_audit import validate_pre_step_audit
from .sim_p0j_load_transfer import (
    EXPECTED_SHA256, EXPECTED_WINDOWS, RL_COMMIT, SAMPLE_INTERVAL_S,
    SCENE_BLOB, SOURCE_URL, OfflineTraceError, _read_exact, _strict_json,
    _verified_frames, _windows, demand, number,
)

SELECTED_JOINTS = (
    "left_hip_roll", "right_hip_roll", "left_knee", "right_knee",
)


def summarize_phase(frames: list[dict]) -> dict:
    """Summarize a *contiguous* window without inferring motor causality."""
    demand(isinstance(frames, list) and len(frames) >= 2,
           "too few frames for a joint-tracking phase")
    times = [number(row.get("sim_time_s"), "phase time") for row in frames]
    demand(all(abs(b - a - SAMPLE_INTERVAL_S) < 1e-5
               for a, b in zip(times, times[1:])),
           "missing or duplicated original solver tick")

    pairs: dict[str, tuple[list[float], list[float]]] = {}
    joints = {}
    for joint in SELECTED_JOINTS:
        controls, positions = [], []
        for row in frames:
            pre = row.get("pre_step_actuators")
            demand(isinstance(pre, dict), "missing original pre-step data")
            actuators = pre.get("actuators")
            demand(isinstance(actuators, dict), "missing original actuator table")
            data = actuators.get(joint)
            demand(isinstance(data, dict), "missing original actuator " + joint)
            controls.append(number(data.get("control_rad"), joint + " control"))
            positions.append(number(data.get("position_rad"), joint + " position"))
        errors = [ctrl - pos for ctrl, pos in zip(controls, positions)]
        pairs[joint] = controls, positions
        joints[joint] = {
            "mean_signed_control_minus_position_deg": math.degrees(
                statistics.fmean(errors)),
            "signed_control_minus_position_min_deg": math.degrees(min(errors)),
            "signed_control_minus_position_max_deg": math.degrees(max(errors)),
            "population_sd_control_minus_position_deg": math.degrees(
                statistics.pstdev(errors)),
            "control_excursion_deg": math.degrees(max(controls) - min(controls)),
            "position_excursion_deg": math.degrees(max(positions) - min(positions)),
        }

    def pair_correlation(field_index: int) -> float | None:
        left = pairs["left_hip_roll"][field_index]
        right = pairs["right_hip_roll"][field_index]
        if (statistics.pstdev(left) < 1e-9
                or statistics.pstdev(right) < 1e-9):
            return None
        correlation = statistics.correlation(left, right)
        demand(math.isfinite(correlation), "nonfinite phase correlation")
        return correlation

    return {
        "frames": len(frames),
        "sim_time_start_s": times[0],
        "sim_time_end_s": times[-1],
        "joints": joints,
        "hip_roll_left_right_control_correlation": pair_correlation(0),
        "hip_roll_left_right_position_correlation": pair_correlation(1),
    }


def audit_files(solver_tap: Path, solver_analysis: Path,
                walk_comparison: Path) -> dict:
    """Refuse any substitute for the original stopped P0e GitHub CI run."""
    frames = _verified_frames(_read_exact(solver_tap))
    # P0e's own validator checks pre-step actuator properties and time coherence.
    validated = validate_pre_step_audit(solver_tap)
    demand(len(validated) == len(frames),
           "original P0e pre-step validator disagrees with archived frames")
    analysis = _strict_json(_read_exact(solver_analysis).decode("utf-8"))
    comparison = _strict_json(_read_exact(walk_comparison).decode("utf-8"))
    demand(isinstance(analysis, dict) and isinstance(comparison, dict),
           "missing original P0e analysis or comparison")
    windows = _windows(analysis, comparison)

    result = {}
    for phase, (low, high) in windows.items():
        subset = [row for row in frames if low <= row["sim_time_s"] <= high]
        demand(len(subset) == EXPECTED_WINDOWS[phase],
               "missing original P0e " + phase + " window")
        expected = analysis.get(phase)
        demand(isinstance(expected, dict)
               and expected.get("frames") == len(subset),
               "P0e solver phase frame count changed")
        result[phase] = summarize_phase(subset)
    return {
        "schema_version": 1,
        "source": "sha256_verified_archived_P0e_native_pre_step_actuators",
        "source_run": SOURCE_URL,
        "source_sha256": dict(EXPECTED_SHA256),
        "rl_commit": RL_COMMIT,
        "scene_git_blob": SCENE_BLOB,
        "stand_and_walk_are_10hz_bracketed_windows_not_50hz_policy_labels": True,
        "joint_tracking_is_original_MuJoCo_ctrl_and_qpos_not_ONNX_output": True,
        "real_robotd_61_input_observations_available": False,
        "previous_raw_ONNX_action_history_available": False,
        "signed_world_horizontal_traction_available": False,
        "new_motor_commands": 0,
        "original_trial_stop_confirmed": True,
        "original_trial_command_count": 24,
        "final_trial_displacement_m": comparison["measured_walk_displacement_m"],
        "phases": result,
        "gait_validated": False,
        "root_cause_proven": False,
        "caveat": (
            "One headless CI run, not WSLg. The 50Hz P0e frames are bracketed by "
            "10Hz P0b policy windows. Target-angle differences, static offsets and "
            "pair correlations do not establish raw ONNX actions, gait phase, "
            "contact patch slip, actuator suitability or a locomotion cause."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SIM-E2-C: offline signed P0e actuator tracking (never motor)")
    parser.add_argument("--solver-tap", type=Path, required=True)
    parser.add_argument("--solver-analysis", type=Path, required=True)
    parser.add_argument("--walk-comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit_files(args.solver_tap, args.solver_analysis,
                             args.walk_comparison)
        args.output.write_text(json.dumps(
            result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8")
        print(json.dumps({
            "source_run": result["source_run"],
            "stand_frames": result["phases"]["stand"]["frames"],
            "walk_frames": result["phases"]["walk"]["frames"],
            "stand_signed_means_deg": {
                j: result["phases"]["stand"]["joints"][j]
                ["mean_signed_control_minus_position_deg"]
                for j in SELECTED_JOINTS
            },
            "gait_validated": False,
            "root_cause_proven": False,
            "new_motor_commands": 0,
        }, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OfflineTraceError, OSError, UnicodeError, ValueError) as exc:
        print("SIM-E2-C refuses original P0e archive: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
