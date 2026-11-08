"""SIM-1D/B2-E1: four mediad frames at 2 Hz, with pose SHA only.

Runs while the single OEM simulator camera / robotd are active. Ground truth
must be reconstructed offline AFTER duck-sim down. No motor or SQLite API.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import time

from experiments.sim1d_launch_context import verify_launch_context
from experiments.sim1db2e1_frame_match import B2GTError, match_frame, read_sidecar
from microduck_companion.sim_bridge import read_simulator_telemetry
from microduck_companion.sim_media_frame import acquire_simulated_oem_frame
from microduck_companion.sim_vis_oem_cycle import (
    _open_pinned_model, uyvy_to_upright_jpeg,
)
from microduck_companion.cata_yolox_categories import prepare_image
from microduck_companion.yolox_attention_candidates import decode_candidates

COUNT = 4
PERIOD_S = 0.5
MAX_START_LAG_S = 0.125
SUCCESS = "PASS_E1_MEDIAD_EXACT_POSE_CAPTURE_ONLY"


def _p95(values):
    s = sorted(values)
    return s[math.ceil(0.95 * len(s)) - 1]


def collect(state: Path, sidecar: Path, arm: Path, model: Path, *, case: str) -> dict:
    if (case not in ("ball", "empty") or not state.is_absolute()
            or not sidecar.is_absolute() or not arm.is_absolute()
            or sidecar.exists() or arm.exists()):
        raise B2GTError("STOP_E1_INVALID_START_OR_REUSE")
    context = verify_launch_context(state, case)
    if context["initial_keyframe"] != "HOME":
        raise B2GTError("STOP_E1_NOT_HOME")
    session = _open_pinned_model(model)
    samples = []
    arm.open("x").close()
    try:
        deadline = time.monotonic() + 1.5
        while not sidecar.exists() and time.monotonic() < deadline:
            time.sleep(0.025)
        if not sidecar.exists() or not read_sidecar(sidecar, case=case):
            raise B2GTError("STOP_E1_NO_INSTRUMENTED_RENDER")
        start = time.monotonic()
        for i in range(COUNT):
            due = start + i * PERIOD_S
            time.sleep(max(0., due - time.monotonic()))
            tick = time.monotonic()
            if tick - due > MAX_START_LAG_S:
                raise B2GTError("STOP_E1_LATE_CYCLE_START")
            telemetry = read_simulator_telemetry(state, timeout_s=0.75, hz=10)
            quality = telemetry.assess(now=time.monotonic(), max_age_s=1.5).status
            if quality != "coherent":
                raise B2GTError("STOP_E1_TELEMETRY_" + quality.upper())
            frame = acquire_simulated_oem_frame(
                state / "duck-a-frame.sock", timeout_s=0.85, max_age_s=1.2)
            if (frame.width, frame.height, frame.rotate) != (640, 360, 90):
                raise B2GTError("STOP_E1_MEDIAD_GEOMETRY")
            if samples and frame.captured_at_unix_us <= samples[-1]["captured_us"]:
                raise B2GTError("STOP_E1_BAD_CAPTURE_SEQUENCE")
            row = match_frame(read_sidecar(sidecar, case=case),
                              frame.pixels_uyvy, case=case)
            if samples and row["render_seq"] <= samples[-1]["render_seq"]:
                raise B2GTError("STOP_E1_NONMONOTONIC_RENDER")
            upright, width, height = uyvy_to_upright_jpeg(frame)
            if (width, height) != (360, 640):
                raise B2GTError("STOP_E1_UPRIGHT_SIZE")
            raw = session.run(None, {"images": prepare_image(
                upright, mode="original")})[0]
            proposals = decode_candidates(raw, width=width, height=height,
                                          max_results=3)
            samples.append({
                "cycle": i,
                "captured_us": frame.captured_at_unix_us,
                "render_seq": row["render_seq"],
                # No mask, category or GT is available to this live collector.
                "pose_sidecar": row,
                "regions_unverified": proposals,
                "capture_age_s": round(
                    time.time() - frame.captured_at_unix_us / 1e6, 4),
                "cycle_elapsed_ms": round((time.monotonic() - tick) * 1000, 3),
            })
    finally:
        arm.unlink(missing_ok=True)
    if verify_launch_context(state, case) != context:
        raise B2GTError("STOP_E1_LAUNCH_CHANGED")
    rows = read_sidecar(sidecar, case=case)
    render_ms = [r["render_ms"] for r in rows]
    if not render_ms:
        raise B2GTError("STOP_E1_RENDER_TIME_ABSENT")
    p95 = _p95(render_ms)
    stamps = [x["captured_us"] for x in samples]
    intervals = [(b-a)/1e6 for a, b in zip(stamps, stamps[1:])]
    if (len(samples) != COUNT or len(intervals) != COUNT - 1
            or any(not 0.35 <= v <= 0.70 for v in intervals)
            or not 0.40 <= statistics.median(intervals) <= 0.60
            or p95 > 40.0):
        raise B2GTError("STOP_E1_CADENCE_OR_RENDER_BUDGET")
    return {
        "status": SUCCESS, "case": case,
        "provenance": "INSTRUMENTED_SINGLE_OEM_RENDER_NOT_REAL_ROBOT",
        "completed_cycles": COUNT,
        "camera_interval_median_s": round(statistics.median(intervals), 4),
        "render_p95_ms": round(p95, 3), "all_sidecar_rows": len(rows),
        "samples": samples,
        "same_step_pixel_gt_verified": False,
        "semantic_category_verified": False,
        "robot_validated": False, "v1_95_percent": False,
        "motor_commands_companion": 0, "experience_writes": 0,
        "image_persisted": False, "oem_gitlinks_changed": False,
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("state", "sidecar", "arm", "model", "output"):
        cli.add_argument("--" + name, type=Path, required=True)
    cli.add_argument("--case", choices=("ball", "empty"), required=True)
    args = cli.parse_args(argv)
    try:
        result = collect(args.state, args.sidecar, args.arm, args.model, case=args.case)
    except (B2GTError, ValueError, RuntimeError, OSError, ImportError,
            TypeError, KeyError, IndexError) as exc:
        print(json.dumps({
            "status": "STOP_E1_LIVE_NOT_QUALIFIED",
            "reason_type": type(exc).__name__,
            "reason": str(exc)[:120],
            "gt_matches": 0, "motor_commands_companion": 0,
            "experience_writes": 0,
        }), file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    args.output.write_text(text)
    print(json.dumps({
        "status": result["status"], "case": args.case,
        "cycles": result["completed_cycles"],
        "render_p95_ms": result["render_p95_ms"],
        "camera_interval_median_s": result["camera_interval_median_s"],
        "gt": "NOT_YET_RECONSTRUCTED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
