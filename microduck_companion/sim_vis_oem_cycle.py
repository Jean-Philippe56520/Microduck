"""SIM-1B: one real OEM mediad simulator frame -> host YOLOX -> MOCK F2.

No motor RPC, no independent camera, no model training and no persisted media.
The temporal telemetry gate is conservative but does not prove a common MuJoCo
step. YOLOX regions stay untrusted; F2's existing mock-only boundary is NOT
promoted to a sensor. This is a diagnostic host run, not robot autonomy.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import sys
import time

from .cata_yolox_categories import (
    MODEL_SHA256, SIZE, prepare_image, validate_model_file,
)
from .sim_bridge import SimulatorTelemetry, read_simulator_telemetry
from .sim_media_frame import (
    EphemeralMediaFrame, MediaFrameError, acquire_simulated_oem_frame,
)
from .sim_vis_d_new_scenes_f2_fixture import mock_f2_from_regions
from .yolox_attention_candidates import decode_candidates


def uyvy_to_upright_jpeg(frame: EphemeralMediaFrame) -> tuple[bytes, int, int]:
    """Decode OEM packed UYVY with BT.601 limited-range colour; rotate to upright.

    This is an ephemeral preprocessing copy for the PREEXISTING YOLOX JPEG
    input, not a second camera or a media recorder. Mount rotation follows
    the pinned OEM's reported clockwise number (also used in SIM-VIS-D).
    """
    import numpy as np
    from PIL import Image

    if type(frame) is not EphemeralMediaFrame:
        raise MediaFrameError("expected ephemeral mediad frame")
    w, h = frame.width, frame.height
    if (type(w) is not int or type(h) is not int
            or not 32 <= w <= 4096 or w % 2
            or not 32 <= h <= 4096 or frame.rotate not in (0, 90, 180, 270)
            or type(frame.pixels_uyvy) is not bytes
            or len(frame.pixels_uyvy) != 2 * w * h
            or 2 * w * h > 16 * 1024 * 1024):
        raise MediaFrameError("unusable UYVY frame")
    if (type(frame.captured_at_unix_us) is not int
            or not 0 <= time.time() - frame.captured_at_unix_us / 1_000_000 <= 2):
        raise MediaFrameError("capture not fresh for cognitive cycle")
    # Each UYVY macro-pixel holds U,Y0,V,Y1. Do not confuse it with YUYV.
    pair = np.frombuffer(frame.pixels_uyvy, dtype=np.uint8).reshape(
        (h, w // 2, 4)).astype(np.float32)
    y = np.empty((h, w), dtype=np.float32)
    y[:, 0::2], y[:, 1::2] = pair[:, :, 1], pair[:, :, 3]
    u = np.repeat(pair[:, :, 0], 2, axis=1) - 128.0
    v = np.repeat(pair[:, :, 2], 2, axis=1) - 128.0
    luma = 1.164383 * (y - 16.0)
    rgb = np.stack((
        luma + 1.596027 * v,
        luma - 0.391762 * u - 0.812968 * v,
        luma + 2.017232 * u,
    ), axis=-1)
    image = Image.fromarray(np.clip(np.rint(rgb), 0, 255).astype(np.uint8))
    if frame.rotate:
        image = image.rotate(-frame.rotate, expand=True)
    output = BytesIO()
    image.save(output, format="JPEG", quality=95)
    return output.getvalue(), image.width, image.height


def evaluate_simulated_camera_cycle(
    frame: EphemeralMediaFrame, telemetry: SimulatorTelemetry, session,
    *, now_monotonic_s: float,
) -> dict:
    """Gate image inference on real read-only OEM telemetry and return one trace.

    The two OEM sockets are sampled sequentially, never asserted to be the
    same simulation step. F2 is deliberately supplied with a synthetic mock
    projection of UNTRUSTED scores; the OEM pixels are not a trusted semantic
    sensor. No image, GT, model category, memory claim or motor authorization
    crosses that boundary.
    """
    if type(telemetry) is not SimulatorTelemetry:
        raise TypeError("only parsed simulator telemetry is accepted")
    assessment = telemetry.assess(now=now_monotonic_s, max_age_s=2.0)
    if assessment.status != "coherent":
        return {
            "status": "STOP_UNSAFE_OR_INCOMPLETE_TELEMETRY",
            "telemetry_quality": assessment.status,
            "intention": "idle",
            "reason": "no_visual_decision_without_coherent_oem_telemetry",
            "inference_attempted": False,
            "motor_commands_issued": 0,
            "memory_writes": 0,
        }

    jpeg, width, height = uyvy_to_upright_jpeg(frame)
    tensor = prepare_image(jpeg, mode="original")
    started = time.perf_counter()
    raw = session.run(None, {"images": tensor})[0]
    infer_ms = round((time.perf_counter() - started) * 1000, 3)
    regions = decode_candidates(raw, width=width, height=height, max_results=3)
    # Map capture wall-clock to local monotonic time conservatively. This
    # does NOT establish shared simulator timestamps or synchronize sockets.
    decision_now = time.monotonic()
    age_at_decision_s = time.time() - frame.captured_at_unix_us / 1_000_000
    if not 0 <= age_at_decision_s <= 2.0:
        raise MediaFrameError("frame expired or clock shifted during inference")
    last_quality = telemetry.assess(now=decision_now, max_age_s=2.0).status
    if last_quality != "coherent":
        return {
            "status": "STOP_UNSAFE_OR_INCOMPLETE_TELEMETRY",
            "telemetry_quality": last_quality,
            "intention": "idle",
            "reason": "telemetry_expired_during_inference",
            "inference_attempted": True,
            "motor_commands_issued": 0,
            "memory_writes": 0,
        }
    sample_at = decision_now - age_at_decision_s
    if sample_at < 0:
        raise MediaFrameError("wall-to-monotonic capture estimate unusable")
    # This existing F2 helper enforces all 'mock' flags, opens exactly one
    # ephemeral ExperienceMemory, and rejects invented semantic labels.
    f2 = mock_f2_from_regions(
        regions, sample_at=sample_at, now=decision_now, claimed_source="mock",
    )
    if (f2["motor_commands_issued"] != 0 or f2["experience_writes"] != 0
            or f2["sensor_source_authenticated"]
            or f2["known_category_promoted"]):
        raise MediaFrameError("mock F2 result claimed unsupported authority")
    return {
        "status": "HOST_SIM_MEDIAD_PIXELS_TO_MOCK_F2",
        "telemetry_quality": assessment.status,
        "telemetry_claim": assessment.source,
        "frame_claim": frame.evidence["source_claim"],
        "camera_width_upright": width,
        "camera_height_upright": height,
        "captured_at_unix_us": frame.captured_at_unix_us,
        "capture_age_s_at_decision": round(age_at_decision_s, 3),
        "model_sha256": MODEL_SHA256,
        "inference_ms_cpu_host": infer_ms,
        "regions_untrusted": regions,
        "f2_mock_projection": f2,
        "temporal_alignment_verified": False,
        "same_mujoco_step_verified": False,
        "semantic_category_verified": False,
        "sensor_source_authenticated": False,
        "physical_robot_verified": False,
        "memory_effect_verified": False,
        "motor_commands_issued": 0,
        "media_written_to_disk": False,
    }


def _open_pinned_model(path: Path):
    import onnxruntime as ort

    validate_model_file(path)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(path), sess_options=opts, providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1
            or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise ValueError("unreviewed YOLOX ONNX contract")
    return session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One OEM MuJoCo frame -> YOLOX CPU -> mock F2 trace; NO motors"
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True,
                        help="SHA-pinned 416px YOLOX-Nano ONNX file on PC")
    args = parser.parse_args(argv)

    try:
        # Refuse missing/mismatched weights BEFORE touching a simulated camera.
        session = _open_pinned_model(args.model)
        telemetry = read_simulator_telemetry(args.state_dir, timeout_s=1.2)
        frame = acquire_simulated_oem_frame(
            args.state_dir.resolve() / "duck-a-frame.sock", timeout_s=1.2,
        )
        trace = evaluate_simulated_camera_cycle(
            frame, telemetry, session, now_monotonic_s=time.monotonic(),
        )
    except (MediaFrameError, ValueError, OSError, ImportError,
            IndexError, RuntimeError) as exc:
        print(json.dumps({"status": "STOP_NO_VISUAL_DECISION",
                          "detail": str(exc),
                          "motor_commands_issued": 0}), file=sys.stderr)
        return 1
    print(json.dumps(trace, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if trace["status"] == "HOST_SIM_MEDIAD_PIXELS_TO_MOCK_F2" else 1


if __name__ == "__main__":
    raise SystemExit(main())
