"""PER-P3B: offline-only official PP-YOLOE vs pinned YOLOX image-level proposals.

Public CI uses existing 13 licensed/attributed repository fixtures only.
Private input MUST be run locally by the operator; never send photos to CI.
No GT boxes, no IoU, no robot, Qwen, SQLite, media socket or motor action.
"""
from __future__ import annotations

import argparse
from collections import Counter
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

TARGETS = {"person": 0, "cat": 15, "dog": 16, "sports_ball": 32, "chair": 56}
EXPECTED_PUBLIC = {
    "cat": 4, "dog": 2, "person": 1, "chair": 1,
    "sports_ball": 3, "unknown": 2,
}
PRIVATE_STUDY = "Cat-A2b two private low-angle views qualitative preflight"
PRIVATE_IDS = ("view_lateral", "view_front")
MAX_IMAGE_BYTES = 8_000_000
MAX_SOURCE_PIXELS = 25_000_000
MAX_EDGE_FOR_INFERENCE = 2048


class StudyStop(ValueError):
    """A contract failed; do not silently resample or repair test data."""


def _object(blob: bytes):
    try:
        return json.loads(
            blob, parse_constant=lambda x: (_ for _ in ()).throw(
                StudyStop("JSON nonfinite")))
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise StudyStop("invalid bounded fixture manifest") from exc


def _safe_payload(root: Path, file_name: str) -> bytes:
    if (type(file_name) is not str or not file_name
            or file_name.startswith(".") or "\\" in file_name
            or Path(file_name).is_absolute()
            or any(p in ("", ".", "..") for p in Path(file_name).parts)):
        raise StudyStop("invalid/traversing fixture name")
    path = root / file_name
    if path.is_symlink() or not path.is_file():
        raise StudyStop("missing or symlinked image")
    size = path.stat().st_size
    if not 1024 < size <= MAX_IMAGE_BYTES:
        raise StudyStop("unexpected image byte length")
    return path.read_bytes()


def verify_inputs(root: Path, *, source: str) -> list[dict]:
    if (source not in ("public", "private")
            or root.is_symlink() or not root.is_dir()
            or (root / "manifest.json").is_symlink()):
        raise StudyStop("unsafe/missing source directory")
    if source == "private" and os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise StudyStop("private photos explicitly forbidden on public CI")
    manifest = _object((root / "manifest.json").read_bytes())
    if source == "public":
        if root.name != "public_vision_smoke" or manifest.get("version") != 1:
            raise StudyStop("not the approved existing public cohort")
        listed = manifest.get("images")
        if type(listed) is not list or len(listed) != 13:
            raise StudyStop("public image manifest changed")
        counts = Counter(item.get("category") for item in listed)
        if dict(counts) != EXPECTED_PUBLIC:
            raise StudyStop("public classes/counts changed")
        seen: set[str] = set()
        rows = []
        for entry in listed:
            if type(entry) is not dict:
                raise StudyStop("invalid public entry")
            filename = entry.get("file")
            if type(filename) is not str or Path(filename).name != filename:
                raise StudyStop("unexpected public image path")
            data = _safe_payload(root, filename)
            header = f"blob {len(data)}\\0".encode()
            digest = hashlib.sha1(header + data).hexdigest()
            if digest != entry.get("source_git_blob_sha") or filename in seen:
                raise StudyStop("public git-blob hash/uniqueness mismatch")
            seen.add(filename)
            rows.append({"id": filename, "expected": entry["category"], "bytes": data})
        return rows

    if (manifest.get("study") != PRIVATE_STUDY
            or manifest.get("not_two_independent_scenes") is not True
            or manifest.get("image_exif_removed") is not True
            or manifest.get("gt_boxes") != "not_available"
            or manifest.get("camera_height_mm") is not None):
        raise StudyStop("private non-GT preflight contract changed")
    photos = manifest.get("photos")
    if (type(photos) is not list or len(photos) != 2
            or tuple(p.get("id") for p in photos) != PRIVATE_IDS):
        raise StudyStop("expected two same-scene private views only")
    result = []
    seen: set[str] = set()
    for entry in photos:
        name = entry.get("file")
        if (type(name) is not str or
                not name.startswith("images/") or
                Path(name).suffix.lower() != ".jpg" or
                entry.get("session_group") != manifest.get("scene_group")):
            raise StudyStop("private scene/photo mismatch")
        data = _safe_payload(root, name)
        digest = hashlib.sha256(data).hexdigest()
        if (digest != entry.get("sha256_sanitized")
                or name in seen or len(digest) != 64):
            raise StudyStop("private photo digest/uniqueness mismatch")
        seen.add(name)
        result.append({"id": entry["id"], "expected": None, "bytes": data,
                       "expected_size": (entry.get("width"), entry.get("height")),
                       "require_no_exif": True})
    return result


