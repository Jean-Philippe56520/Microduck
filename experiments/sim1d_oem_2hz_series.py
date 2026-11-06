"""SIM-1D/A: actual OEM mediad -> host YOLOX -> mock F2, at fixed 2 Hz.

Host diagnostic ONLY. This runner has no motor RPC, separate camera/model,
semantic GT, memory writer, source authentication or persisted media. World
contents come from a separate pinned OEM XML, NOT from camera pixels.
See docs/sim-1d-2hz-oem-paired-preregister-2026-11-06.md.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import time

from microduck_companion.sim_bridge import read_simulator_telemetry
from microduck_companion.sim_media_frame import (
    MediaFrameError, acquire_simulated_oem_frame,
)
from microduck_companion.sim_vis_oem_cycle import (
    _open_pinned_model, evaluate_simulated_camera_cycle,
)

CYCLES = 10
PERIOD_S = 0.5
MAX_START_LATE_S = 0.125
MIN_CAPTURE_INTERVAL_S = 0.35
MAX_CAPTURE_INTERVAL_S = 0.70
MIN_MEDIAN_INTERVAL_S = 0.40
MAX_MEDIAN_INTERVAL_S = 0.60
SUCCESS = "PASS_2HZ_OEM_READONLY_MOCK_F2"
ACCEPTED_F2 = frozenset({"idle", "inspect"})
WORLDS = {"ball": True, "empty": False}


def _summary(numbers: list[float]) -> dict | None:
    if not numbers:
        return None
    values = sorted(numbers)
    return {
        "min": round(values[0], 4),
        "median": round(statistics.median(values), 4),
        "p95_nearest_rank": round(values[min(
            len(values) - 1, math.ceil(0.95 * len(values)) - 1,
        )], 4),
        "max": round(values[-1], 4),
    }


def run_series(
    state_dir: Path, session, *, world_case: str,
    clock=time.monotonic, pause=time.sleep,
    observe=read_simulator_telemetry,
    acquire=acquire_simulated_oem_frame,
    evaluate=evaluate_simulated_camera_cycle,
    count: int = CYCLES,
) -> dict:
    """Measure a bounded series; failed frames never become a valid denominator.

    Injectable clock/readers exist for OFFLINE negative tests only. The CLI
    always uses the actual OEM readers, real monotonic clock, and fixed 10.
    """
    if world_case not in WORLDS or type(count) is not int or not 2 <= count <= CYCLES:
        raise ValueError("invalid preregistered world or fixture count")
    if not isinstance(state_dir, Path) or not state_dir.is_absolute():
        raise ValueError("state dir must be absolute")
    samples: list[dict] = []
    error = None
    started = clock()
    previous_stamp = None
    for i in range(count):
        due = started + i * PERIOD_S
        delay = due - clock()
        if delay > 0:
            pause(delay)
        cycle_start = clock()
        lag_s = max(0.0, cycle_start - due)
        if not math.isfinite(lag_s) or lag_s > MAX_START_LATE_S:
            error = {"status": "STOP_CADENCE_SLIP", "cycle": i,
                     "start_delay_s": round(lag_s, 4)}
            break
        try:
            telemetry = observe(state_dir, timeout_s=0.75, hz=10)
            quality = telemetry.assess(now=clock(), max_age_s=1.5).status
            if quality != "coherent":
                error = {"status": "STOP_TELEMETRY_UNSAFE_OR_MISSING",
                         "cycle": i, "quality": quality}
                break
            frame = acquire(state_dir / "duck-a-frame.sock",
                            timeout_s=0.85, max_age_s=1.2)
            stamp = frame.captured_at_unix_us
            if type(stamp) is not int or (
                    previous_stamp is not None and stamp <= previous_stamp):
                error = {"status": "STOP_DUPLICATE_OR_REVERSED_FRAME",
                         "cycle": i}
                break
            trace = evaluate(
                frame, telemetry, session, now_monotonic_s=clock(),
            )
            if trace.get("status") != "HOST_UNVERIFIED_CAMERA_FRAME_TO_MOCK_F2":
                error = {"status": "STOP_F2_OR_OEM_GATE", "cycle": i,
                         "source_status": trace.get("status", "unknown"),
                         "quality": trace.get("telemetry_quality", "unknown")}
                break
            f2 = trace["f2_mock_projection"]
            if (trace.get("motor_commands_issued") != 0
                    or trace.get("sensor_source_authenticated") is not False
                    or trace.get("semantic_category_verified") is not False
                    or trace.get("same_mujoco_step_verified") is not False
                    or trace.get("media_written_to_disk") is not False
                    or trace.get("memory_effect_verified") is not False
                    or f2["motor_commands_issued"] != 0
                    or f2["experience_writes"] != 0
                    or f2["sensor_source_authenticated"] is not False
                    or f2["known_category_promoted"] is not False
                    or f2["intention"] not in ACCEPTED_F2
                    or f2["target_category"] not in (None, "unknown")):
                error = {"status": "STOP_UNSUPPORTED_F2_AUTHORITY",
                         "cycle": i}
                break
            regions = trace["regions_untrusted"]
            if type(regions) is not list or len(regions) > 3:
                error = {"status": "STOP_INVALID_REGION_COUNT", "cycle": i}
                break
            best = max((r["score"] for r in regions), default=None)
            if best is not None and (
                    type(best) is not float or not math.isfinite(best)):
                error = {"status": "STOP_INVALID_REGION_SCORE", "cycle": i}
                break
            samples.append({
                "cycle": i, "capture_us": stamp,
                "start_slip_s": round(lag_s, 4),
                "cycle_elapsed_s": round(clock() - cycle_start, 4),
                "capture_age_s_at_decision": trace["capture_age_s_at_decision"],
                "inference_ms_cpu_host": trace["inference_ms_cpu_host"],
                "telemetry_quality": trace["telemetry_quality"],
                "regions_untrusted_count": len(regions),
                "max_untrusted_score": best,
                "f2_intention": f2["intention"],
                "f2_reason": f2["reason"],
                "motor_commands_issued": 0,
                "experience_writes": 0,
            })
            previous_stamp = stamp
        except (MediaFrameError, ValueError, OSError, ImportError,
                RuntimeError, TypeError, KeyError, IndexError) as exc:
            error = {"status": "STOP_OEM_READER_OR_MODEL", "cycle": i,
                     "error_type": type(exc).__name__, "detail": str(exc)[:150]}
            break
    capture_intervals = [
        (b["capture_us"] - a["capture_us"]) / 1_000_000
        for a, b in zip(samples, samples[1:])
    ]
    count_ok = len(samples) == count and error is None
    schedule_ok = (
        count_ok and len(capture_intervals) == count - 1
        and all(MIN_CAPTURE_INTERVAL_S <= interval <= MAX_CAPTURE_INTERVAL_S
                for interval in capture_intervals)
        and MIN_MEDIAN_INTERVAL_S <= statistics.median(
            capture_intervals) <= MAX_MEDIAN_INTERVAL_S
    )
    report = {
        "status": SUCCESS if schedule_ok else (
            error["status"] if error else "FAIL_2HZ_CAPTURE_CADENCE"
        ),
        "world_case": world_case,
        "world_contains_ball_xml": WORLDS[world_case],
        "world_truth_source": "pinned_oem_scene_xml_not_frame_gt",
        "frame_ball_visibility_known": False,
        "pixel_gt_synchronised": False,
        "scene_xml_changed": False,
        "requested_visual_hz": 2.0,
        "visual_period_s": PERIOD_S,
        "requested_cycles": count,
        "completed_cycles": len(samples),
        "unique_frame_timestamps": len({
            row["capture_us"] for row in samples
        }),
        "on_time_samples": len([
            row for row in samples
            if row["start_slip_s"] <= MAX_START_LATE_S
        ]),
        "camera_interval_s": _summary(capture_intervals),
        "capture_interval_criteria_met": bool(schedule_ok),
        "total_cycle_duration_s": _summary([
            row["cycle_elapsed_s"] for row in samples
        ]),
        "inference_ms_cpu_host": _summary([
            row["inference_ms_cpu_host"] for row in samples
        ]),
        "capture_age_s": _summary([
            row["capture_age_s_at_decision"] for row in samples
        ]),
        "f2_idle_count": sum(row["f2_intention"] == "idle" for row in samples),
        "f2_inspect_unknown_count": sum(
            row["f2_intention"] == "inspect" for row in samples
        ),
        "semantic_category_verified": False,
        "same_mujoco_step_verified": False,
        "source_authenticated": False,
        "memory_effect_verified": False,
        "motor_commands_issued": 0,
        "experience_writes": 0,
        "image_written": False,
        "physical_robot_verified": False,
        "gt_eligible_for_detection_accuracy": False,
        "error": error,
        "samples": samples,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OEM MuJoCo 10 camera->YOLOX->mock F2 cycles at 2Hz; NO motors"
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--world-case", choices=tuple(WORLDS), required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="Only JSON metadata, no frames, binary or memory")
    args = parser.parse_args(argv)
    result = None
    try:
        model = _open_pinned_model(args.model)
        result = run_series(
            args.state_dir.resolve(), model, world_case=args.world_case
        )
    except (ValueError, MediaFrameError, RuntimeError, ImportError,
            OSError) as exc:
        result = {
            "status": "STOP_NO_MODEL_OR_STARTUP",
            "detail": str(exc)[:150],
            "requested_cycles": CYCLES, "completed_cycles": 0,
            "motor_commands_issued": 0, "experience_writes": 0,
            "image_written": False,
        }
    # Store only numerical/text observations. Never store raw frames.
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n", encoding="utf-8",
    )
    print(json.dumps({
        k: v for k, v in result.items() if k != "samples"
    }, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == SUCCESS else 1


if __name__ == "__main__":
    raise SystemExit(main())
