"""Fifth disjoint COCO-val: one fast GrabCut ROI selected by YOLOX without GT.

This is a host-only comparison. COCO polygon GT is used after inference for
scoring, never to choose the detector ROI. No media persisted, no second model,
no memory, Qwen, robotd or cameras.
"""
from __future__ import annotations

from collections import defaultdict
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import statistics
import time

from experiments.light_grabcut_region_probe import (
    describe_mask, grabcut_rectangle, mask_iou,
)
from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, CATEGORIES, COCO_IDS, MAX_COCO_JSON_BYTES,
    _official_jpeg, select_coco_cases,
)
from microduck_companion.cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, _grid, prepare_image, validate_model_file,
)

COHORT = "fifth_disjoint_coco_val_polygon_fixed_SHA_order_2026_10_29"
MAX_FRAME = 640
MIN_MASKS = 9
MIN_GOOD_MASKS = 7
MIN_COLOR_CASES = 7
MIN_COLOR_AGREEMENT = 0.60
MIN_ORACLE_ROUND_BALLS = 1
MIN_TOP1_BOX_HITS = 6
MIN_TOP1_BALL_HITS = 1
MAX_MEDIAN_HOST_MS = 20
MAX_P95_HOST_MS = 100


def _without_ids(data, ids):
    return json.dumps({
        **data,
        "images": [x for x in data["images"] if x["id"] not in ids],
        "annotations": [x for x in data["annotations"]
                        if x["image_id"] not in ids],
    }, separators=(",", ":")).encode("utf-8")


def _fifth_cohort(blob):
    if (len(blob) > MAX_COCO_JSON_BYTES or
            hashlib.sha256(blob).hexdigest() != ANNOTATIONS_SHA256):
        raise ValueError("unexpected COCO val annotations")
    data = json.loads(blob)
    exclude = set()
    cohort_sizes = []
    final = ()
    for per, negatives in ((4, 4), (4, 4), (3, 3), (2, 2), (2, 2)):
        selected = select_coco_cases(
            _without_ids(data, exclude) if exclude else blob,
            per_class=per, negatives=negatives,
        )
        ids = {c.image_id for c in selected}
        if ids & exclude or len(ids) != 5*per+negatives:
            raise ValueError("cohort overlap or unexpected size")
        exclude |= ids
        cohort_sizes.append(len(selected))
        final = selected
    if cohort_sizes != [24, 24, 18, 12, 12] or len(final) != 12:
        raise ValueError("invalid fifth disjoint cohort")
    return final, data, cohort_sizes[:-1]


def _polygon_mask(items, category, W, H, w, h):
    import cv2
    import numpy as np

    candidates = [
        a for a in items
        if a.get("category_id") == COCO_IDS[category]
        and a.get("iscrowd", 0) == 0
        and isinstance(a.get("segmentation"), list)
        and isinstance(a.get("bbox"), list) and len(a["bbox"]) == 4
    ]
    candidates.sort(key=lambda a: -float(a.get("area", 0)))
    if not candidates:
        return None, None
    chosen = candidates[0]
    x, y, bw, bh = chosen["bbox"]
    gt_box = (
        max(0., float(x)), max(0., float(y)),
        min(float(W), float(x+bw)), min(float(H), float(y+bh)),
    )
    if gt_box[2]-gt_box[0] < 10 or gt_box[3]-gt_box[1] < 10:
        return None, None
    mask = np.zeros((h, w), np.uint8)
    polys = []
    for p in chosen["segmentation"]:
        if not isinstance(p, list) or len(p) < 6 or len(p) % 2:
            continue
        pts = np.array(p, dtype=np.float32).reshape(-1, 2)
        if not np.isfinite(pts).all():
            continue
        pts[:, 0] *= w/W
        pts[:, 1] *= h/H
        polys.append(np.round(pts).astype(np.int32))
    if not polys:
        return None, None
    cv2.fillPoly(mask, polys, 255)
    return mask, gt_box


def _top1_proposal(raw, W, H):
    """Top 80-class COCO score, fixed 0.25, before any GT lookup."""
    import numpy as np
    p = np.asarray(raw)
    if p.shape != (1, 3549, 85) or not np.isfinite(p).all():
        raise ValueError("invalid fixed YOLOX output")
    p = p[0]
    if (np.any(p[:, 4:] < 0) or np.any(p[:, 4:] > 1)):
        raise ValueError("invalid raw YOLOX class scores")
    joint = p[:, 4, None] * p[:, 5:]
    classes = np.argmax(joint, axis=1)
    scores = joint[np.arange(len(p)), classes]
    candidates = np.flatnonzero(scores >= MIN_SCORE)
    order = sorted(candidates.tolist(),
                   key=lambda k: (-float(scores[k]), k))[:160]
    grid, stride = _grid()
    ratio = min(SIZE/W, SIZE/H)
    rw, rh = max(1, round(W*ratio)), max(1, round(H*ratio))
    for k in order:
        with np.errstate(over="ignore", invalid="ignore"):
            center = (p[k, :2] + grid[k]) * stride[k]
            dim = np.exp(p[k, 2:4]) * stride[k]
        if not np.isfinite(center).all() or not np.isfinite(dim).all():
            continue
        xyxy = [
            float(np.clip(center[0]-dim[0]/2, 0, rw)*W/rw),
            float(np.clip(center[1]-dim[1]/2, 0, rh)*H/rh),
            float(np.clip(center[0]+dim[0]/2, 0, rw)*W/rw),
            float(np.clip(center[1]+dim[1]/2, 0, rh)*H/rh),
        ]
        if min(xyxy[2]-xyxy[0], xyxy[3]-xyxy[1]) >= 9:
            return {
                "box": xyxy,
                "score": round(float(scores[k]), 5),
                "unverified_coco_class_index": int(classes[k]),
            }
    return None


