"""P0d offline validation and comparison of ORIGINAL live MuJoCo solver data.

Requires a complete, STOP-confirmed verified P0b trace and a non-blocking
on-step stream from the exact pinned body server. Force measurements come
from mj_contactForce on the ORIGINAL live solver MjData, not from P0c's
offline geometric replay. This does not imply gait/traction validation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import sys

from .sim_contact_replay import _validated_frames
from .sim_flat_zone import FLAT_SCENE_BLOB, GroundTruthError, RL_COMMIT
from .sim_live_solver_tap import (
    EVERY_N_STEPS, EXPECTED_TIMESTEP_S, JOINT_NAMES,
)

MAX_INPUT_BYTES = 15_000_000
MAX_FRAMES = 4000
MIN_PHASE_FRAMES = 20
MIN_NORMAL_LOAD_N = 0.1


def _finite(x, label: str) -> float:
    if type(x) not in (int, float) or not math.isfinite(x):
        raise GroundTruthError(f"invalid live solver {label}")
    return float(x)


def _read_solver_trace(path: Path) -> list[dict]:
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise GroundTruthError("missing or oversized live solver trace")
    try:
        with path.open(encoding="utf-8") as fh:
            records = [
                json.loads(line, parse_constant=lambda _: (
                    _ for _ in ()).throw(ValueError()))
                for line in fh if line.strip()
            ]
    except (UnicodeDecodeError, ValueError, OSError) as exc:
        raise GroundTruthError("invalid or truncated solver JSONL") from exc
    if not (MIN_PHASE_FRAMES * 2 <= len(records) <= MAX_FRAMES + 1):
        raise GroundTruthError("incomplete or excessive solver trace")
    header = records[0]
    if (not isinstance(header, dict) or header.get("kind") != "header"
            or header.get("schema_version") != 1
            or header.get("source") != "live_pinned_oem_mujoco_mj_step_tap"
            or header.get("rl_commit") != RL_COMMIT
            or header.get("flat_scene_git_blob") != FLAT_SCENE_BLOB
            or header.get("sample_every_n_physics_steps") != EVERY_N_STEPS
            or _finite(header.get("model_timestep_s"), "timestep")
               != EXPECTED_TIMESTEP_S
            or header.get("capture_is_not_actuator_authority") is not True):
        raise GroundTruthError("unverified solver header or model provenance")
    frames = records[1:]
    previous_step, previous_time = None, None
    for row in frames:
        if not isinstance(row, dict) or row.get("kind") != "frame":
            raise GroundTruthError("incomplete solver stream or tap failure")
        step = row.get("step")
        if type(step) is not int or step <= 0 or step % EVERY_N_STEPS:
            raise GroundTruthError("invalid original solver step number")
        timestamp = _finite(row.get("sim_time_s"), "sim time")
        if (previous_step is not None
                and (step != previous_step + EVERY_N_STEPS
                     or abs(timestamp - previous_time -
                            EVERY_N_STEPS * EXPECTED_TIMESTEP_S) > 0.001)):
            raise GroundTruthError("lost/out-of-order solver frame or altered physics cadence")
        previous_step, previous_time = step, timestamp
        _finite(row.get("capture_us"), "capture overhead")
        xyz = row.get("trunk_xyz_after_integration_m")
        if (not isinstance(xyz, list) or len(xyz) != 3):
            raise GroundTruthError("missing original solver trunk pose")
        for x in xyz:
            _finite(x, "trunk pose")
        for field in ("actuator_position_controls_rad",
                      "joint_angles_post_integration_rad",
                      "actuator_force_simulated_nm"):
            values = row.get(field)
            if not isinstance(values, dict) or set(values) != set(JOINT_NAMES):
                raise GroundTruthError("missing original per-joint actuator telemetry")
            for v in values.values():
                _finite(v, field)
        feet = row.get("contacts_original_solver")
        foot_sites = row.get("foot_sites_solver_cache_xyz_m")
        if (row.get("live_solver_source") is not True
                or not isinstance(feet, dict)
                or set(feet) != {"left", "right"}
                or not isinstance(foot_sites, dict)
                or set(foot_sites) != {"left", "right"}):
            raise GroundTruthError("original live solver contacts are not proven")
        for side in ("left", "right"):
            foot = feet[side]
            if not isinstance(foot, dict):
                raise GroundTruthError("missing per-foot solver contact")
            pairs = foot.get("pair_count")
            if type(pairs) is not int or pairs < 0 or pairs > 100:
                raise GroundTruthError("invalid solver pair count")
            for key in ("normal_force_n", "tangent_force_norm_n"):
                _finite(foot.get(key), key)
            distance = foot.get("min_signed_distance_m")
            if distance is not None:
                _finite(distance, "signed contact distance")
            if (pairs == 0 and distance is not None) or (
                    pairs > 0 and distance is None):
                raise GroundTruthError("inconsistent solver contact geometry")
            site = foot_sites[side]
            if not isinstance(site, list) or len(site) != 3:
                raise GroundTruthError("missing solver foot site")
            for v in site:
                _finite(v, "foot site")
    return frames


def _range(frames: list[dict], path: str) -> dict:
    keys = JOINT_NAMES
    return {
        key: max(row[path][key] for row in frames)
             - min(row[path][key] for row in frames)
        for key in keys
    }


def _phase_summary(rows: list[dict]) -> dict:
    if len(rows) < MIN_PHASE_FRAMES:
        raise GroundTruthError("insufficient native solver coverage for a P0b phase")
    foot_summary = {}
    for side in ("left", "right"):
        loaded = [
            row for row in rows
            if row["contacts_original_solver"][side]["normal_force_n"]
               > MIN_NORMAL_LOAD_N
        ]
        speed_during_consecutive_load = []
        for a, b in zip(rows, rows[1:]):
            if (a["contacts_original_solver"][side]["normal_force_n"] >
                    MIN_NORMAL_LOAD_N
                    and b["contacts_original_solver"][side]["normal_force_n"] >
                    MIN_NORMAL_LOAD_N):
                dt = b["sim_time_s"] - a["sim_time_s"]
                if dt <= 0:
                    raise GroundTruthError("non-advancing native solver time")
                start = a["foot_sites_solver_cache_xyz_m"][side]
                end = b["foot_sites_solver_cache_xyz_m"][side]
                speed_during_consecutive_load.append(
                    math.hypot(end[0] - start[0], end[1] - start[1]) / dt
                )
        foot_summary[side] = {
            "frames_with_any_solver_contact": sum(
                f["contacts_original_solver"][side]["pair_count"] > 0
                for f in rows
            ),
            "frames_with_normal_force_gt_0_1n": len(loaded),
            "max_original_normal_force_n": max(
                row["contacts_original_solver"][side]["normal_force_n"]
                for row in rows
            ),
            "mean_original_normal_force_n": statistics.fmean(
                row["contacts_original_solver"][side]["normal_force_n"]
                for row in rows
            ),
            "max_original_tangential_force_norm_n": max(
                row["contacts_original_solver"][side]["tangent_force_norm_n"]
                for row in rows
            ),
            "max_foot_site_world_xy_speed_during_consecutive_load_mps":
                max(speed_during_consecutive_load, default=None),
            "site_speed_is_not_true_contact_patch_slip": True,
        }
    return {
        "frames": len(rows),
        "sim_time_start_s": rows[0]["sim_time_s"],
        "sim_time_end_s": rows[-1]["sim_time_s"],
        "original_solver_contacts": foot_summary,
        "actuator_control_range_rad": _range(rows, "actuator_position_controls_rad"),
        "joint_angle_range_rad": _range(rows, "joint_angles_post_integration_rad"),
        "actuator_force_range_nm": _range(rows, "actuator_force_simulated_nm"),
        "net_trunk_xy_m": math.hypot(
            rows[-1]["trunk_xyz_after_integration_m"][0]
                - rows[0]["trunk_xyz_after_integration_m"][0],
            rows[-1]["trunk_xyz_after_integration_m"][1]
                - rows[0]["trunk_xyz_after_integration_m"][1],
        ),
    }


def analyze_live_solver(trace: dict, raw_frames: list[dict]) -> dict:
    """Align live solver samples to the 10-Hz P0b observation windows."""
    stand, moving = _validated_frames(trace)
    if (trace.get("motion_memory_outcome") != "no_progress_observed"
            or trace.get("walk_policy_sampled") is not True
            or trace.get("motor_authority") != "official_robotd"):
        raise GroundTruthError("P0d requires negative verified P0b motor outcome")
    if not raw_frames:
        raise GroundTruthError("missing live solver frames")
    ranges = {
        "stand": (stand[0]["sim_time_s"], stand[-1]["sim_time_s"]),
        "walk": (moving[0]["sim_time_s"], moving[-1]["sim_time_s"]),
    }
    if ranges["stand"][1] >= ranges["walk"][0]:
        raise GroundTruthError("P0b phase windows overlap")
    phase_rows = {
        name: [
            row for row in raw_frames if lo <= row["sim_time_s"] <= hi
        ]
        for name, (lo, hi) in ranges.items()
    }
    phase = {name: _phase_summary(rows) for name, rows in phase_rows.items()}
    costs = [frame["capture_us"] for frame in raw_frames]
    return {
        "schema_version": 1,
        "source": "original_live_pinned_oem_mujoco_solver",
        "provenance": {
            "rl_commit": RL_COMMIT,
            "flat_scene_git_blob": FLAT_SCENE_BLOB,
            "full_stream_validated": True,
            "same_world_as_official_robotd": True,
            "measurement_hook": "post_oem_mj_step_every_fourth_step",
        },
        "all_frames": len(raw_frames),
        "capture_overhead_us": {
            "mean": statistics.fmean(costs),
            "peak": max(costs),
        },
        "phase_windows_from_p0b_10hz": ranges,
        "stand": phase["stand"],
        "walk": phase["walk"],
        "original_solver_foot_contacts_observed": True,
        "original_solver_contact_forces_observed": True,
        "original_actuator_controls_observed": True,
        "diagnostic_adds_processing_to_simulator": True,
        "never_modified_oem_joint_targets": True,
        "gait_validated": False,
        "traction_validated": False,
        "locomotion_root_cause": "unknown",
        "measured_p0b_displacement_m": trace["measured_walk_displacement_m"],
        "original_p0b_stop_confirmed": True,
        "caveat": (
            "mj_contactForce comes from the just-completed native solver step. "
            "Recorded qpos is post-integration and MuJoCo contact/site caches "
            "can be from pre-integration state. Offline 10-Hz P0b phase labels "
            "bracket 50-Hz solver frames, not exact per-frame policy IDs. "
            "Foot site XY speed during load is a proxy, NOT contact-patch slip. "
            "Monkeypatch measurement has nonzero execution overhead and is "
            "not a physical robot validation."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P0d validate genuine live solver telemetry")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--p0b", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        p0b = json.loads(
            args.p0b.read_text(encoding="utf-8"),
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        frames = _read_solver_trace(args.input)
        result = analyze_live_solver(p0b, frames)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "solver_frame_count": result["all_frames"],
            "p0b_displacement_m": result["measured_p0b_displacement_m"],
            "capture_overhead_us": result["capture_overhead_us"],
            "stand": {
                "frames": result["stand"]["frames"],
                "feet": result["stand"]["original_solver_contacts"],
            },
            "walk": {
                "frames": result["walk"]["frames"],
                "feet": result["walk"]["original_solver_contacts"],
                "leg_control_ranges_rad": {
                    name: value
                    for name, value in result["walk"]["actuator_control_range_rad"].items()
                    if name.startswith(("left_", "right_"))
                },
            },
            "gait_validated": False,
            "locomotion_root_cause": "unknown",
        }, allow_nan=False, sort_keys=True))
        return 0
    except (GroundTruthError, ValueError, TypeError, OSError, KeyError) as exc:
        print(f"P0d solver diagnostic rejected: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
