"""PER-P4: three pinned Ultralytics nano models, 300 held-out licensed COCO photos.

Public host-only observation, not a robot/RKNN validation. No media/model files
published; one GT-guided selection before model inference, no tuning on results.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import time

from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, COCO_IDS, CocoCase, Box,
    IMAGE_HOST, MAX_COCO_JSON_BYTES, PHOTO_LICENSE_NAME, PHOTO_LICENSE_URL,
    _official_jpeg,
)
from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint

STUDY = "per_p4_public_coco300_yolo26_20261030"
SEED = "per-p4-300-20261030"
COHORT_PER_CLASS = 40
COHORT_NEGATIVES = 100
MAX_COCO_PHOTOS = 300
CLASSES = ("person", "cat", "dog", "sports_ball", "chair")
SELECTION_ORDER = ("cat", "dog", "sports_ball", "chair", "person")
PRIORITY = ("person", "cat", "dog", "sports_ball")
WEIGHT_DIGESTS = {
    "yolo11n.pt": "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
    "yolo26n.pt": "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef",
    "yolo26n-seg.pt": "361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f",
}
SCORE = 0.25
NMS_IOU = 0.50
MATCH_IOU = 0.50
IMG_SIZE = 640
MAX_DET = 100
MIN_PRIORITY_REGION_RECALL = .75
SEG_GAIN_MARGIN = .05
MIN_SEG_BOX_BETTER_RATE = .60


@dataclass(frozen=True)
class Photo:
    image_id: int
    filename: str
    width: int
    height: int
    target_annotations: tuple[dict, ...]
    target_cohort: str


def fixed_order(image_ids: set[int] | list[int]) -> list[int]:
    return sorted(image_ids, key=lambda i: (hashlib.sha256(f"{SEED}:{i}".encode()).digest(), i))


def photo_is_control(annotations: tuple[dict, ...] | list[dict]) -> bool:
    return not any(int(a["category_id"]) in COCO_IDS.values() for a in annotations)


def select_photos(blob: bytes) -> tuple[Photo, ...]:
    """Frozen selection: exclude every earlier COCO image, never use model scores."""
    if not isinstance(blob, bytes) or len(blob) > MAX_COCO_JSON_BYTES:
        raise ValueError("COCO annotation bytes invalid")
    if hashlib.sha256(blob).hexdigest() != ANNOTATIONS_SHA256:
        raise ValueError("COCO annotation SHA256 differs from the pinned source")
    eighth, data, sizes, previously_seen = eighth_disjoint(blob)
    excluded = set(previously_seen) | {case.image_id for case in eighth}
    if len(excluded) != 132 or sizes != [24, 24, 18, 12, 12, 12, 12]:
        raise ValueError("historical COCO cohorts changed")
    names = {a["id"]: a["name"] for a in data["categories"]}
    if any(names.get(cid) != category.replace("_", " ") for category, cid in COCO_IDS.items()):
        raise ValueError("COCO categories changed")
    valid_licenses = {entry["id"] for entry in data["licenses"]
                      if entry.get("name") == PHOTO_LICENSE_NAME
                      and entry.get("url") in (PHOTO_LICENSE_URL, PHOTO_LICENSE_URL.replace("http:", "https:"))}
    allowed: dict[int, dict] = {}
    for row in data["images"]:
        image_id = row.get("id")
        if (isinstance(image_id, int) and image_id not in excluded
                and row.get("license") in valid_licenses
                and row.get("file_name") == f"{image_id:012d}.jpg"
                and isinstance(row.get("width"), int) and 32 <= row["width"] <= 4096
                and isinstance(row.get("height"), int) and 32 <= row["height"] <= 4096):
            allowed[image_id] = row
    by_image: dict[int, list[dict]] = defaultdict(list)
    invalid = set()
    target_ids = set(COCO_IDS.values())
    for ann in data["annotations"]:
        image_id = ann.get("image_id")
        if image_id not in allowed or ann.get("category_id") not in target_ids:
            continue
        bbox = ann.get("bbox")
        if (ann.get("iscrowd", 0) != 0 or not isinstance(bbox, list)
                or len(bbox) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in bbox)
                or bbox[2] <= 0 or bbox[3] <= 0 or "segmentation" not in ann):
            invalid.add(image_id)
            continue
        by_image[image_id].append(ann)
    for bad in invalid:
        allowed.pop(bad, None)
    result: list[Photo] = []
    taken = set()
    for category in SELECTION_ORDER:
        cid = COCO_IDS[category]
        eligible = [i for i in fixed_order(set(allowed) - taken)
                    if any(a["category_id"] == cid for a in by_image[i])]
        if len(eligible) < COHORT_PER_CLASS:
            raise ValueError(f"not enough licensed COCO photos: {category}: {len(eligible)}")
        for image_id in eligible[:COHORT_PER_CLASS]:
            row = allowed[image_id]
            result.append(Photo(image_id, row["file_name"], row["width"], row["height"],
                                tuple(by_image[image_id]), category))
            taken.add(image_id)
    eligible = [i for i in fixed_order(set(allowed) - taken) if not by_image[i]]
    if len(eligible) < COHORT_NEGATIVES:
        raise ValueError("not enough target-free licensed COCO controls")
    for image_id in eligible[:COHORT_NEGATIVES]:
        row = allowed[image_id]
        result.append(Photo(image_id, row["file_name"], row["width"], row["height"], (), "target_free"))
        taken.add(image_id)
    if (len(result) != MAX_COCO_PHOTOS or len(taken) != MAX_COCO_PHOTOS
            or excluded.intersection(taken)
            or [sum(p.target_cohort == category for p in result) for category in CLASSES] != [40] * 5
            or sum(p.target_cohort == "target_free" for p in result) != 100
            or any(p.target_cohort == "target_free" and not photo_is_control(p.target_annotations)
                   for p in result)):
        raise ValueError("sample count, class balance or historical disjointness failed")
    return tuple(result)


def box_iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0., x2 - x1) * max(0., y2 - y1)
    aa = max(0., a[2] - a[0]) * max(0., a[3] - a[1])
    bb = max(0., b[2] - b[0]) * max(0., b[3] - b[1])
    return inter / (aa + bb - inter) if aa + bb > inter else 0.


def one_to_one_matches(ground_truth: list[dict], predicted: list[dict], *, correct_category: bool) -> list[tuple[int, int, float]]:
    edges = []
    for g, gt in enumerate(ground_truth):
        for p, pred in enumerate(predicted):
            if correct_category and gt["category"] != pred["category"]:
                continue
            iou = box_iou(gt["box"], pred["box"])
            if iou >= MATCH_IOU:
                edges.append((iou, float(pred["score"]), g, p))
    used_g, used_p, chosen = set(), set(), []
    for iou, score, g, p in sorted(edges, reverse=True):
        if g not in used_g and p not in used_p:
            chosen.append((g, p, iou))
            used_g.add(g)
            used_p.add(p)
    return chosen


def mask_iou(a, b) -> float:
    import numpy as np
    aa = np.asarray(a, dtype=np.bool_)
    bb = np.asarray(b, dtype=np.bool_)
    if aa.shape != bb.shape or aa.ndim != 2:
        raise ValueError("mismatched mask geometry")
    union = np.logical_or(aa, bb).sum()
    return float(np.logical_and(aa, bb).sum() / union) if union else 0.


def get_gt_mask(annotation: dict, height: int, width: int):
    """COCO poly/RLE into independent per-pixel ground truth, not a model input."""
    from pycocotools import mask as mask_api
    segmentation = annotation["segmentation"]
    if isinstance(segmentation, list):
        rles = mask_api.frPyObjects(segmentation, height, width)
        rle = mask_api.merge(rles)
    elif isinstance(segmentation, dict) and isinstance(segmentation.get("counts"), list):
        rle = mask_api.frPyObjects(segmentation, height, width)
    elif isinstance(segmentation, dict):
        rle = segmentation
    else:
        raise ValueError("invalid segmentation label")
    array = mask_api.decode(rle)
    if array.ndim != 2 or array.shape != (height, width):
        raise ValueError("ground truth mask incorrect dimensions")
    return array


def predicted_mask_from_polygon(xy, height: int, width: int):
    """Convert Ultralytics orig-image contour to bitmap; holes not represented."""
    import cv2
    import numpy as np
    mask = np.zeros((height, width), dtype=np.uint8)
    pts = np.asarray(xy, dtype=np.float32)
    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 3 or not np.isfinite(pts).all():
        return mask
    # Ultralytics Results.masks.xy uses original-image pixel coordinates.
    cv2.fillPoly(mask, [np.rint(pts).astype(np.int32)], 1)
    return mask


def rectangle_mask(box: tuple[float, ...], height: int, width: int):
    import numpy as np
    mask = np.zeros((height, width), dtype=np.uint8)
    x1, y1 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
    x2, y2 = min(width, math.ceil(box[2])), min(height, math.ceil(box[3]))
    if x1 < x2 and y1 < y2:
        mask[y1:y2, x1:x2] = 1
    return mask


def model_predictions(result) -> list[dict]:
    boxes = result.boxes
    if boxes is None:
        raise ValueError("model has no detection head")
    found = []
    for rect, cls, score in zip(boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist()):
        name = result.names[int(cls)].replace(" ", "_")
        if not math.isfinite(float(score)) or any(not math.isfinite(float(v)) for v in rect):
            raise ValueError("nonfinite model output")
        found.append({"box": tuple(map(float, rect)), "category": name, "score": float(score)})
    return found


def selected_gt(photo: Photo) -> list[dict]:
    classes = {v: k for k, v in COCO_IDS.items()}
    gt = []
    for a in photo.target_annotations:
        x, y, w, h = a["bbox"]
        rect = (max(0., x), max(0., y), min(photo.width, x + w), min(photo.height, y + h))
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            raise ValueError("invalid clipped COCO target geometry")
        gt.append({"category": classes[a["category_id"]], "box": rect, "ann": a})
    return gt


def new_accumulator() -> dict:
    return {"gt": defaultdict(int), "class_hits": defaultdict(int), "region_hits": defaultdict(int),
            "times_ms": [], "control_target_predictions": 0, "controls_with_target_predictions": 0,
            "mask_evaluable": 0, "mask_iou_ge55": 0, "mask_better_than_predicted_box": 0,
            "mask_iou_sum": 0., "rectangle_iou_sum": 0.}


def record_result(acc: dict, photo: Photo, gt: list[dict], preds: list[dict], result,
                  elapsed_ms: float, *, segmentation: bool) -> None:
    if photo.target_cohort == "target_free":
        if gt:
            raise ValueError("control has target annotations")
        count = sum(p["category"] in CLASSES for p in preds)
        acc["control_target_predictions"] += count
        acc["controls_with_target_predictions"] += int(count > 0)
    correct = one_to_one_matches(gt, preds, correct_category=True)
    proposals = one_to_one_matches(gt, preds, correct_category=False)
    for obj in gt:
        acc["gt"][obj["category"]] += 1
    for gi, _, _ in correct:
        acc["class_hits"][gt[gi]["category"]] += 1
    for gi, pi, _ in proposals:
        acc["region_hits"][gt[gi]["category"]] += 1
        if segmentation:
            if result.masks is None or len(result.masks.xy) != len(preds):
                raise ValueError("segmentation model produced missing masks")
            gm = get_gt_mask(gt[gi]["ann"], photo.height, photo.width)
            pm = predicted_mask_from_polygon(result.masks.xy[pi], photo.height, photo.width)
            rm = rectangle_mask(preds[pi]["box"], photo.height, photo.width)
            miou, riou = mask_iou(gm, pm), mask_iou(gm, rm)
            acc["mask_evaluable"] += 1
            acc["mask_iou_ge55"] += int(miou >= .55)
            acc["mask_better_than_predicted_box"] += int(miou > riou)
            acc["mask_iou_sum"] += miou
            acc["rectangle_iou_sum"] += riou
    acc["times_ms"].append(elapsed_ms)


def round_pct(a: int, b: int) -> float | None:
    return round(a/b, 4) if b else None


def summarize_model(acc: dict, model_sha256: str) -> dict:
    gt = dict(acc["gt"])
    primary_gt = sum(gt.get(c, 0) for c in PRIORITY)
    primary_region = sum(acc["region_hits"].get(c, 0) for c in PRIORITY)
    primary_class = sum(acc["class_hits"].get(c, 0) for c in PRIORITY)
    nmask = acc["mask_evaluable"]
    times = sorted(acc["times_ms"])
    if len(times) != 300:
        raise ValueError("incomplete model evaluation")
    return {
        "weights_sha256": model_sha256,
        "photos_evaluated": len(times),
        "gt_instances_by_class": gt,
        "correct_category_iou50_by_class": {k: acc["class_hits"].get(k, 0) for k in CLASSES},
        "class_agnostic_region_iou50_by_class": {k: acc["region_hits"].get(k, 0) for k in CLASSES},
        "primary_instance_count": primary_gt,
        "primary_class_recall_iou50": round_pct(primary_class, primary_gt),
        "primary_region_recall_iou50": round_pct(primary_region, primary_gt),
        "chair_region_recall_iou50": round_pct(acc["region_hits"].get("chair", 0), gt.get("chair", 0)),
        "target_named_predictions_in_100_annotation_target_free_controls": acc["control_target_predictions"],
        "control_photos_with_target_named_prediction": acc["controls_with_target_predictions"],
        "mask_evaluable_instances": nmask,
        "mask_iou_ge55_count": acc["mask_iou_ge55"],
        "mask_better_than_predicted_box_count": acc["mask_better_than_predicted_box"],
        "mask_better_than_predicted_box_fraction": round_pct(acc["mask_better_than_predicted_box"], nmask),
        "mean_mask_iou": round(acc["mask_iou_sum"] / nmask, 4) if nmask else None,
        "mean_rectangle_iou": round(acc["rectangle_iou_sum"] / nmask, 4) if nmask else None,
        "host_cpu_predict_wall_p50_ms": round(statistics.median(times), 3),
        "host_cpu_predict_wall_p95_ms": round(times[math.ceil(.95*len(times))-1], 3),
    }


def decide(reports: dict[str, dict]) -> dict:
    eligible = {name: d for name, d in reports.items()
                if d["primary_region_recall_iou50"] is not None
                and d["primary_region_recall_iou50"] >= MIN_PRIORITY_REGION_RECALL}
    if not eligible:
        return {"status": "insufficient", "recommended_for_low_camera_study": None,
                "reason": "no_model_met_predeclared_primary_region_recall"}
    max_recall = max(d["primary_region_recall_iou50"] for d in eligible.values())
    seg_name = "yolo26n-seg.pt"
    seg = eligible.get(seg_name)
    if (seg and seg["primary_region_recall_iou50"] >= max_recall - SEG_GAIN_MARGIN
            and seg["mask_evaluable_instances"] > 0
            and seg["mask_better_than_predicted_box_fraction"] >= MIN_SEG_BOX_BETTER_RATE):
        chosen = seg_name
        reason = "segmenter_near_best_region_recall_and_mask_better_than_rectangle"
    else:
        detector_options = {k: v for k, v in eligible.items() if k != seg_name}
        if not detector_options:
            return {"status": "insufficient", "recommended_for_low_camera_study": None,
                    "reason": "seg_only_eligible_but_mask_gain_not_sufficient"}
        chosen = max(sorted(detector_options), key=lambda k: detector_options[k]["primary_region_recall_iou50"])
        reason = "highest_primary_region_recall_without_qualifying_segmentation_gain"
    return {"status": "pc_public_candidate_only", "recommended_for_low_camera_study": chosen, "reason": reason}


def verified_weights(folder: Path) -> dict[str, Path]:
    files = {}
    for filename, wanted in WEIGHT_DIGESTS.items():
        path = folder / filename
        if path.is_symlink() or not path.is_file() or not 1_000_000 <= path.stat().st_size <= 15_000_000:
            raise ValueError("missing/non-regular model weights: " + filename)
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != wanted:
            raise ValueError("model weight SHA256 mismatch: " + filename)
        files[filename] = path
    return files


def run(*, annotations_path: Path, weights_dir: Path) -> dict:
    import numpy as np
    import torch
    import ultralytics
    from ultralytics import YOLO
    if ultralytics.__version__ != "8.4.190":
        raise ValueError("unreviewed Ultralytics package version")
    if (annotations_path.is_symlink() or not annotations_path.is_file()
            or not 128 <= annotations_path.stat().st_size <= MAX_COCO_JSON_BYTES):
        raise ValueError("invalid annotation file")
    photos = select_photos(annotations_path.read_bytes())
    weights = verified_weights(weights_dir)
    torch.set_num_threads(2)
    np.random.seed(0)
    models, accumulators = {}, {}
    blank = np.zeros((640, 640, 3), dtype=np.uint8)
    for filename, path in weights.items():
        model = YOLO(str(path))
        want_segment = filename.endswith("-seg.pt")
        if (model.task == "segment") != want_segment:
            raise ValueError("model task mismatch")
        labels = {name.replace(" ", "_") for name in model.names.values()}
        if not set(CLASSES).issubset(labels):
            raise ValueError("unexpected COCO class names")
        # Same warmup, excluded from the 300 real-image timings and results.
        model.predict(source=blank, imgsz=IMG_SIZE, conf=SCORE, iou=NMS_IOU,
                      max_det=MAX_DET, device="cpu", verbose=False)
        models[filename] = model
        accumulators[filename] = new_accumulator()
    for index, photo in enumerate(photos, 1):
        case = CocoCase(photo.image_id, photo.filename, photo.width, photo.height,
                        tuple(Box({v:k for k,v in COCO_IDS.items()}[a["category_id"]],
                                  (a["bbox"][0], a["bbox"][1],
                                   a["bbox"][0]+a["bbox"][2],
                                   a["bbox"][1]+a["bbox"][3]))
                              for a in photo.target_annotations))
        raw = _official_jpeg(case)
        from PIL import Image
        with Image.open(BytesIO(raw)) as opened:
            rgb = opened.convert("RGB")
        gt = selected_gt(photo)
        for filename, model in models.items():
            start = time.perf_counter()
            outputs = model.predict(source=rgb, imgsz=IMG_SIZE, conf=SCORE,
                                    iou=NMS_IOU, max_det=MAX_DET, device="cpu", verbose=False)
            ms = (time.perf_counter() - start) * 1000.
            if len(outputs) != 1:
                raise ValueError("expected one image per prediction")
            res = outputs[0]
            preds = model_predictions(res)
            record_result(accumulators[filename], photo, gt, preds, res, ms,
                          segmentation=filename.endswith("-seg.pt"))
        if index % 50 == 0:
            print(json.dumps({"completed_photos": index, "expected": MAX_COCO_PHOTOS}), flush=True)
        del raw, rgb
    reports = {filename: summarize_model(accumulators[filename], WEIGHT_DIGESTS[filename])
               for filename in weights}
    return {
        "study": STUDY, "dataset": "COCO val2017 target-balanced 300, NOT global mAP",
        "annotation_sha256": ANNOTATIONS_SHA256,
        "model_asset_release": "ultralytics/assets@v8.4.0",
        "ultralytics": ultralytics.__version__, "torch": torch.__version__,
        "source_image_count": len(photos),
        "cohort_images": {k: sum(p.target_cohort == k for p in photos) for k in (*CLASSES,"target_free")},
        "selected_image_ids": [p.image_id for p in photos],
        "licence_photos_claim": "Flickr Attribution License / CC BY 2.0 metadata; image licenses not individually audited",
        "license_weights": "AGPL-3.0 or Ultralytics enterprise; no redistribution",
        "robot_or_npu_verified": False, "camera_height_known": False,
        "no_robot_actuation": True, "media_saved": False, "qwen_calls": 0, "sqlite_writes": 0,
        "thresholds_frozen": {"conf": SCORE, "nms_iou": NMS_IOU,
                              "match_box_iou": MATCH_IOU, "imgsz": IMG_SIZE, "max_det": MAX_DET},
        "reports": reports, "decision": decide(reports),
        "linux_host_peak_rss_kib_process_includes_all_models": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="300-public-COCO YOLO nano comparison, host-only")
    ap.add_argument("--approved-public-media", action="store_true")
    ap.add_argument("--annotations", required=True, type=Path)
    ap.add_argument("--weights-dir", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args(argv)
    if not args.approved_public_media:
        ap.error("explicit public media authorization required")
    report = run(annotations_path=args.annotations, weights_dir=args.weights_dir)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({"study": STUDY, "decision": report["decision"],
                      "models": {name: {"region_recall": v["primary_region_recall_iou50"],
                                       "class_recall": v["primary_class_recall_iou50"],
                                       "mask_better": v["mask_better_than_predicted_box_fraction"]}
                                 for name, v in report["reports"].items()}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
