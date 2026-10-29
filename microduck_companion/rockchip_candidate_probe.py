"""OEM-first candidate A/B: Rockchip RK3566-ready YOLO11n vs existing YOLOX.

One new, disjoint COCO2017-val third cohort with independent boxes.
Only public reviewed CC BY-labelled photographs; no originals stored/logged.
Preprocessor/head contract adapted narrowly from Rockchip RKNN Model Zoo
commit 837db8e992815ff8647eadb709f07067f4bc3a71 (Apache-2.0 demo).
The upstream Ultralytics model/weights rights remain to be reviewed; host
evaluation is NOT a licensed production integration or NPU performance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import sys
import time

from .cata_yolox_categories import (
    CATEGORIES, MIN_SCORE as YOLOX_SCORE, MODEL_SHA256 as YOLOX_SHA,
    SIZE, prepare_image, validate_model_file,
)
from .cata2_bbox_eval import (
    ANNOTATIONS_SHA256, MAX_COCO_JSON_BYTES, Box, _official_jpeg,
    decode_boxes, evaluate_localization, iou, select_coco_cases,
)

# SHA + output format obtained directly from a completed OEM-first
# GitHub preflight: https://github.com/Jean-Philippe56520/Microduck/
# actions/runs/40929896414 ; do not ship or embed weights.
ROCKCHIP_SHA = "62a3751662e06c678debb54b113c211d918f245ea6d3aea0b09fc418b8fc7705"
ROCKCHIP_BYTES = 10527859
ROCKCHIP_INPUT = 640
ROCKCHIP_SCORE = 0.25  # Rockchip vendor unmodified reference
ROCKCHIP_NMS = 0.45
PREDECLARED_COHORT_COUNTS = (3, 3)  # per class, target-free
PREDECLARED_COHORT = "third_disjoint_cohort_fixed_SHA_order_2026-10-29"
MAX_SINGLE_CLASS_CANDIDATES = 160
MAX_TOTAL_RESULTS = 80
EXPECTED_STRIDES = (8, 16, 32)
CLASS_TO_ID = dict(CATEGORIES)


class CandidateProbeError(RuntimeError):
    """No trustworthy positive/negative evidence; never a model success."""


def validate_vendor_file(path: Path) -> None:
    """The inspected ONNX file, never an arbitrary source of network/code."""
    if (not isinstance(path, Path) or path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != ROCKCHIP_BYTES):
        raise CandidateProbeError("Rockchip candidate size/path is not pinned")
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    if digest != ROCKCHIP_SHA:
        raise CandidateProbeError("Rockchip ONNX SHA256 mismatch")


def _preprocess_rockchip(jpeg: bytes, *, original_w: int, original_h: int):
    """Vendor's black-padded letterbox, bilinear resize, RGB float / 255."""
    import cv2
    import numpy as np
    from PIL import Image

    if not isinstance(jpeg, bytes):
        raise CandidateProbeError("verified JPEG bytes required")
    with Image.open(BytesIO(jpeg)) as img:
        if img.format != "JPEG" or img.size != (original_w, original_h):
            raise CandidateProbeError("COCO source geometry mismatch")
        rgb = np.array(img.convert("RGB"), copy=True)
    ratio = min(ROCKCHIP_INPUT / original_w, ROCKCHIP_INPUT / original_h)
    rw, rh = int(round(original_w * ratio)), int(round(original_h * ratio))
    dx = (ROCKCHIP_INPUT - rw) / 2
    dy = (ROCKCHIP_INPUT - rh) / 2
    left, right = int(round(dx - .1)), int(round(dx + .1))
    top, bottom = int(round(dy - .1)), int(round(dy + .1))
    resized = cv2.resize(rgb, (rw, rh), interpolation=cv2.INTER_LINEAR)
    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )
    if padded.shape != (ROCKCHIP_INPUT, ROCKCHIP_INPUT, 3):
        raise CandidateProbeError("Rockchip vendor letterbox geometry invalid")
    tensor = np.ascontiguousarray(
        padded.transpose(2, 0, 1)[None, ...], dtype=np.float32
    ) / np.float32(255.)
    return tensor, ratio, left, top


def _dfl_bins(position):
    """Distribution focal regression exactly as vendor, but NumPy not Torch."""
    import numpy as np
    x = np.asarray(position)
    if (x.ndim != 4 or x.shape[0] != 1 or x.shape[1] != 64
            or not np.issubdtype(x.dtype, np.floating)
            or not np.isfinite(x).all()):
        raise CandidateProbeError("wrong Rockchip DFL input")
    height, width = x.shape[2:]
    values = x.reshape(1, 4, 16, height, width)
    shifted = values - values.max(axis=2, keepdims=True)
    exponents = np.exp(shifted)
    distributions = exponents / exponents.sum(axis=2, keepdims=True)
    bins = np.arange(16, dtype=np.float32).reshape(1, 1, 16, 1, 1)
    return np.sum(distributions * bins, axis=2)[0]


