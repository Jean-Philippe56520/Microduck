"""B2: eight bounded live mediad captures with OPTIONAL MuJoCo sidecar truth.

Only an instrumented CI simulator produces the GT; production F2/robotd never
sees it. The OCR/semantic class of YOLOX regions is NOT promoted.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import time

from experiments.sim1db2_frame_match import B2GTError, match_frame, read_sidecar
from experiments.sim1d_launch_context import verify_launch_context
from microduck_companion.sim_media_frame import acquire_simulated_oem_frame
from microduck_companion.sim_vis_oem_cycle import (
    _open_pinned_model, uyvy_to_upright_jpeg,
)
from microduck_companion.cata_yolox_categories import prepare_image
from microduck_companion.yolox_attention_candidates import _iou, decode_candidates
from microduck_companion.sim_bridge import read_simulator_telemetry

COUNT = 4
PERIOD = 0.5
MIN_CAPTURE = 0.35
MAX_CAPTURE = 0.70
MIN_MEDIAN = 0.40
MAX_MEDIAN = 0.60
MAX_START_LAG = 0.125
MAX_P95_RENDER_MS = 40.0
SUCCESS = "PASS_B2_INSTRUMENTED_EXACT_FRAME_GT_HOST_ONLY"


def _p95(numbers):
    ordered = sorted(numbers)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def run(state: Path, sidecar: Path, arm: Path, model: Path, *,
        case: str) -> dict:
    if (case not in ("ball", "empty") or not state.is_absolute()
            or not sidecar.is_absolute() or not arm.is_absolute()
            or sidecar.exists() or arm.exists()):
        raise B2GTError("invalid or re-used B2 trial paths")
    # Prove the OFFICIAL launcher and the actual scene before instrumentation.
    context = verify_launch_context(state, case)
    if context["initial_keyframe"] != "HOME":
        raise B2GTError("B2 requires HOME launch")
    session = _open_pinned_model(model)
    samples = []
    recorded = []
    # Only activate the double-render camera after the stock daemons have booted.
    # The OEM FrameServer may still hold a pre-arm latest frame, so do NOT
    # start the four measured requests until a new instrumented render exists.
    arm.open("x").close()
    try:
        deadline = time.monotonic() + 1.0
        while not sidecar.exists() and time.monotonic() < deadline:
            time.sleep(0.025)
        if not sidecar.exists():
            raise B2GTError("STOP_B2_INSTRUMENTED_RENDER_NOT_STARTED")
        if not read_sidecar(sidecar, case=case):
            raise B2GTError("STOP_B2_NO_COMPLETE_RENDER")
        start = time.monotonic()
        for i in range(COUNT):
            due = start + i * PERIOD
            time.sleep(max(0.0, due - time.monotonic()))
            tick = time.monotonic()
            if tick - due > MAX_START_LAG:
                raise B2GTError("STOP_B2_START_CADENCE")
            telemetry = read_simulator_telemetry(state, timeout_s=0.75, hz=10)
            if telemetry.assess(now=time.monotonic(), max_age_s=1.5).status != "coherent":
                raise B2GTError("STOP_B2_TELEMETRY_UNHEALTHY")
            frame = acquire_simulated_oem_frame(
                state / "duck-a-frame.sock", timeout_s=0.85, max_age_s=1.2)
            if (frame.width, frame.height, frame.rotate) != (640, 360, 90):
                raise B2GTError("STOP_B2_MEDIAD_GEOMETRY")
            if samples and frame.captured_at_unix_us <= samples[-1]["captured_us"]:
                raise B2GTError("STOP_B2_REPEATED_MEDIAD_TIMESTAMP")
            rows = read_sidecar(sidecar, case=case)
            matched = match_frame(rows, frame.pixels_uyvy, case=case)
            if (case == "ball" and matched["ball_visible_pixels"] < 80
                    or case == "empty" and (matched["ball_visible_pixels"] != 0
                                             or matched["ball_geom_id"] is not None)):
                raise B2GTError("STOP_B2_VISIBLE_GT_WITNESS")
            # The detector receives ONLY pixels. This spatial IoU is computed
            # AFTER detection, for independent offline diagnostics, NOT F2.
            image, width, height = uyvy_to_upright_jpeg(frame)
            if (width, height) != (360, 640):
                raise B2GTError("STOP_B2_UPRIGHT_GEOMETRY")
            sample = prepare_image(image, mode="original")
            raw = session.run(None, {"images": sample})[0]
            proposals = decode_candidates(raw, width=width, height=height,
                                          max_results=3)
            gt_bbox = matched["ball_bbox_upright_xyxy"]
            best_iou = (max((_iou(tuple(gt_bbox), p["xyxy"])
                             for p in proposals), default=0.)
                        if gt_bbox is not None else None)
            samples.append({
                "cycle": i, "captured_us": frame.captured_at_unix_us,
                "render_seq": matched["render_seq"],
                "sim_time_s": matched["sim_time_s"],
                "ball_visible_pixels": matched["ball_visible_pixels"],
                "ball_bbox_upright_xyxy": gt_bbox,
                "regions_unverified": len(proposals),
                "best_region_ball_gt_iou": (round(best_iou, 6)
                                             if best_iou is not None else None),
                "render_ms": matched["render_ms"],
                "cycle_elapsed_ms": round((time.monotonic() - tick) * 1000, 3),
            })
    finally:
        arm.unlink(missing_ok=True)
    context_stable = verify_launch_context(state, case) == context
    if not context_stable:
        raise B2GTError("STOP_B2_LAUNCH_CONTEXT_CHANGED")
    # No active writer now: the next OEM frame reverts to the original render.
    # Capture the last published batch of instrumented metadata.
    recorded = read_sidecar(sidecar, case=case)
    latencies = [r["render_ms"] for r in recorded]
    if not latencies:
        raise B2GTError("STOP_B2_NO_RENDER_MEASURES")
    p95 = _p95(latencies)
    stamps = [s["captured_us"] for s in samples]
    periods = [(b - a) / 1_000_000 for a, b in zip(stamps, stamps[1:])]
    cadence = (len(samples) == COUNT and len(periods) == COUNT - 1
               and all(MIN_CAPTURE <= dt <= MAX_CAPTURE for dt in periods)
               and MIN_MEDIAN <= statistics.median(periods) <= MAX_MEDIAN)
    if not cadence or p95 > MAX_P95_RENDER_MS:
        raise B2GTError("STOP_B2_CADENCE_OR_RENDER_BUDGET")
    return {
        "status": SUCCESS, "case": case,
        "provenance": "EXPLICIT_TEMPORARY_INSTRUMENTED_MUJOCO_NOT_OEM_INTACT",
        "completed_cycles": COUNT, "camera_period_median_s": round(statistics.median(periods), 4),
        "gt_exact_frame_matches": COUNT, "visible_witness": case == "ball",
        "render_p95_ms": round(p95, 3), "all_sidecar_rows": len(recorded),
        "samples": samples,
        "pixel_gt_injected_into_f2": False,
        "semantic_category_verified": False, "robot_validated": False,
        "motor_commands_companion": 0, "experience_writes": 0,
        "image_persisted": False, "oem_gitlinks_changed": False,
    }


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("state", "sidecar", "arm", "model", "output"):
        cli.add_argument("--" + name, type=Path, required=True)
    cli.add_argument("--case", choices=("ball", "empty"), required=True)
    args = cli.parse_args(argv)
    try:
        outcome = run(args.state, args.sidecar, args.arm, args.model, case=args.case)
    except (B2GTError, ValueError, RuntimeError, OSError, ImportError,
            KeyError, IndexError, TypeError) as exc:
        # Keep only error TYPE and a stable STOP code; no pixels/path/trace dumps.
        print(json.dumps({
            "status": "STOP_B2_FRAME_GT_NOT_PROVEN",
            "reason_type": type(exc).__name__, "reason": str(exc)[:160],
            "gt_exact_frame_matches_accepted": 0,
            "semantic_category_verified": False,
            "motor_commands_companion": 0, "experience_writes": 0,
        }), file=sys.stderr)
        return 1
    output = json.dumps(outcome, indent=2, allow_nan=False) + "\n"
    args.output.write_text(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
