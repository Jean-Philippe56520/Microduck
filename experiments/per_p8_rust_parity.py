"""PER-P8: one-image vendor RKNN host simulation -> exact same tensors -> Rust masks.

No second SDK inference, robot, camera, SQLite, Qwen, motors or published tensor.
Decoded tensors are ephemeral in a private temporary directory, never artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import traceback

from experiments import per_p6_yolo26seg_tail as p6

MASK_PIXELS = 160 * 160
PIXEL_MIN_ALL = 0.999
PIXEL_MIN_EACH = 0.995
MAX_GEOM_DELTA = 0.001
MAX_CANDIDATES = 10


def run_rust_once(executable: Path, decoded, proto):
    """Read-only mask producer; only transient local tensor/mask bytes."""
    import numpy as np

    if not executable.is_file() or executable.is_symlink():
        raise ValueError("approved host Rust probe missing/unsafe")
    if tuple(decoded.shape) != (1, 300, 38):
        raise ValueError("unexpected ONNX output0 shape")
    if tuple(proto.shape) != (1, 32, 160, 160):
        raise ValueError("unexpected ONNX output1 shape")
    if not np.isfinite(decoded).all() or not np.isfinite(proto).all():
        raise ValueError("non-finite pre-Rust tensor")
    tmpdir = os.environ.get("RUNNER_TEMP") or None
    with tempfile.TemporaryDirectory(dir=tmpdir, prefix="kwipi-per-p8-") as temp:
        folder = Path(temp)
        boxpath, protopath, maskpath = (folder / x for x in (
            "decoded-f32-le.bin", "prototype-f32-le.bin", "rust-mask-u8.bin"))
        np.asarray(decoded, dtype="<f4", order="C").tofile(boxpath)
        np.asarray(proto, dtype="<f4", order="C").tofile(protopath)
        result = subprocess.run(
            [str(executable.resolve()), str(boxpath), str(protopath), str(maskpath)],
            check=False, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError("Rust parity probe refused input: " + result.stderr[:450])
        data = json.loads(result.stdout.strip())
        count = data.get("count")
        if type(count) is not int or not 0 <= count <= MAX_CANDIDATES:
            raise ValueError("invalid Rust mask count")
        if not maskpath.is_file() or maskpath.stat().st_size != count * MASK_PIXELS:
            raise ValueError("invalid or missing Rust mask file")
        mask = np.fromfile(maskpath, dtype=np.uint8).reshape(count, 160, 160)
        if np.any((mask != 0) & (mask != 1)):
            raise ValueError("non-binary Rust masks")
        if len(data.get("classes", [])) != count or len(data.get("scores", [])) != count or len(data.get("boxes", [])) != count:
            raise ValueError("invalid Rust metadata cardinality")
        return data, mask


def verify_against_official(decoded, proto, executable: Path, report: dict):
    """Official vendor decoder is only a test oracle on x86; never shipped on robot."""
    import numpy as np
    import torch
    from ultralytics.utils import nms, ops

    if tuple(decoded.shape) != (1, 300, 38) or tuple(proto.shape) != (1, 32, 160, 160):
        raise ValueError("wrong shape for official P6 decoder")
    official = nms.non_max_suppression(
        torch.from_numpy(np.asarray(decoded).copy()).float(),
        conf_thres=0.25, iou_thres=0.5, max_det=10, nc=80, end2end=True,
    )[0]
    if official.ndim != 2 or official.shape[1] != 38:
        raise RuntimeError("official NMS emitted an unexpected shape")
    if len(official):
        official_masks = ops.process_mask(
            torch.from_numpy(np.asarray(proto[0]).copy()).float(),
            official[:, 6:], official[:, :4], (640, 640), upsample=False,
        ).cpu().numpy().astype(np.uint8, copy=False)
    else:
        official_masks = np.zeros((0, 160, 160), dtype=np.uint8)

    rust_metadata, rust_masks = run_rust_once(executable, decoded, proto)
    count = int(len(official))
    report["p8_official_count"] = count
    report["p8_rust_count"] = rust_metadata["count"]
    if count != rust_metadata["count"]:
        raise RuntimeError("Rust vs official proposal count differs")
    if count == 0 or int(np.count_nonzero(official_masks)) == 0:
        raise RuntimeError("insufficient_zero_masks: cannot establish real parity")

    o = official.cpu().numpy()
    rust_classes = np.asarray(rust_metadata["classes"], dtype=np.int32)
    rust_scores = np.asarray(rust_metadata["scores"], dtype=np.float32)
    rust_boxes = np.asarray(rust_metadata["boxes"], dtype=np.float32)
    if rust_boxes.shape != (count, 4):
        raise ValueError("Rust metadata box shape wrong")
    if not np.array_equal(rust_classes, o[:, 5].astype(np.int32)):
        raise RuntimeError("Rust and official class ids/order differ")
    score_diff = float(np.max(np.abs(rust_scores - o[:, 4])))
    xyxy_diff = float(np.max(np.abs(rust_boxes - o[:, :4])))
    report["p8_score_max_abs"] = round(score_diff, 8)
    report["p8_xyxy_max_abs"] = round(xyxy_diff, 8)
    if score_diff > MAX_GEOM_DELTA or xyxy_diff > MAX_GEOM_DELTA:
        raise RuntimeError("Rust and official detection geometry differs")

    mismatch_per = np.count_nonzero(rust_masks != official_masks, axis=(1, 2))
    agreement_each = 1.0 - mismatch_per / MASK_PIXELS
    overall = 1.0 - int(mismatch_per.sum()) / (count * MASK_PIXELS)
    report["p8_comparison_pixels"] = count * MASK_PIXELS
    report["p8_mismatched_pixels"] = int(mismatch_per.sum())
    report["p8_mismatch_pixels_per_instance"] = [int(x) for x in mismatch_per]
    report["p8_pixel_agreement_all"] = round(float(overall), 8)
    report["p8_pixel_agreement_worst"] = round(float(min(agreement_each)), 8)
    report["p8_official_nonempty"] = int(np.count_nonzero(np.sum(official_masks, axis=(1, 2))))
    report["p8_rust_nonempty"] = int(np.count_nonzero(np.sum(rust_masks, axis=(1, 2))))
    report["p8_source"] = "one_RKNN_2.3.2_x86_simulation_public_calibration_image"
    report["p8_OEM_mediad_integrated"] = False
    report["p8_robot_validated"] = False
    report["p8_rust_parity_passed"] = False
    if overall < PIXEL_MIN_ALL or np.min(agreement_each) < PIXEL_MIN_EACH:
        raise RuntimeError("Rust mask pixel parity below preregistered gate")
    if report["p8_official_nonempty"] != report["p8_rust_nonempty"]:
        raise RuntimeError("Rust and official nonempty-mask count differs")
    report["p8_rust_parity_passed"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weight", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--rust-bin", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {
        "study": "PER-P8_Rust_vs_vendor_RKNN_host_parity",
        "status": "not_executed",
        "robot_present": False, "NPU_real_measured": False,
        "OEM_integration": False, "license_cleared_for_deployment": False,
        "model_or_media_redistributed": False, "p8_rust_parity_passed": False,
        "memory_writes": 0, "motor_commands": 0,
    }
    code = 0
    try:
        p6.run(args.weight, args.calibration, result, parity_hook=lambda decoded, proto, report:
               verify_against_official(decoded, proto, args.rust_bin, report))
        if not result["p8_rust_parity_passed"]:
            raise RuntimeError("Rust parity never executed")
        result["status"] = "rust_cpu_matches_vendor_host_sdk_on_one_calibration_image"
    except Exception as error:
        result["status"] = "rust_parity_failed_stop"
        result["error_type"] = type(error).__name__
        result["error_text"] = str(error)[:450]
        print(traceback.format_exc(limit=8), file=sys.stderr)
        code = 1
    result["host_process_peak_rss_kib_including_all_toolkits"] = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
