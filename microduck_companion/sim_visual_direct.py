"""SIM-VIS-A1b: one raw official MuJoCo head-camera frame -> existing Cat-A YOLOX.

Read-only optical diagnostic *before* mediad: uses the manufacturer's
microduck_rl FrameServer protocol (4-byte LE length + UYVY), on loopback.
It does NOT validate mediad/media.frame, real-time physics, robot hardware,
ToF, scene-ball visibility or detection accuracy. No raw image is persisted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import socket
import struct
import sys
import time

from .sim_visual_a1 import (
    FRAME_HEIGHT, FRAME_WIDTH, VisualProbeError,
    jpeg_for_existing_yolox, scene_ball_inventory,
)
from .cata_yolox_categories import (
    MODEL_SHA256, MIN_SCORE, SIZE, prepare_image, validate_model_file,
)
from .cata2_bbox_eval import decode_boxes

MAX_CAMERA_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2
DEFAULT_PORT = 17901
SOCKET_TIMEOUT_S = 12.0


def _read_exact(connection: socket.socket, length: int) -> bytes:
    if type(length) is not int or not 1 <= length <= MAX_CAMERA_BYTES:
        raise VisualProbeError("invalid bounded frame length")
    data = bytearray()
    while len(data) < length:
        try:
            chunk = connection.recv(min(65536, length - len(data)))
        except (OSError, socket.timeout) as exc:
            raise VisualProbeError("simulator camera read timed out") from exc
        if not chunk:
            raise VisualProbeError("truncated simulator camera payload")
        data.extend(chunk)
    return bytes(data)


def read_official_rendered_frame(*, port: int) -> bytes:
    """Read one frame from the OEM RL server, never send any command."""
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("invalid local simulator camera port")
    try:
        with socket.create_connection(("127.0.0.1", port),
                                      timeout=SOCKET_TIMEOUT_S) as connection:
            connection.settimeout(SOCKET_TIMEOUT_S)
            header = _read_exact(connection, 4)
            length = struct.unpack("<I", header)[0]
            if length != MAX_CAMERA_BYTES:
                raise VisualProbeError("wrong length from OEM RL camera server")
            return _read_exact(connection, length)
    except (OSError, TimeoutError) as exc:
        raise VisualProbeError("official loopback camera source unavailable") from exc


def evaluate_render_only(*, camera_port: int, model_path: Path,
                         scene_path: Path) -> dict:
    """One real MuJoCo rendered image; no OEM mediad or physical validation."""
    n_balls = scene_ball_inventory(scene_path)
    validate_model_file(model_path)
    raw = read_official_rendered_frame(port=camera_port)
    jpeg, width, height, contrast = jpeg_for_existing_yolox(
        raw, width=FRAME_WIDTH, height=FRAME_HEIGHT, rotate=90
    )
    # Digest can identify a simulator frame in logs; it is not visual ground truth.
    frame_digest = hashlib.sha256(raw).hexdigest()

    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=opts, providers=["CPUExecutionProvider"]
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise VisualProbeError("unreviewed existing Cat-A ONNX interface")
    tensor = prepare_image(jpeg, mode="original")
    start = time.perf_counter()
    raw_predictions = session.run(None, {"images": tensor})[0]
    ms = round((time.perf_counter() - start) * 1000, 3)
    proposals = decode_boxes(raw_predictions, width=width, height=height)
    return {
        "lot": "SIM-VIS-A1b_direct_render_only",
        "status": "rendered_image_processed_no_pixel_ground_truth",
        "image_source": "pinned_microduck_rl_FrameServer_tcp_uyvy",
        "source_authenticated": False,
        "official_mediad_path_tested": False,
        "real_time_physics_validated": False,
        "simulated_robotd_tofd_tested_here": False,
        "frame_uyvy_size": [FRAME_WIDTH, FRAME_HEIGHT],
        "image_after_oem_90_degree_mount": [width, height],
        "frame_sha256": frame_digest,
        "frame_rgb_std": contrast,
        "frame_bytes": len(raw),
        "frame_has_capture_timestamp": False,
        "inference_model_sha256": MODEL_SHA256,
        "inference_score_fixed": MIN_SCORE,
        "inference_host_ms": ms,
        "proposed_boxes": len(proposals),
        "proposed_categories": dict(sorted(Counter(
            box.category for box in proposals).items())),
        "scene_world_balls": n_balls,
        "balls_visible_ground_truth": None,
        "precision_recall_ap50": None,
        "actual_robot_camera_tested": False,
        "motor_commands_sent": 0,
        "qwen_calls": 0,
        "sqlite_writes": 0,
        "raw_image_saved_or_uploaded": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--scene-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-sim-render-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_sim_render_only:
        parser.error("explicit opt-in for synthetic MuJoCo camera required")
    try:
        result = evaluate_render_only(
            camera_port=args.camera_port, model_path=args.model_path,
            scene_path=args.scene_path
        )
        if args.output.is_symlink() or args.output.exists():
            raise VisualProbeError("do not overwrite a prior observation")
        args.output.write_text(
            json.dumps(result, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (VisualProbeError, RuntimeError, ValueError, OSError) as exc:
        print(f"SIM-VIS-A1b inconclusive: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