def prepare_rgb_and_jpeg(row: dict):
    """One bounded in-memory normalised source shared by both model pipelines."""
    from PIL import Image, ImageOps

    payload = row["bytes"]
    try:
        with Image.open(BytesIO(payload)) as src:
            if (src.format not in ("JPEG", "PNG")
                    or src.width * src.height > MAX_SOURCE_PIXELS
                    or min(src.size) < 32
                    or (row.get("require_no_exif") and len(src.getexif()) != 0)):
                raise StudyStop("image format/geometry/EXIF contract rejected")
            if row.get("expected_size") and tuple(src.size) != row["expected_size"]:
                raise StudyStop("sanitised private image dimensions altered")
            rgb = ImageOps.exif_transpose(src).convert("RGB")
        if max(rgb.size) > MAX_EDGE_FOR_INFERENCE:
            rgb.thumbnail((MAX_EDGE_FOR_INFERENCE, MAX_EDGE_FOR_INFERENCE),
                          Image.Resampling.BILINEAR)
        out = BytesIO()
        rgb.save(out, format="JPEG", quality=95)
        return rgb, out.getvalue()
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        if isinstance(exc, StudyStop):
            raise
        raise StudyStop("unable to decode bounded source image") from exc


def summarize_targets(items: list[tuple[int, float]]) -> dict:
    """Conserve only five COCO labels; extra classes are not 'unknown objects'."""
    values = {}
    for idx, score in items:
        if (type(idx) is not int or idx not in range(80)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
                or not 0.0 <= float(score) <= 1.0):
            raise StudyStop("invalid untrusted model class/score")
    for name, idx in TARGETS.items():
        scores = [float(score) for c, score in items if c == idx]
        if scores:
            values[name] = {
                "count": len(scores), "best_score": round(max(scores), 6),
            }
    return values


def run_yolox(sess, jpeg: bytes, width: int, height: int) -> tuple[list, float]:
    from microduck_companion.cata_yolox_categories import prepare_image
    from microduck_companion.cata2_bbox_eval import decode_boxes

    tensor = prepare_image(jpeg, mode="original")
    inp = sess.get_inputs()
    if len(inp) != 1 or inp[0].name != "images":
        raise StudyStop("unexpected YOLOX interface")
    start = time.perf_counter()
    outputs = sess.run(None, {"images": tensor})
    duration = round((time.perf_counter() - start) * 1000, 3)
    if len(outputs) != 1:
        raise StudyStop("unexpected YOLOX output count")
    boxes = decode_boxes(outputs[0], width=width, height=height)
    return [(TARGETS[b.category], float(b.confidence)) for b in boxes], duration


def run_ppyoloe(sess, vendor, rgb) -> tuple[list, float]:
    import cv2
    import numpy as np
    from py_utils.coco_utils import COCO_test_helper
    from experiments.per_p3a_rockchip_low_oem_visual import check_heads

    rgb_bytes = np.array(rgb, dtype=np.uint8)
    bgr = cv2.cvtColor(rgb_bytes, cv2.COLOR_RGB2BGR)
    helper = COCO_test_helper(enable_letter_box=True)
    padded = helper.letter_box(
        im=bgr, new_shape=(640, 640), pad_color=(0, 0, 0))
    input_rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    tensor = (np.ascontiguousarray(input_rgb.transpose(2, 0, 1)[None],
                                  dtype=np.float32) / 255.0)
    inputs = sess.get_inputs()
    if (len(inputs) != 1
            or list(inputs[0].shape) != [1, 3, 640, 640]):
        raise StudyStop("unexpected vendor ONNX interface")
    start = time.perf_counter()
    outputs = sess.run(None, {inputs[0].name: tensor})
    duration = round((time.perf_counter() - start) * 1000, 3)
    check_heads(outputs)
    boxes, classes, scores = vendor.post_process(outputs)
    result = []
    if boxes is not None:
        mapped = helper.get_real_box(boxes)
        for box, category, score in zip(mapped, classes, scores):
            if (not np.isfinite(box).all()
                    or len(box) != 4
                    or not 0 <= box[0] < box[2] <= rgb.width
                    or not 0 <= box[1] < box[3] <= rgb.height):
                continue  # Vendor can propose a box outside the visible frame.
            result.append((int(category), float(score)))
    return result, duration