def _box_iou(a, b):
    if a is None:
        return 0.
    intersection = (
        max(0., min(a[2], b[2])-max(a[0], b[0])) *
        max(0., min(a[3], b[3])-max(a[1], b[1]))
    )
    area_a = (a[2]-a[0])*(a[3]-a[1])
    area_b = (b[2]-b[0])*(b[3]-b[1])
    return intersection/(area_a+area_b-intersection)


def run(annotation_path: Path, model_path: Path):
    import cv2
    import numpy as np
    import onnxruntime as ort
    from PIL import Image

    cv2.setNumThreads(1)
    cv2.setRNGSeed(0)
    blob = annotation_path.read_bytes()
    cases, data, earlier_sizes = _fifth_cohort(blob)
    validate_model_file(model_path)
    ann_by_id = defaultdict(list)
    for a in data["annotations"]:
        ann_by_id[a["image_id"]].append(a)
    opt = ort.SessionOptions()
    opt.intra_op_num_threads = 1
    opt.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=opt, providers=["CPUExecutionProvider"]
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].shape != [1, 3549, 85]
            or session.get_outputs()[0].name != "output"):
        raise ValueError("unsupported pinned YOLOX ONNX interface")

    all_rows = []
    start = time.perf_counter()
    for i, case in enumerate(cases):
        label_for_scoring = list(CATEGORIES)[i//2] if i < 10 else "target_free"
        jpeg = _official_jpeg(case)
        with Image.open(BytesIO(jpeg)) as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        if rgb.shape[:2] != (case.height, case.width):
            raise ValueError("untrusted image dimensions")
        scale = min(1., MAX_FRAME/max(case.width, case.height))
        w = max(2, round(case.width*scale))
        h = max(2, round(case.height*scale))
        small = (cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)
                 if scale < 1 else rgb)
        # All selection and segmentation must precede ground truth lookup.
        input_tensor = prepare_image(jpeg, mode="original")
        pred = session.run(None, {"images": input_tensor})[0]
        top = _top1_proposal(pred, case.width, case.height)
        row = {
            "image_id": case.image_id,
            "label_for_scoring_only": label_for_scoring,
            "candidate_count": int(top is not None),
            "top_80_unverified_candidate": top,
            "top1_roi_shape": "unknown",
            "top1_roi_colors": [],
            "top1_segmentation_ms_host": None,
            "ground_truth_used_to_choose_proposal": False,
        }
        mask = None
        if top is not None:
            trial, mask, trial_frame = grabcut_rectangle(rgb, top["box"])
            if trial_frame.shape != small.shape:
                raise ValueError("preprocessing geometry mismatch")
            row["top1_status"] = trial["status"]
            row["top1_segmentation_ms_host"] = trial.get("grabcut_ms")
            desc = trial.get("descriptor")
            if desc:
                row["top1_roi_shape"] = desc["shape"]
                row["top1_roi_colors"] = desc["colors"][:3]
        else:
            row["top1_status"] = "no_candidate"
        if label_for_scoring != "target_free":
            gt, ground_box = _polygon_mask(
                ann_by_id[case.image_id], label_for_scoring,
                case.width, case.height, w, h,
            )
            if gt is None or np.count_nonzero(gt) < 40:
                row["gt_status"] = "no_polygon_gt"
            else:
                # Oracle mode is a research control, not a real detector.
                oracle, oracle_mask, oracle_frame = grabcut_rectangle(
                    rgb, ground_box,
                )
                if oracle_frame.shape != small.shape:
                    raise ValueError("oracle geometry mismatch")
                ground_features = describe_mask(small, gt)
                oracle_features = oracle.get("descriptor", {})
                gt_colors = ground_features.get("colors", [])
                oracle_colors = oracle_features.get("colors", [])
                row.update({
                    "gt_status": "evaluated",
                    "oracle_mask_iou": (
                        round(mask_iou(oracle_mask, gt), 4)
                        if oracle_mask is not None else None
                    ),
                    "gt_shape": ground_features.get("shape", "unknown"),
                    "oracle_shape": oracle_features.get("shape", "unknown"),
                    "gt_top_color": gt_colors[0]["name"] if gt_colors else None,
                    "oracle_top_color": (
                        oracle_colors[0]["name"] if oracle_colors else None
                    ),
                    "oracle_color_agreement": (
                        oracle_colors[0]["name"] == gt_colors[0]["name"]
                        if gt_colors and oracle_colors else None
                    ),
                    "oracle_segmentation_ms_host": oracle.get("grabcut_ms"),
                    "top1_bbox_iou_to_gt_for_scoring": round(
                        _box_iou(top["box"] if top else None, ground_box), 4
                    ),
                    "top1_mask_iou_to_gt_for_scoring": (
                        round(mask_iou(mask, gt), 4) if mask is not None else None
                    ),
                })
        else:
            row["gt_status"] = "target_free_not_object_free"
        all_rows.append(row)

    rows = [r for r in all_rows if r["gt_status"] == "evaluated"]
    oracle_mask_iou = [
        r["oracle_mask_iou"] for r in rows if r["oracle_mask_iou"] is not None
    ]
    colors = [r["oracle_color_agreement"] for r in rows
              if r["oracle_color_agreement"] is not None]
    balls = [r for r in rows if r["label_for_scoring_only"] == "sports_ball"]
    costs = [r["top1_segmentation_ms_host"] for r in all_rows
             if r["top1_segmentation_ms_host"] is not None]
    sorted_costs = sorted(costs)
    p95 = sorted_costs[math.ceil(0.95*len(costs))-1] if costs else None
    top_hits = sum(r["top1_bbox_iou_to_gt_for_scoring"] >= 0.5 for r in rows)
    ball_hits = sum(
        r["top1_bbox_iou_to_gt_for_scoring"] >= 0.5 for r in balls
    )
    ball_round = sum(
        r["gt_shape"] == "round_like" and r["oracle_shape"] == "round_like"
        for r in balls
    )
    criteria = {
        "min_nine_polygon_gt": len(rows) >= 9,
        "min_seven_oracle_mask_IoU50_55": (
            len(oracle_mask_iou) >= 9
            and sum(v >= 0.55 for v in oracle_mask_iou) >= 7
        ),
        "min_seven_color_cases_and_60pct_agreement": (
            len(colors) >= 7 and sum(colors)/len(colors) >= 0.60
        ),
        "min_one_of_two_oracle_balls_round": len(balls) == 2 and ball_round >= 1,
        "median_single_segmentation_at_most_20ms_host": (
            bool(costs) and statistics.median(costs) <= 20
        ),
        "p95_single_segmentation_at_most_100ms_host": (
            p95 is not None and p95 <= 100
        ),
        "top1_detector_at_least_six_of_ten_gt": top_hits >= 6,
        "top1_detector_at_least_one_of_two_balls": ball_hits >= 1,
    }
    pass_gate = all(criteria.values())
    return {
        "status": "light_host_gate_passed" if pass_gate else "light_host_gate_failed",
        "study": COHORT,
        "predeclared_gate_passed": pass_gate,
        "predeclared_criteria_passed_individually": criteria,
        "image_count": len(all_rows),
        "prior_disjoint_cohort_sizes": earlier_sizes,
        "selected_image_ids": [x.image_id for x in cases],
        "annotation_sha256": ANNOTATIONS_SHA256,
        "unchanged_yolox_model_sha256": MODEL_SHA256,
        "unchanged_yolox_score_threshold": MIN_SCORE,
        "GT_polygon_available_cases": len(rows),
        "oracle_mask_IoU_median": (
            round(statistics.median(oracle_mask_iou), 4)
            if oracle_mask_iou else None
        ),
        "oracle_mask_IoU_ge_055": sum(x >= 0.55 for x in oracle_mask_iou),
        "oracle_color_agreement": {
            "matches": sum(colors), "cases_with_both_colors": len(colors)
        },
        "oracle_balls_round": ball_round,
        "top1_boxes_IoU50_to_targets": top_hits,
        "top1_boxes_IoU50_to_balls": ball_hits,
        "single_roi_segmentation_host_ms": {
            "median": round(statistics.median(costs), 3) if costs else None,
            "p95_nearest_rank": round(p95, 3) if p95 is not None else None,
            "max": round(max(costs), 3) if costs else None,
        },
        "model_inference_times_not_part_of_segmentation_ms": True,
        "candidate_source": "top1_of_all_80_yolox_categories_not_GT",
        "oracle_uses_GT_box_not_a_deployable_detector": True,
        "GT_used_only_for_evaluation": True,
        "negative_cases_target_free_not_empty": True,
        "generic_object_false_positive_rate_known": False,
        "source_pixels_archived": False,
        "actual_robot_or_NPU_validated": False,
        "new_model_count": 0,
        "new_onnx_or_oem_changes": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
        "qwen_calls": 0,
        "host_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "host_total_wall_s": round(time.perf_counter()-start, 3),
        "cases": all_rows,
    }


if __name__ == "__main__":
    result = run(Path(os.environ["COCO_VAL_ANNOTATIONS"]),
                 Path(os.environ["YOLOX_MODEL"]))
    Path(os.environ["LIGHT_GRABCUT_RESULT"]).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(result, separators=(",", ":"), allow_nan=False))
