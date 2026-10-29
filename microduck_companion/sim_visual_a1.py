"""SIM-VIS-A1: one read-only OEM MuJoCo camera + ToF + YOLOX host probe.

Never asks robotd to move, never forwards scene ground truth to cognition,
never saves or uploads a frame. World inventory is NOT pixel-level ground truth.
This is a bounded operator/CI opt-in, not a daemon or an onboard vision port.
"""
from __future__ import annotations

import argparse
from collections import Counter
from io import BytesIO
import json
from pathlib import Path
import socket
import stat
import sys
import time
import xml.etree.ElementTree as ET

from .oem_frame_preflight import (
    MAX_HEADER_BYTES, FrameContractError, check_mock_frame_tail,
)
from .sim_probe import collect as read_sim_telemetry
from .cata_yolox_categories import (
    MODEL_SHA256, MIN_SCORE, SIZE, prepare_image, validate_model_file,
)
from .cata2_bbox_eval import decode_boxes

FRAME_WIDTH = 640
FRAME_HEIGHT = 360
FRAME_ROTATION = 90
MAX_READ_S = 5.0
WORLD_BALL_NAMES = frozenset({"ball_0", "ball_1", "ball_2"})


class VisualProbeError(RuntimeError):
    """Inconclusive simulation evidence, never a perception success."""


def read_frame(frame_socket: Path) -> tuple[object, bytes]:
    """Use the OEM local media.frame IPC: JSON header followed by exact UYVY."""
    if (not isinstance(frame_socket, Path) or frame_socket.is_symlink()
            or not frame_socket.exists()
            or not stat.S_ISSOCK(frame_socket.stat().st_mode)):
        raise VisualProbeError("official simulator frame socket unavailable")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(MAX_READ_S)
            conn.connect(str(frame_socket))
            conn.sendall(
                b'{"jsonrpc":"2.0","id":1,"method":"media.frame","params":{}}\n'
            )
            header = bytearray()
            while not header.endswith(b"\n"):
                part = conn.recv(1)
                if not part:
                    raise VisualProbeError("truncated OEM frame header")
                header.extend(part)
                if len(header) > MAX_HEADER_BYTES:
                    raise VisualProbeError("oversized OEM frame header")
            # Parsing the header bounds the exact frame allocation before reading.
            from .oem_frame_preflight import parse_mock_frame_header
            now_us = time.time_ns() // 1000
            shape = parse_mock_frame_header(bytes(header), now_unix_us=now_us)
            if (shape.width, shape.height, shape.rotation) != (
                FRAME_WIDTH, FRAME_HEIGHT, FRAME_ROTATION
            ):
                raise VisualProbeError("unexpected pinned simulated camera geometry")
            tail = bytearray()
            while len(tail) < shape.expected_bytes:
                chunk = conn.recv(min(65536, shape.expected_bytes - len(tail)))
                if not chunk:
                    raise VisualProbeError("truncated OEM frame payload")
                tail.extend(chunk)
            checked = check_mock_frame_tail(
                bytes(header), bytes(tail), now_unix_us=time.time_ns() // 1000
            )
            return checked, bytes(tail)
    except (OSError, TimeoutError, FrameContractError) as exc:
        raise VisualProbeError("OEM simulated frame unavailable or invalid") from exc