def validate_vendor_outputs(outputs: list) -> None:
    import numpy as np
    expected = []
    for res in (80, 40, 20):
        expected += [
            (1, 64, res, res),
            (1, 80, res, res),
            (1, 1, res, res),
        ]
    if (type(outputs) is not list or len(outputs) != 9
            or any(np.asarray(a).shape != shape for a, shape in zip(outputs, expected))
            or any(not np.issubdtype(np.asarray(a).dtype, np.floating)
                   or not np.isfinite(a).all() for a in outputs)):
        raise CandidateProbeError("Rockchip YOLO11n 9-head schema changed")


def _nms_indices(boxes, scores, limit: int = MAX_SINGLE_CLASS_CANDIDATES):
    import numpy as np
    if len(scores) == 0:
        return []
    order = np.argsort(-scores, kind="stable")[:limit]
    kept = []
    while len(order) > 0:
        k = int(order[0])
        kept.append(k)
        if len(order) == 1:
            break
        other = order[1:]
        xx0 = np.maximum(boxes[k, 0], boxes[other, 0])
        yy0 = np.maximum(boxes[k, 1], boxes[other, 1])
        xx1 = np.minimum(boxes[k, 2], boxes[other, 2])
        yy1 = np.minimum(boxes[k, 3], boxes[other, 3])
        intersection = np.maximum(0., xx1-xx0)*np.maximum(0., yy1-yy0)
        areas = np.maximum(0., boxes[:, 2]-boxes[:, 0])*np.maximum(
            0., boxes[:, 3]-boxes[:, 1]
        )
        union = areas[k]+areas[other]-intersection
        overlap = np.divide(intersection, union, out=np.zeros_like(intersection),
                            where=union>0)
        order = other[overlap <= ROCKCHIP_NMS]
    return kept


def decode_rockchip(outputs: list, *, original_w: int, original_h: int,
                    ratio: float, pad_left: int, pad_top: int) -> tuple[Box, ...]:
    """Decode official three-scale 80-class optimized head, one-to-one Cat-A boxes.

    The vendor first takes a single top COCO class at each grid point, then
    applies class-wise NMS. Other non-target COCO classes are not false alarms
    for the five requested categories. Coordinates undo *black* letterbox.
    """
    import numpy as np

    validate_vendor_outputs(outputs)
    if (not 32 <= original_w <= 4096 or not 32 <= original_h <= 4096
            or not math.isfinite(ratio) or ratio <= 0
            or not 0 <= pad_left <= ROCKCHIP_INPUT
            or not 0 <= pad_top <= ROCKCHIP_INPUT):
        raise CandidateProbeError("invalid source geometry for model output")
    all_boxes, all_scores, all_classes = [], [], []
    for k, stride in enumerate(EXPECTED_STRIDES):
        pos = outputs[3 * k]
        conf = outputs[3 * k + 1]
        # Branch #3 is the original vendor's auxiliary score-sum output.
        boxes_dfl = _dfl_bins(pos)
        grid_h, grid_w = conf.shape[2], conf.shape[3]
        yy, xx = np.mgrid[:grid_h, :grid_w]
        x0 = (xx + .5 - boxes_dfl[0]) * stride
        y0 = (yy + .5 - boxes_dfl[1]) * stride
        x1 = (xx + .5 + boxes_dfl[2]) * stride
        y1 = (yy + .5 + boxes_dfl[3]) * stride
        xyxy = np.stack([x0, y0, x1, y1], axis=-1).reshape(-1, 4)
        probs = np.transpose(conf[0], (1, 2, 0)).reshape(-1, 80)
        if np.any(probs < 0) or np.any(probs > 1.00001):
            raise CandidateProbeError("Rockchip class probabilities out of range")
        classes = np.argmax(probs, axis=1)
        scores = np.max(probs, axis=1)
        active = np.flatnonzero(scores >= ROCKCHIP_SCORE)
        if active.size:
            all_boxes.append(xyxy[active])
            all_scores.append(scores[active])
            all_classes.append(classes[active])
    if not all_boxes:
        return ()
    boxes = np.concatenate(all_boxes, axis=0)
    scores = np.concatenate(all_scores, axis=0)
    classes = np.concatenate(all_classes, axis=0)
    results = []
    for category, index in CLASS_TO_ID.items():
        inds = np.flatnonzero(classes == index)
        if not inds.size:
            continue
        subset = boxes[inds]
        confidence = scores[inds]
        for ki in _nms_indices(subset, confidence):
            x0, y0, x1, y1 = subset[ki]
            coords = (
                float(np.clip((x0-pad_left)/ratio, 0, original_w)),
                float(np.clip((y0-pad_top)/ratio, 0, original_h)),
                float(np.clip((x1-pad_left)/ratio, 0, original_w)),
                float(np.clip((y1-pad_top)/ratio, 0, original_h)),
            )
            if coords[2] > coords[0] and coords[3] > coords[1]:
                results.append(Box(category, coords,
                                   float(np.clip(confidence[ki], 0, 1))))
    return tuple(sorted(
        results, key=lambda b: (-b.confidence, b.category, b.xyxy)
    )[:MAX_TOTAL_RESULTS])


