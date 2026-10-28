"""SIM-E2H: OFFLINE, fail-closed foot-load audit of ONE stopped OEM sim run.

Uses P0d original MuJoCo mj_step snapshots and E2G's two simulator-clock
bookends. Does not send commands, open sockets, manipulate MuJoCo, edit
ExperienceMemory, or infer gait from net translation. The bracket includes
transitions and post-stop: support events are NOT per-command labels.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import statistics
import sys

from .sim_flat_zone import GroundTruthError
from .sim_live_solver_analyze import _read_solver_trace
from .sim_p0j_load_transfer import LOADED_N
from .sim_policy_pair import PINNED_V8_SHA256
from .sim_walk_trial import ONSET_PROBE_SPEED_MPS, ONSET_PROBE_TICKS

MAX_REPORT_BYTES = 16000
MIN_BRACKET_FRAMES = 40
MAX_BRACKET_FRAMES = 180
MAX_BRACKET_SEC = 3.0
MAX_SOLVER_POSE_DELTA_M = 0.015
MAX_TAP_P95_US = 2000.0


def _number(value: object, key: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise GroundTruthError("missing/nonfinite " + key)
    return float(value)


def _load_report(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_REPORT_BYTES:
        raise GroundTruthError("missing/invalid stopped E2G report")
    try:
        report = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, UnicodeError, OSError) as exc:
        raise GroundTruthError("invalid stopped E2G JSON") from exc
    if not isinstance(report, dict):
        raise GroundTruthError("invalid E2G report shape")
    if (report.get("experiment")
            != "SIM-E2G_one_fixed_speed_onset_pinned_OEM_sim_only"
            or report.get("robotd_only_motor_authority") is not True
            or report.get("network_slots_verified_from_live_robotd") is not True
            or report.get("pinned_v8_sha256") != PINNED_V8_SHA256
            or report.get("active_gait") != {
                "walk": "alpha_walking.onnx", "stand": "alpha_stand.onnx",
            }
            or report.get("speed_mps") != ONSET_PROBE_SPEED_MPS
            or report.get("commands_sent") != ONSET_PROBE_TICKS
            or report.get("stop_confirmed") is not True
            or report.get("gait_validated") is not False):
        raise GroundTruthError("E2G policy, provenance or stop not verified")
    policy = report.get("sampled_policy")
    if (not isinstance(policy, dict)
            or policy.get("policy_samples") != ONSET_PROBE_TICKS
            or policy.get("walk_policy_samples", 0) < ONSET_PROBE_TICKS - 4
            or policy.get("limited_by") != []
            or _number(policy.get("max_applied_vx_mps"), "applied") < .25):
        raise GroundTruthError("E2G control stream not eligible")
    start = _number(report.get("sim_baseline_time_s"), "baseline time")
    end = _number(report.get("sim_after_stop_time_s"), "after-stop time")
    duration = _number(report.get("simulated_duration_s"), "duration")
    if not (start >= 0 and 0 < end - start < MAX_BRACKET_SEC
            and abs(end - start - duration) < .001):
        raise GroundTruthError("E2G simulator time window is invalid")
    return report


def summarize_support(trace_path: Path, report_path: Path) -> dict:
    """No extrapolation beyond a contiguous, source-checked solver bracket."""
    report = _load_report(report_path)
    frames = _read_solver_trace(trace_path)  # P0d: verifies ALL rows, gaps, model
    start = report["sim_baseline_time_s"]
    end = report["sim_after_stop_time_s"]
    if (frames[0]["sim_time_s"] > start + .02
            or frames[-1]["sim_time_s"] < end - .02):
        raise GroundTruthError("solver stream does not cover complete E2G bracket")
    middle = [f for f in frames if start <= f["sim_time_s"] <= end]
    if not MIN_BRACKET_FRAMES <= len(middle) <= MAX_BRACKET_FRAMES:
        raise GroundTruthError("insufficient/oversized original solver bracket")
    if middle[0]["sim_time_s"] > start + .025 or middle[-1]["sim_time_s"] < end - .025:
        raise GroundTruthError("uncovered E2G time edges")
    if not trace_path.is_file() or trace_path.is_symlink():
        raise GroundTruthError("untrusted live solver trace path")

    classes = {"both": 0, "left_only": 0, "right_only": 0, "neither": 0}
    shares = []
    loads = {"left": [], "right": []}
    sites = {"left": [], "right": []}
    for row in middle:
        foot = row["contacts_original_solver"]
        left = _number(foot["left"]["normal_force_n"], "left normal force")
        right = _number(foot["right"]["normal_force_n"], "right normal force")
        if left < 0 or right < 0:
            raise GroundTruthError("negative normal contact force")
        for side, n in (("left", left), ("right", right)):
            count = foot[side]["pair_count"]
            if (type(count) is not int or count < 0
                    or (n > 0 and count == 0)):
                raise GroundTruthError("force without original foot contact")
            loads[side].append(n)
            sites[side].append(row["foot_sites_solver_cache_xyz_m"][side])
        l, r = left > LOADED_N, right > LOADED_N
        classes["both" if l and r else "left_only" if l else
                "right_only" if r else "neither"] += 1
        if left + right > 0:
            shares.append(left / (left + right))
    support_codes = [
        "both" if l > LOADED_N and r > LOADED_N else
        "left" if l > LOADED_N else "right" if r > LOADED_N else "neither"
        for l, r in zip(loads["left"], loads["right"])
    ]
    switches = sum((a == "left" and b == "right") or
                   (a == "right" and b == "left")
                   for a, b in zip(support_codes, support_codes[1:]))
    sides_ever_unilateral = (classes["left_only"] > 0 and classes["right_only"] > 0)
    first = middle[0]["trunk_xyz_after_integration_m"]
    last = middle[-1]["trunk_xyz_after_integration_m"]
    dx, dy = last[0]-first[0], last[1]-first[1]
    observed = math.hypot(dx, dy)
    reference = _number(report.get("net_xy_displacement_m"), "ground-truth translation")
    if abs(observed - reference) > MAX_SOLVER_POSE_DELTA_M:
        raise GroundTruthError("independent solver displacement disagrees with E2G")
    capture_us = sorted(_number(f["capture_us"], "tap capture duration") for f in middle)
    p95 = capture_us[math.ceil(.95*len(capture_us))-1]
    return {
        "experiment": "SIM-E2H_original_solver_support_during_one_E2G_bracket",
        "source": "pinned_oem_original_live_mj_step_50hz_sample",
        "source_trace_sha256": sha256(trace_path.read_bytes()).hexdigest(),
        "source_e2g_sha256": sha256(report_path.read_bytes()).hexdigest(),
        "complete_original_solver_stream": True,
        "alignment": "MuJoCo simulator-clock bracket, not per-command synchronization",
        "frames_in_bracket": len(middle),
        "bracket_sim_duration_s": middle[-1]["sim_time_s"]-middle[0]["sim_time_s"],
        "support_threshold_n": LOADED_N,
        "loaded_contact_samples": classes,
        "both_feet_were_unilaterally_loaded_at_different_samples": sides_ever_unilateral,
        "direct_left_right_single_support_switches": switches,
        "left_normal_min_max_n": [min(loads["left"]), max(loads["left"])],
        "right_normal_min_max_n": [min(loads["right"]), max(loads["right"])],
        "left_share_of_contact_force_min_max": (
            [min(shares), max(shares)] if shares else None
        ),
        "trunk_solver_net_xy_m": observed,
        "trunk_e2g_reported_net_xy_m": reference,
        "solver_minus_e2g_distance_m": observed-reference,
        "tap_capture_p95_us": p95,
        "tap_capture_max_us": max(capture_us),
        "observer_cost_confounded": p95 > MAX_TAP_P95_US,
        "gait_validated": False,
        "foot_slip_verified": False,
        "ground_friction_or_traction_direction_verified": False,
        "robot_hardware_validated": False,
        "causal_low_speed_threshold_proven": False,
        "interpretation": (
            "contact_load_transfer_observed_not_stable_gait"
            if sides_ever_unilateral else
            "no_independent_unilateral_load_transfer_evidence"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--e2g", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        state = args.e2g.parent.resolve(strict=True)
        if any(p.parent.resolve(strict=True) != state
               for p in (args.trace, args.output)):
            raise GroundTruthError("diagnostics outside isolated simulator state")
        if (args.trace.name != "solver-tap.jsonl"
                or args.e2g.name != "sim-e2g-report.json"
                or args.output.name != "sim-e2h-contact-report.json"
                or args.output.is_symlink() or args.output.exists()):
            raise GroundTruthError("unapproved or existing E2H output")
        result = summarize_support(args.trace, args.e2g)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True,
                                          allow_nan=False)+"\n", encoding="utf-8")
        print(json.dumps({
            "interpretation": result["interpretation"],
            "sample_count": result["frames_in_bracket"],
            "loaded_contact_samples": result["loaded_contact_samples"],
            "trunk_solver_net_xy_mm": round(1000*result["trunk_solver_net_xy_m"], 3),
            "tap_capture_p95_us": round(result["tap_capture_p95_us"], 2),
            "gait_validated": False,
        }, sort_keys=True))
        return 0
    except (GroundTruthError, OSError, ValueError, TypeError, KeyError) as exc:
        print("SIM-E2H refused incomplete contact data: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