def assess_image(mode: str, expected, detections: dict) -> dict:
    """Image-level proposals are NOT IoU/mAP, object existence or obstacle safety."""
    if mode not in ("public", "private") or set(detections) != {"yolox", "ppyoloe"}:
        raise StudyStop("incomplete model pair")
    row = {"expected_image_label": expected if mode == "public" else None,
           "results": {}}
    for model, pairs in detections.items():
        found = summarize_targets(pairs)
        out = {"proposed_categories": found}
        if mode == "public":
            if expected == "unknown":
                out["no_target_category_proposed"] = not bool(found)
            elif expected in TARGETS:
                out["expected_category_proposed"] = expected in found
            else:
                raise StudyStop("unknown public expected label")
        row["results"][model] = out
    return row


def run(root: Path, *, source: str, preflight_only: bool,
        yolox_model: Path | None, ppyoloe_model: Path | None,
        vendor_root: Path | None) -> dict:
    cases = verify_inputs(root, source=source)
    from PIL import Image  # Loaded only during explicit local/CI execution
    for entry in cases:
        rgb, jpeg = prepare_rgb_and_jpeg(entry)
        entry["prepared_jpeg"] = jpeg
        entry["rgb"] = rgb
        entry.pop("bytes")  # Data must not enter any report.
    report = {
        "study": "PER-P3B_unmodified_YOLOX_vs_Rockchip_PPYOLOE",
        "source": source, "scenes": len(cases),
        "single_private_scene_multiple_angles": source == "private",
        "source_integrity_passed": True,
        "inference_attempted": False,
        "no_robot_or_npu_or_onnx_change": True,
        "images_or_weights_recorded": False,
        "ground_truth_boxes_available": False,
        "io_u_or_average_precision_claimed": False,
    }
    if preflight_only:
        report["status"] = "preflight_only_NO_model_scores"
        return report
    if not all(p is not None for p in (yolox_model, ppyoloe_model, vendor_root)):
        raise StudyStop("both pinned ONNX models and official vendor path required")
    from microduck_companion.cata_yolox_categories import validate_model_file
    from experiments.per_p3a_rockchip_low_oem_visual import verify_model, load_vendor
    import onnxruntime as ort

    validate_model_file(yolox_model)
    verify_model(ppyoloe_model)
    vendor = load_vendor(vendor_root)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    opts.inter_op_num_threads = 1
    yolox = ort.InferenceSession(str(yolox_model), sess_options=opts,
                                providers=["CPUExecutionProvider"])
    ppyoloe = ort.InferenceSession(str(ppyoloe_model), sess_options=opts,
                                  providers=["CPUExecutionProvider"])
    report["inference_attempted"] = True
    scored = []
    for c in cases:
        rgb, jpeg = c.pop("rgb"), c.pop("prepared_jpeg")
        a, t1 = run_yolox(yolox, jpeg, rgb.width, rgb.height)
        b, t2 = run_ppyoloe(ppyoloe, vendor, rgb)
        item = assess_image(source, c["expected"], {"yolox": a, "ppyoloe": b})
        item["id"] = c["id"]
        item["inference_ms_host_only"] = {"yolox": t1, "ppyoloe": t2}
        scored.append(item)
    report["observations"] = scored
    if source == "public":
        counts = {}
        for model in ("yolox", "ppyoloe"):
            counts[model] = {
                k: {
                    "declared_photo_count": n,
                    "expected_label_proposed": sum(
                        bool(row["results"][model].get("expected_category_proposed"))
                        for row in scored if row["expected_image_label"] == k)
                    if k != "unknown" else None,
                    "without_target_proposal": sum(
                        bool(row["results"][model].get("no_target_category_proposed"))
                        for row in scored if row["expected_image_label"] == k)
                    if k == "unknown" else None,
                }
                for k, n in EXPECTED_PUBLIC.items()
            }
        report["per_class_image_level_only"] = counts
    report["status"] = "diagnostic_only_NOT_model_selection"
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("public", "private"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--yolox-model", type=Path)
    parser.add_argument("--ppyoloe-model", type=Path)
    parser.add_argument("--vendor-root", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--authorize-local-private-inference", action="store_true")
    args = parser.parse_args(argv)
    if (args.source == "private" and not args.preflight_only
            and not args.authorize_local_private_inference):
        parser.error("explicit local private inference authorisation required")
    try:
        if args.report.exists() or args.report.is_symlink():
            raise StudyStop("refusing to overwrite previous evidence")
        obj = run(args.root, source=args.source,
                  preflight_only=args.preflight_only,
                  yolox_model=args.yolox_model, ppyoloe_model=args.ppyoloe_model,
                  vendor_root=args.vendor_root)
        args.report.write_text(json.dumps(obj, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps({k: v for k, v in obj.items()
                          if k != "observations"}, sort_keys=True))
        return 0
    except (StudyStop, ValueError, RuntimeError, OSError) as e:
        print(f"PER-P3B STOP: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