def _session(model: Path, *, rockchip: bool):
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    s = ort.InferenceSession(str(model), sess_options=opts,
                             providers=["CPUExecutionProvider"])
    ip = s.get_inputs()
    op = s.get_outputs()
    input_size = ROCKCHIP_INPUT if rockchip else SIZE
    expected_out_shapes = ([1, 64, 80, 80], [1, 80, 80, 80], [1, 1, 80, 80],
                           [1, 64, 40, 40], [1, 80, 40, 40], [1, 1, 40, 40],
                           [1, 64, 20, 20], [1, 80, 20, 20], [1, 1, 20, 20]) if rockchip else ([1, 3549, 85],)
    if (len(ip) != 1 or len(op) != len(expected_out_shapes)
            or ip[0].name != "images"
            or ip[0].shape != [1, 3, input_size, input_size]
            or ip[0].type != "tensor(float)"
            or tuple(o.shape for o in op) != tuple(expected_out_shapes)
            or any(o.type != "tensor(float)" for o in op)):
        raise CandidateProbeError("model contract differs from approved preflight")
    return s


def _fixed_third_cohort(annotations: bytes):
    original = select_coco_cases(annotations)
    first_exclusions = frozenset(c.image_id for c in original)
    second = select_coco_cases(annotations, excluded_image_ids=first_exclusions)
    all_exclusions = first_exclusions | frozenset(c.image_id for c in second)
    cases = select_coco_cases(
        annotations, per_class=PREDECLARED_COHORT_COUNTS[0],
        negatives=PREDECLARED_COHORT_COUNTS[1],
        excluded_image_ids=all_exclusions,
    )
    if len(cases) != 18 or any(c.image_id in all_exclusions for c in cases):
        raise CandidateProbeError("third COCO set is not disjoint from historical sets")
    return cases, len(all_exclusions)


def _percentiles(times: list[float]) -> dict:
    return {
        "median_ms": round(statistics.median(times), 3),
        "p95_ms": round(sorted(times)[min(len(times)-1, math.ceil(.95*len(times))-1)], 3),
    }


