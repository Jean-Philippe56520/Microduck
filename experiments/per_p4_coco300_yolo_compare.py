"""PER-P4: frozen 300-image public COCO comparison of three official nano YOLOs.

Host-only; no robot, camera, Qwen, memory, actuator, new YOLO implementation,
or persisted media. Reject reused COCO IDs and unauthorized source images.
This is not an evaluation on Microduck's low physical camera.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import time

from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, COCO_IDS, CocoCase, MAX_COCO_JSON_BYTES,
    PHOTO_LICENSE_NAME, PHOTO_LICENSE_URL, _official_jpeg,
)
from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint

STUDY = "PER-P4-coco300-20261030"
MODEL_NAMES = ("yolo11n.pt", "yolo26n.pt", "yolo26n-seg.pt")
TARGETS = ("person", "cat", "dog", "sports_ball", "chair")
PRIORITY = TARGETS[:4]
PER_TARGET = 30
CONTROLS = 150
TOTAL = 300
SEED = "per-p4-300-20261030"
SCORE = 0.25
NMS = 0.50
MATCH = 0.50
SIZE = 640
MAX_DETECTIONS = 100
MAX_IMAGE_BYTES = 2_500_000
# COCO categories sorted by numeric ID; Ultralytics uses contiguous 0..79.
COCO_INDEX = {"person": 0, "cat": 15, "dog": 16,
              "sports_ball": 32, "chair": 56}


@dataclass(frozen=True)
class Case:
    image_id: int
    filename: str
    width: int
    height: int
    annotations: tuple[dict, ...]
    assigned_group: str


def box_iou(a, b):
    """Axis-aligned xyxy IoU; scores are never inferred from labels."""
    ax1, ay1, ax2, ay2 = map(float, a)
    bx1, by1, bx2, by2 = map(float, b)
    if not all(math.isfinite(x) for x in (*a, *b)):
        raise ValueError("non-finite box")
    intersection = max(0.0, min(ax2, bx2)-max(ax1, bx1)) * max(
        0.0, min(ay2, by2)-max(ay1, by1))
    aa = max(0.0, ax2-ax1)*max(0.0, ay2-ay1)
    bb = max(0.0, bx2-bx1)*max(0.0, by2-by1)
    return intersection/(aa+bb-intersection) if aa+bb > intersection else 0.0


def match_predictions(predictions, ground_truth, *, class_aware):
    """Greedy one-to-one, deterministic descending confidence matching."""
    matched = {}
    available = set(range(len(ground_truth)))
    for pred_index in sorted(range(len(predictions)),
                             key=lambda i: (-predictions[i]["confidence"], i)):
        pred = predictions[pred_index]
        options = []
        for gt_index in available:
            gt = ground_truth[gt_index]
            if class_aware and pred["category_id"] != gt["category_id"]:
                continue
            overlap = box_iou(pred["box"], gt["box"])
            if overlap >= MATCH:
                options.append((overlap, gt_index))
        if options:
            _, gt_index = max(options, key=lambda x: (x[0], -x[1]))
            matched[gt_index] = pred_index
            available.remove(gt_index)
    return matched


def select_300(data, excluded_ids):
    """SHA-order case selection fixed before ANY model inference.

    Controls have no GT for five interest categories, NOT necessarily empty.
    Photo rights are declared by COCO metadata, not independently re-licensed.
    """
    if type(data) is not dict or type(excluded_ids) is not set:
        raise ValueError("invalid selection inputs")
    licenses = set()
    for x in data["licenses"]:
        if (x.get("name") == PHOTO_LICENSE_NAME and
                x.get("url") in (
                    PHOTO_LICENSE_URL, PHOTO_LICENSE_URL.replace("http:", "https:")
                )):
            licenses.add(x["id"])
    if not licenses:
        raise ValueError("no approved Flickr CC BY records")
    images = {}
    for img in data["images"]:
        i, w, h = img.get("id"), img.get("width"), img.get("height")
        if (type(i) is int and i not in excluded_ids and
                img.get("license") in licenses and
                type(w) is int and 32 <= w <= 4096 and
                type(h) is int and 32 <= h <= 4096 and
                img.get("file_name") == f"{i:012d}.jpg"):
            images[i] = img
    if not images:
        raise ValueError("no eligible COCO images")
    target_ids = set(COCO_IDS.values())
    anns = defaultdict(list)
    rejected_ids = set()
    for a in data["annotations"]:
        image_id = a.get("image_id")
        if image_id not in images:
            continue
        if a.get("category_id") not in target_ids:
            continue
        if a.get("iscrowd", 0):
            rejected_ids.add(image_id)
            continue
        b = a.get("bbox")
        if (not isinstance(b, list) or len(b) != 4 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in b)
                or b[2] <= 0 or b[3] <= 0):
            rejected_ids.add(image_id)
            continue
        x, y, w, h = map(float, b)
        image = images[image_id]
        clipped = [max(0.0, x), max(0.0, y),
                   min(image["width"]*1.0, x+w),
                   min(image["height"]*1.0, y+h)]
        if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
            rejected_ids.add(image_id)
            continue
        if not a.get("segmentation"):
            rejected_ids.add(image_id)
            continue
        anns[image_id].append({
            "category_id": a["category_id"],
            "box": clipped, "segmentation": a["segmentation"],
        })
    available = set(images)-rejected_ids
    used = set()
    cases = []

    def ordered(ids):
        return sorted(ids, key=lambda i: (
            hashlib.sha256(f"{SEED}:{i}".encode("ascii")).digest(), i))

    for name in TARGETS:
        choices = ordered(i for i in available-used
                          if any(a["category_id"] == COCO_IDS[name] for a in anns[i]))
        if len(choices) < PER_TARGET:
            raise ValueError(f"insufficient licensed COCO cases for {name}: {len(choices)}")
        for i in choices[:PER_TARGET]:
            im = images[i]
            cases.append(Case(i, im["file_name"], im["width"], im["height"],
                              tuple(anns[i]), name))
            used.add(i)
    controls = ordered(i for i in available-used if not anns[i])
    if len(controls) < CONTROLS:
        raise ValueError(f"insufficient licensed COCO control images: {len(controls)}")
    for i in controls[:CONTROLS]:
        im = images[i]
        cases.append(Case(i, im["file_name"], im["width"], im["height"],
                          tuple(), "target_free"))
        used.add(i)
    if (len(cases) != TOTAL or len({c.image_id for c in cases}) != TOTAL
            or set(c.image_id for c in cases)&excluded_ids
            or sum(c.assigned_group == "target_free" for c in cases) != CONTROLS):
        raise ValueError("cohort size or independence broken")
    return tuple(cases)


def score_single_image(predictions, case, masks=None):
    """Independent category and spatial ROI recall; mask scored on matched ROIs."""
    gts = case.annotations
    class_matches = match_predictions(predictions, gts, class_aware=True)
    region_matches = match_predictions(predictions, gts, class_aware=False)
    observed = {
        "ground_truth": defaultdict(int),
        "class_hits": defaultdict(int),
        "region_hits": defaultdict(int),
        "predicted_target_boxes": 0,
        "mask_pairs": 0, "mask_better_than_box": 0,
        "mask_iou_sum": 0., "rectangle_iou_sum": 0.,
    }
    by_cat = {v: k for k, v in COCO_IDS.items()}
    for index, gt in enumerate(gts):
        cat = by_cat[gt["category_id"]]
        observed["ground_truth"][cat] += 1
        observed["class_hits"][cat] += int(index in class_matches)
        observed["region_hits"][cat] += int(index in region_matches)
    observed["predicted_target_boxes"] = sum(
        p["category_id"] in by_cat for p in predictions
    ) if case.assigned_group == "target_free" else 0
    if masks is not None:
        from pycocotools import mask as coco_mask
        import numpy as np
        for gt_index, pred_index in region_matches.items():
            gt = gts[gt_index]
            seg = gt["segmentation"]
            if isinstance(seg, list):
                if not seg:
                    continue
                rle = coco_mask.merge(coco_mask.frPyObjects(
                    seg, case.height, case.width))
            elif isinstance(seg, dict):
                if isinstance(seg.get("counts"), list):
                    rle = coco_mask.frPyObjects(seg, case.height, case.width)
                else:
                    rle = seg
            else:
                raise ValueError("unsupported COCO GT segmentation")
            gt_mask = coco_mask.decode(rle).astype(bool)
            if gt_mask.ndim == 3:
                gt_mask = gt_mask.any(axis=2)
            pm = masks[pred_index]
            if pm.shape != (case.height, case.width):
                raise ValueError("predicted mask shape not original resolution")
            pm = pm > 0.5
            intersection = np.logical_and(pm, gt_mask).sum()
            union = np.logical_or(pm, gt_mask).sum()
            mask_iou = float(intersection / union) if union else 0.0
            x1, y1, x2, y2 = predictions[pred_index]["box"]
            x1, y1 = max(0, math.floor(x1)), max(0, math.floor(y1))
            x2, y2 = min(case.width, math.ceil(x2)), min(case.height, math.ceil(y2))
            rec = np.zeros((case.height, case.width), dtype=np.bool_)
            rec[y1:y2, x1:x2] = True
            intersection = np.logical_and(rec, gt_mask).sum()
            union = np.logical_or(rec, gt_mask).sum()
            rectangle_iou = float(intersection / union) if union else 0.0
            observed["mask_pairs"] += 1
            observed["mask_better_than_box"] += int(mask_iou > rectangle_iou)
            observed["mask_iou_sum"] += mask_iou
            observed["rectangle_iou_sum"] += rectangle_iou
    return observed


def score_summary(observations, timings):
    counts = {k: sum(obs[key].get(k, 0) for obs in observations)
              for key in ("ground_truth", "class_hits", "region_hits")
              for k in []}
    categories = {}
    for cat in TARGETS:
        g = sum(o["ground_truth"].get(cat, 0) for o in observations)
        c = sum(o["class_hits"].get(cat, 0) for o in observations)
        r = sum(o["region_hits"].get(cat, 0) for o in observations)
        categories[cat] = {
            "gt_instances": g, "class_hits": c, "region_hits": r,
            "class_recall_iou50": round(c/g, 5) if g else None,
            "region_recall_iou50": round(r/g, 5) if g else None,
        }
    priority_g = sum(categories[cat]["gt_instances"] for cat in PRIORITY)
    priority_r = sum(categories[cat]["region_hits"] for cat in PRIORITY)
    priority_c = sum(categories[cat]["class_hits"] for cat in PRIORITY)
    seg_count = sum(o["mask_pairs"] for o in observations)
    sorted_times = sorted(timings)
    return {
        "categories": categories,
        "priority_ground_truth_instances": priority_g,
        "priority_class_recall_iou50": round(priority_c/priority_g, 5)
            if priority_g else None,
        "priority_region_recall_iou50": round(priority_r/priority_g, 5)
            if priority_g else None,
        "priority_macro_region_recall_iou50": round(statistics.mean(
            categories[cat]["region_recall_iou50"] for cat in PRIORITY), 5),
        "target_class_predictions_on_target_free_controls": sum(
            o["predicted_target_boxes"] for o in observations),
        "mask_pairs_on_region_matched_targets": seg_count,
        "fraction_masks_better_than_rectangles": round(
            sum(o["mask_better_than_box"] for o in observations)/seg_count, 5
        ) if seg_count else None,
        "mean_matched_mask_iou": round(sum(o["mask_iou_sum"] for o in observations)/seg_count, 5)
            if seg_count else None,
        "mean_same_box_rectangle_iou": round(
            sum(o["rectangle_iou_sum"] for o in observations)/seg_count, 5
        ) if seg_count else None,
        "host_inference_wall_p50_ms": round(statistics.median(timings), 3),
        "host_inference_wall_p95_ms": round(
            sorted_times[min(len(timings)-1, math.ceil(.95*len(timings))-1)], 3),
    }


def run(annotation_path: Path):
    import cv2
    import numpy as np
    import ultralytics
    from ultralytics import YOLO

    data_bytes = annotation_path.read_bytes()
    if (not 128 <= len(data_bytes) <= MAX_COCO_JSON_BYTES
            or hashlib.sha256(data_bytes).hexdigest() != ANNOTATIONS_SHA256):
        raise ValueError("COCO annotation SHA256 mismatch")
    old_eighth, data, _, prior_114 = eighth_disjoint(data_bytes)
    excluded = prior_114 | {c.image_id for c in old_eighth}
    if len(excluded) != 132:
        raise ValueError("COCO 132-image history witness mismatch")
    cases = select_300(data, excluded)
    names = [c.name for c in []]  # no label source used to select models
    runtime_models = []
    for filename in MODEL_NAMES:
        model = YOLO(filename)
        actual = Path(model.ckpt_path)
        if not actual.is_file() or actual.stat().st_size > 80_000_000:
            raise ValueError("model checkpoint missing or unusually large")
        model_names = model.names
        for cat in TARGETS:
            if model_names.get(COCO_INDEX[cat]) != cat.replace("_", " "):
                raise ValueError("wrong COCO class order in " + filename)
        runtime_models.append((filename, model, {
            "weight_sha256": hashlib.sha256(actual.read_bytes()).hexdigest(),
            "weight_size_bytes": actual.stat().st_size,
            "name": filename,
        }))
    # Warmup is not scored; actual photo set is evaluated exactly once.
    for _, model, _ in runtime_models:
        model.predict(source=np.zeros((480, 640, 3), dtype=np.uint8),
                      imgsz=SIZE, conf=SCORE, iou=NMS, max_det=MAX_DETECTIONS,
                      device="cpu", retina_masks=True, verbose=False)
    measured = {name: [] for name in MODEL_NAMES}
    timings = {name: [] for name in MODEL_NAMES}
    image_digests = []
    for case in cases:
        image_bytes = _official_jpeg(CocoCase(
            case.image_id, case.filename, case.width, case.height, tuple()
        ))
        image_digests.append(hashlib.sha256(image_bytes).hexdigest())
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8),
                             cv2.IMREAD_COLOR)
        del image_bytes
        if image is None or image.shape[:2] != (case.height, case.width):
            raise ValueError("unexpected image decoding dimensions")
        for filename, model, _ in runtime_models:
            start = time.perf_counter()
            result = model.predict(source=image, imgsz=SIZE, conf=SCORE,
                                   iou=NMS, max_det=MAX_DETECTIONS, device="cpu",
                                   retina_masks=True, verbose=False)[0]
            timings[filename].append((time.perf_counter()-start)*1000)
            boxes = result.boxes
            xyxy = boxes.xyxy.cpu().numpy()
            conf = boxes.conf.cpu().numpy()
            cats = boxes.cls.cpu().numpy()
            preds = [{"box": [float(x) for x in xyxy[j]],
                      "confidence": float(conf[j]),
                      "category_id": int(cats[j])}
                     for j in range(len(boxes))]
            masks = None
            if filename.endswith("-seg.pt"):
                masks = (result.masks.data.cpu().numpy()
                         if result.masks is not None else
                         np.zeros((0, case.height, case.width), dtype=np.float32))
                if len(masks) != len(preds):
                    raise ValueError("segmentation boxes and masks not aligned")
            measured[filename].append(score_single_image(preds, case, masks))
            del result, boxes, xyxy, conf, cats, preds, masks
        del image
    summaries = {name: score_summary(measured[name], timings[name])
                 for name in MODEL_NAMES}
    ranked = sorted(MODEL_NAMES, key=lambda name: (
        summaries[name]["priority_region_recall_iou50"] or 0,
        summaries[name]["priority_class_recall_iou50"] or 0,
    ), reverse=True)
    best = summaries[ranked[0]]["priority_region_recall_iou50"]
    candidate_seg = summaries["yolo26n-seg.pt"]
    eligible = [n for n in ranked if summaries[n]["priority_region_recall_iou50"] >= .75]
    recommended_for_further_low_view_test = None
    if eligible:
        recommended_for_further_low_view_test = eligible[0]
        if (candidate_seg["priority_region_recall_iou50"] >=
                summaries[eligible[0]]["priority_region_recall_iou50"] - .05
                and candidate_seg["fraction_masks_better_than_rectangles"] is not None
                and candidate_seg["fraction_masks_better_than_rectangles"] >= .60
                and candidate_seg["priority_region_recall_iou50"] >= .75):
            recommended_for_further_low_view_test = "yolo26n-seg.pt"
    return {
        "study": STUDY, "status": "public_host_evaluation_only",
        "source": "COCO2017 val; selected Flickr Attribution License CC BY 2.0",
        "image_rights_independently_verified": False,
        "annotation_sha256": ANNOTATIONS_SHA256,
        "excluded_historic_image_ids": len(excluded),
        "new_images_evaluated_per_model": len(cases),
        "selected_image_ids": [c.image_id for c in cases],
        "selected_image_sha256": image_digests,
        "cohorts": {k: sum(c.assigned_group == k for c in cases)
                    for k in (*TARGETS, "target_free")},
        "ultralytics_version": ultralytics.__version__,
        "library_expected": "8.4.60",
        "model_metadata": {name: meta for name, _, meta in runtime_models},
        "threshold": SCORE, "nms_iou": NMS, "image_size": SIZE,
        "results": summaries, "best_region_model_on_this_sample": ranked[0],
        "recommended_for_further_low_view_study": recommended_for_further_low_view_test,
        "host_peak_rss_kib_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "low_view_robot_camera": False, "real_rknn_npu_validated": False,
        "robot_motion_issued": False, "sqlite_writes": 0, "qwen_calls": 0,
        "note": "Target-free controls may contain unannotated target objects; "
                "COCO labels are an incomplete inventory of physical regions. "
                "IoU50 sample recall is NOT official COCO mAP or free-space safety.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotations", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(argv)
    if not a.annotations.is_file():
        raise SystemExit("Missing pinned public COCO annotations")
    report = run(a.annotations)
    a.report.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({
        "images": report["new_images_evaluated_per_model"],
        "best": report["best_region_model_on_this_sample"],
        "further_study": report["recommended_for_further_low_view_study"],
        "priority_region_recall": {
            name: val["priority_region_recall_iou50"]
            for name, val in report["results"].items()
        },
        "public_host_only": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