def jpeg_for_existing_yolox(payload: bytes, *, width: int, height: int,
                            rotate: int) -> tuple[bytes, int, int, float]:
    """Convert UYVY to upright JPEG in memory, without writing pixels to disk.

    This is only a pixel-format bridge to Cat-A's existing JPEG preprocessor.
    The output is not a measurement of the real robot's ISP or camera geometry.
    """
    import numpy as np
    from PIL import Image

    if (type(payload) is not bytes or width != FRAME_WIDTH
            or height != FRAME_HEIGHT or rotate != FRAME_ROTATION
            or len(payload) != width * height * 2):
        raise VisualProbeError("invalid virtual camera pixel geometry")
    pairs = np.frombuffer(payload, dtype=np.uint8).reshape(height, width // 2, 4)
    y = np.empty((height, width), dtype=np.float32)
    y[:, 0::2] = pairs[:, :, 1]
    y[:, 1::2] = pairs[:, :, 3]
    u = np.repeat(pairs[:, :, 0].astype(np.float32) - 128.0, 2, axis=1)
    v = np.repeat(pairs[:, :, 2].astype(np.float32) - 128.0, 2, axis=1)
    rgb = np.stack((y + 1.402 * v,
                    y - 0.344136 * u - 0.714136 * v,
                    y + 1.772 * u), axis=-1)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    contrast = float(np.std(rgb))
    if not np.isfinite(contrast) or contrast < 1.0:
        raise VisualProbeError("simulated camera frame has no usable contrast")
    image = Image.fromarray(rgb, mode="RGB")
    image = image.transpose(Image.Transpose.ROTATE_270)  # 90 degrees clockwise
    output = BytesIO()
    image.save(output, format="JPEG", quality=95)
    return output.getvalue(), image.width, image.height, round(contrast, 3)


def scene_ball_inventory(scene_path: Path) -> int:
    """World-object truth only; never infer ball visibility or detector accuracy."""
    if not isinstance(scene_path, Path) or scene_path.is_symlink():
        raise VisualProbeError("pinned MuJoCo scene required")
    try:
        root = ET.parse(scene_path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise VisualProbeError("pinned MuJoCo apartment scene unavailable") from exc
    found = set()
    for body in root.iter("body"):
        name = body.get("name")
        if name not in WORLD_BALL_NAMES:
            continue
        if (body.find("freejoint") is None
                or not any(geom.get("type") == "sphere"
                           and geom.get("name") == name + "_geom"
                           for geom in body.findall("geom"))):
            raise VisualProbeError("scene ball has no expected dynamic sphere")
        found.add(name)
    if found != WORLD_BALL_NAMES:
        raise VisualProbeError("scene lacks the predeclared three free balls")
    return len(found)


def evaluate_once(state_dir: Path, model_path: Path,
                  scene_path: Path) -> dict:
    """One bounded read-only probe; no action, Qwen call or SQLite write."""
    if not isinstance(state_dir, Path) or state_dir.is_symlink() or not state_dir.is_dir():
        raise VisualProbeError("existing trusted simulator state dir required")
    ball_count = scene_ball_inventory(scene_path)
    # Reuse X2's OEM read-only health, state and ToF parsers unchanged.
    telemetry = read_sim_telemetry(state_dir, samples=2)
    sequences = telemetry["tof_sequences"]
    if (telemetry["robot_healthy"] is not True
            or telemetry["tof_unavailable"] is True
            or telemetry["tof_frame_cells"] != [64, 64]
            or len(sequences) != 2 or sequences[1] <= sequences[0]):
        raise VisualProbeError("simulated robot or ToF not fresh/healthy")
    if (telemetry["health_achieved_hz"] is None
            or telemetry["health_achieved_hz"] < 45):
        raise VisualProbeError("robotd loop below OEM 45 Hz health gate")

    # Exact SHA-pinned public Cat-A weights, no model training or threshold search.
    validate_model_file(model_path)
    shapes = []
    image = None
    for _ in range(2):
        shape, raw = read_frame(state_dir / "duck-a-frame.sock")
        jpeg, width, height, contrast = jpeg_for_existing_yolox(
            raw, width=shape.width, height=shape.height, rotate=shape.rotation
        )
        shapes.append((shape.age_us, width, height, contrast))
        image = jpeg
    assert image is not None

    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise VisualProbeError("unreviewed YOLOX ONNX interface")
    tensor = prepare_image(image, mode="original")
    t0 = time.perf_counter()
    raw_output = session.run(None, {"images": tensor})[0]
    infer_ms = round((time.perf_counter() - t0) * 1000, 3)
    # Existing Cat-A2a nonmax suppression and 0.25 fixed threshold.
    boxes = decode_boxes(raw_output, width=shapes[-1][1], height=shapes[-1][2])
    counts = dict(sorted(Counter(b.category for b in boxes).items()))
    return {
        "lot": "SIM-VIS-A1",
        "status": "visual_path_observed_no_pixel_ground_truth",
        "source": "oem_pinned_duck_sim_mediad_declared",
        "frame_count": len(shapes),
        "raw_uyvy_geometry": [FRAME_WIDTH, FRAME_HEIGHT],
        "raw_rotate_deg_clockwise": FRAME_ROTATION,
        "upright_yolox_geometry": [shapes[-1][1], shapes[-1][2]],
        "frame_age_ms": [round(x[0] / 1000, 3) for x in shapes],
        "render_rgb_std": [x[3] for x in shapes],
        "robot_healthy": telemetry["robot_healthy"],
        "robotd_hz": telemetry["health_achieved_hz"],
        "tof_frame_cells": telemetry["tof_frame_cells"],
        "tof_sequence_advanced": True,
        "world_free_balls": ball_count,
        "ball_visible_in_frame_ground_truth": None,
        "ball_true_positives": None,
        "ball_false_positives": None,
        "ball_false_negatives": None,
        "accuracy_validated": False,
        "yolox_sha256": MODEL_SHA256,
        "yolox_score_threshold": MIN_SCORE,
        "yolox_inference_ms_host": infer_ms,
        "proposed_box_count": len(boxes),
        "proposed_classes": counts,
        "same_frame_mujoco_segmentation": False,
        "actual_robot_or_camera_validated": False,
        "companion_motor_commands_issued": 0,
        "qwen_calls": 0,
        "sqlite_writes": 0,
        "raw_media_stored_or_uploaded": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--scene-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-simulated-snapshot", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_simulated_snapshot:
        parser.error("explicit simulated camera snapshot authorization required")
    try:
        result = evaluate_once(args.state_dir, args.model_path, args.scene_path)
        if args.output.exists() or args.output.is_symlink():
            raise VisualProbeError("refusing to overwrite a simulator report")
        args.output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    except (VisualProbeError, ValueError, OSError, RuntimeError) as exc:
        print(f"SIM-VIS-A1 inconclusive: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