def compare(*, candidate: Path, baseline: Path, annotations_path: Path):
    validate_vendor_file(candidate)
    validate_model_file(baseline)
    if (not annotations_path.is_file() or annotations_path.is_symlink()
            or not 128 <= annotations_path.stat().st_size <= MAX_COCO_JSON_BYTES):
        raise CandidateProbeError("missing independently annotated COCO-val")
    raw_json = annotations_path.read_bytes()
    if hashlib.sha256(raw_json).hexdigest() != ANNOTATIONS_SHA256:
        raise CandidateProbeError("COCO annotation SHA mismatch")
    samples, excluded = _fixed_third_cohort(raw_json)
    rk = _session(candidate, rockchip=True)
    yo = _session(baseline, rockchip=False)
    model_results = {"rockchip_yolo11n": [], "megvii_yolox_nano": []}
    timings = {"rockchip_yolo11n": [], "megvii_yolox_nano": []}
    digests = []
    started = time.perf_counter()
    for case in samples:
        jpeg = _official_jpeg(case)
        digests.append(hashlib.sha256(jpeg).hexdigest())
        tensor, ratio, pl, pt = _preprocess_rockchip(
            jpeg, original_w=case.width, original_h=case.height
        )
        t0 = time.perf_counter()
        rk_outputs = rk.run(None, {"images": tensor})
        timings["rockchip_yolo11n"].append((time.perf_counter()-t0)*1000)
        rk_boxes = decode_rockchip(
            rk_outputs, original_w=case.width, original_h=case.height,
            ratio=ratio, pad_left=pl, pad_top=pt,
        )
        model_results["rockchip_yolo11n"].append((case, rk_boxes))
        yolox_image = prepare_image(jpeg, mode="original")
        t0 = time.perf_counter()
        yo_raw = yo.run(None, {"images": yolox_image})[0]
        timings["megvii_yolox_nano"].append((time.perf_counter()-t0)*1000)
        yo_boxes = decode_boxes(yo_raw, width=case.width, height=case.height)
        model_results["megvii_yolox_nano"].append((case, yo_boxes))
        del jpeg, tensor, rk_outputs, yolox_image, yo_raw

    rk_result = evaluate_localization(tuple(model_results["rockchip_yolo11n"]))
    yo_result = evaluate_localization(tuple(model_results["megvii_yolox_nano"]))
    ball = "sports_ball"
    diff_ap = (rk_result["macro_ap50_101point_present_classes"]
               - yo_result["macro_ap50_101point_present_classes"])
    quality_gate = (
        diff_ap >= .03
        and rk_result["by_class"][ball]["tp_iou50"] >
            yo_result["by_class"][ball]["tp_iou50"]
        and rk_result["empty_gt_images_with_false_alarm"] <=
            yo_result["empty_gt_images_with_false_alarm"] + 1
    )
    return {
        "lot": "OEM-FIRST-RK-A1",
        "status": "comparison_completed_only_no_rknn_or_robot",
        "source": "licensed_public_COCO2017_val_with_independent_bbox",
        "cohort": PREDECLARED_COHORT,
        "images": len(samples),
        "selected_image_ids": [x.image_id for x in samples],
        "excluded_historical_images": excluded,
        "original_cohort_overlap": 0,
        "independent_scene_or_low_camera_height": False,
        "image_sha256": digests,
        "annotation_sha256": ANNOTATIONS_SHA256,
        "coco_image_license_metadata": "Flickr CC BY 2.0 declaration, originals not independently verified",
        "vendor_model_source": "Rockchip RKNN Model Zoo official 640px YOLO11n",
        "vendor_repo_commit": "837db8e992815ff8647eadb709f07067f4bc3a71",
        "model_sha256": {"rockchip_yolo11n": ROCKCHIP_SHA,
                         "megvii_yolox_nano": YOLOX_SHA},
        "production_rights_of_ultralytics_weights_reviewed": False,
        "model_hardware_rknn_tested": False,
        "rockchip_vendor_score": ROCKCHIP_SCORE,
        "rockchip_vendor_nms_iou": ROCKCHIP_NMS,
        "megvii_yolox_score": YOLOX_SCORE,
        "quality_gate_predeclared": "macroAP50>=YOLOX+0.03 and ball TP>YOLOX and no more than 1 extra empty-target alert",
        "quality_gate_for_further_rknn_exploration_met": quality_gate,
        "gt_is_independent_of_model": True,
        "metrics": {"rockchip_yolo11n": rk_result,
                    "megvii_yolox_nano": yo_result},
        "inference_cpu_only": {k:_percentiles(v) for k,v in timings.items()},
        "host_peak_rss_kib_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "wall_s_includes_public_image_downloads": round(time.perf_counter()-started, 3),
        "robot_50hz_thermal_battery_effect": None,
        "mediad_or_npu_integrated": False,
        "qwen_or_sqlite_calls": 0,
        "motor_actions": 0,
        "raw_media_stored_or_published": False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-model",type=Path,required=True)
    parser.add_argument("--baseline-model",type=Path,required=True)
    parser.add_argument("--annotations",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--authorize-cc-by-public",action="store_true")
    args=parser.parse_args(argv)
    if not args.authorize_cc_by_public:
        parser.error("explicit reviewed public image use required")
    try:
        value=compare(candidate=args.candidate_model,baseline=args.baseline_model,
                      annotations_path=args.annotations)
        if args.output.exists() or args.output.is_symlink():
            raise CandidateProbeError("do not overwrite experiment")
        args.output.write_text(json.dumps(value,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({
            "lot":value["lot"],"status":value["status"],
            "images":value["images"],
            "candidate_tp_fp_fn":{
                k:value["metrics"]["rockchip_yolo11n"][k]
                for k in ("tp_iou50","fp_iou50","fn_iou50","macro_ap50_101point_present_classes")
            },
            "baseline_tp_fp_fn":{
                k:value["metrics"]["megvii_yolox_nano"][k]
                for k in ("tp_iou50","fp_iou50","fn_iou50","macro_ap50_101point_present_classes")
            },
            "quality_gate_met":value["quality_gate_for_further_rknn_exploration_met"],
            "cpu_times":value["inference_cpu_only"],
        },sort_keys=True))
    except (CandidateProbeError, RuntimeError, OSError, ValueError) as exc:
        print(f"OEM-FIRST-RK-A1 inconclusive: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
