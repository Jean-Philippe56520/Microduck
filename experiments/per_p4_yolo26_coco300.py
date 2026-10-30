"""PER-P4: pinned host-only 300-image paired YOLO nano detector/segmenter study.

Images never touch disk, no capture/robot/SQLite/Qwen, and no runtime model edits.
The labels are COCO val2017 boxes and instance masks, not low-view robot truth.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from io import BytesIO
import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import time

from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, COCO_IDS, PHOTO_LICENSE_NAME, PHOTO_LICENSE_URL,
    MAX_COCO_JSON_BYTES, Box, CocoCase, _official_jpeg,
)
from microduck_companion.cata_yolox_categories import CATEGORIES
from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint

MODEL_SHA256 = {
    "yolo11n.pt": "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
    "yolo26n.pt": "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef",
    "yolo26n-seg.pt": "361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f",
}
LICENSE = "Ultralytics AGPL-3.0 / Enterprise; host-only exploratory comparison"
SEED = "per-p4-300-20261030"
PER_CLASS = 20
NEGATIVES = 200
MATCH_IOU = 0.50
PRIORITY = ("person", "cat", "dog", "sports_ball")
TARGETS = tuple(COCO_IDS)
NUM_IMAGES = 5 * PER_CLASS + NEGATIVES
COCO_IDX = {name: CATEGORIES[name] for name in TARGETS}


@dataclass(frozen=True)
class Target:
    category: str
    xyxy: tuple[float, float, float, float]
    segmentation: object


def _bbox(ann: dict, width: int, height: int) -> tuple[float, float, float, float] | None:
    values = ann.get("bbox")
    if (type(values) is not list or len(values) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
        return None
    x, y, w, h = values
    if w <= 0 or h <= 0:
        return None
    b = (max(0., float(x)), max(0., float(y)),
         min(float(width), float(x + w)), min(float(height), float(y + h)))
    return b if b[2] > b[0] and b[3] > b[1] else None


def select_cases(data: dict, excluded: set[int], *,
                 per_class: int = PER_CLASS, negatives: int = NEGATIVES):
    """Reuses official COCO/CC-BY fields and CocoCase validation; SHA checked by caller."""
    if (type(data) is not dict or type(excluded) is not set
            or any(type(x) is not int for x in excluded)
            or type(per_class) is not int or not 1 <= per_class <= 40
            or type(negatives) is not int or not 1 <= negatives <= 200):
        raise ValueError("invalid cohort request")
    cats = {x["id"]: x["name"] for x in data["categories"]}
    if any(cats.get(cid) != name.replace("_", " ") for name, cid in COCO_IDS.items()):
        raise ValueError("not the expected COCO taxonomy")
    permitted = {
        x["id"] for x in data["licenses"]
        if x.get("name") == PHOTO_LICENSE_NAME
        and x.get("url") in (PHOTO_LICENSE_URL, PHOTO_LICENSE_URL.replace("http:", "https:"))
    }
    if not permitted:
        raise ValueError("no acceptable per-image CC BY licensing")
    images: dict[int, dict] = {}
    for x in data["images"]:
        image_id = x.get("id")
        width, height = x.get("width"), x.get("height")
        if (type(image_id) is not int or image_id in excluded
                or type(width) is not int or type(height) is not int
                or not 32 <= width <= 4096 or not 32 <= height <= 4096
                or x.get("license") not in permitted
                or x.get("file_name") != f"{image_id:012d}.jpg"
                or image_id in images):
            continue
        images[image_id] = x
    by_image: dict[int, list[Target]] = defaultdict(list)
    invalid: set[int] = set()
    by_id = {v: k for k, v in COCO_IDS.items()}
    for ann in data["annotations"]:
        image_id, cid = ann.get("image_id"), ann.get("category_id")
        if image_id not in images or cid not in by_id:
            continue
        meta = images[image_id]
        box = _bbox(ann, meta["width"], meta["height"])
        seg = ann.get("segmentation")
        if ann.get("iscrowd") != 0 or box is None or not seg:
            invalid.add(image_id)
            continue
        by_image[image_id].append(Target(by_id[cid], box, seg))
    for image_id in invalid:
        images.pop(image_id, None)
        by_image.pop(image_id, None)

    def order(ids):
        return sorted(ids, key=lambda i: (hashlib.sha256(
            f"{SEED}:{i}".encode("ascii")).digest(), i))

    picked: list[int] = []
    used: set[int] = set()
    for name in TARGETS:
        choices = order(i for i in images if i not in used
                        and any(gt.category == name for gt in by_image[i]))
        if len(choices) < per_class:
            raise ValueError(f"insufficient licensed target photos for {name}: {len(choices)}")
        picked.extend(choices[:per_class])
        used.update(choices[:per_class])
    empties = order(i for i in images if i not in used and not by_image[i])
    if len(empties) < negatives:
        raise ValueError("insufficient target-free licensed photos")
    picked.extend(empties[:negatives])
    if len(set(picked)) != 5 * per_class + negatives or excluded.intersection(picked):
        raise ValueError("cohort collision")
    cases = []
    for image_id in picked:
        x = images[image_id]
        targets = tuple(by_image[image_id])
        cases.append((CocoCase(
            image_id, x["file_name"], x["width"], x["height"],
            tuple(Box(t.category, t.xyxy) for t in targets)
        ), targets))
    return cases


def box_iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    overlap = max(0., x2-x1) * max(0., y2-y1)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return overlap / (area_a+area_b-overlap) if area_a+area_b > overlap else 0.


def assign(gt: tuple[Target, ...], predictions: list[dict], *,
           class_aware: bool) -> list[tuple[int, int, float]]:
    """One-to-one maximal-score greedy matching. No ground-truth assisted prediction."""
    choices = []
    for gi, target in enumerate(gt):
        for pi, pred in enumerate(predictions):
            if class_aware and target.category != pred["category"]:
                continue
            iou = box_iou(target.xyxy, pred["xyxy"])
            if iou >= MATCH_IOU:
                choices.append((-iou, gi, pi))
    matched_gt, matched_pred, pairs = set(), set(), []
    for negative_iou, gi, pi in sorted(choices):
        if gi in matched_gt or pi in matched_pred:
            continue
        matched_gt.add(gi)
        matched_pred.add(pi)
        pairs.append((gi, pi, -negative_iou))
    return pairs


def mask_scores(seg, predicted_mask, pred_box, width: int, height: int):
    """Compare predicted mask with COCO instance mask and the SAME predicted box."""
    import numpy as np
    from pycocotools import mask as coco_mask
    if isinstance(seg, list):
        rle = coco_mask.merge(coco_mask.frPyObjects(seg, height, width))
    elif isinstance(seg, dict):
        rle = coco_mask.frPyObjects(seg, height, width) if isinstance(
            seg.get("counts"), list) else seg
    else:
        raise ValueError("unexpected COCO mask encoding")
    truth = coco_mask.decode(rle).astype(bool)
    pred = np.asarray(predicted_mask) > 0.5
    if truth.shape != (height, width) or pred.shape != truth.shape:
        raise ValueError("invalid oracle/predicted segmentation geometry")
    x1, y1, x2, y2 = pred_box
    x1, y1 = max(0, math.floor(x1)), max(0, math.floor(y1))
    x2, y2 = min(width, math.ceil(x2)), min(height, math.ceil(y2))
    rectangle = np.zeros_like(truth, dtype=bool)
    rectangle[y1:y2, x1:x2] = True

    def score(a):
        intersection = np.logical_and(a, truth).sum()
        union = np.logical_or(a, truth).sum()
        return float(intersection / union) if union else 0.
    return score(pred), score(rectangle)


def _percentile(nums: list[float], p: float) -> float:
    if not nums:
        raise ValueError("empty timing")
    return sorted(nums)[math.ceil(p*len(nums))-1]


def analyze(model_path: Path, entries, *,
            model_name: str):
    from PIL import Image
    from ultralytics import YOLO
    import numpy as np

    if model_path.name != model_name or model_name not in MODEL_SHA256:
        raise ValueError("unapproved model")
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != MODEL_SHA256[model_name]:
        raise ValueError("unverified model weights")
    model = YOLO(str(model_path))
    if model.task != ("segment" if model_name.endswith("-seg.pt") else "detect"):
        raise ValueError("unexpected YOLO task")
    if any(model.names.get(COCO_IDX[name]) != name.replace("_", " ")
           for name in TARGETS):
        raise ValueError("unexpected COCO label mapping")
    segment = model.task == "segment"
    counter = {name: Counter() for name in TARGETS}
    timing, seg_iou, box_mask_iou = [], [], []
    mask_wins, mask_evaluated = 0, 0
    targetfree_pred_counts = []
    # Warmup does not count as dataset evidence or a speed observation.
    model.predict(Image.new("RGB", (640, 640)), imgsz=640, conf=.25,
                  iou=.50, max_det=100, device="cpu", verbose=False,
                  retina_masks=segment)
    for case, targets, jpeg in entries:
        with Image.open(BytesIO(jpeg)) as img:
            rgb = img.convert("RGB")
            tick = time.perf_counter()
            result = model.predict(rgb, imgsz=640, conf=.25, iou=.50,
                                   max_det=100, device="cpu", verbose=False,
                                   retina_masks=segment)[0]
            timing.append((time.perf_counter()-tick)*1000)
        preds = []
        if result.boxes is not None:
            xyxy = result.boxes.xyxy.cpu().numpy()
            indices = result.boxes.cls.cpu().numpy()
            for coords, idx in zip(xyxy, indices):
                if not np.isfinite(coords).all():
                    raise ValueError("nonfinite prediction")
                n = int(idx)
                name = result.names.get(n)
                if name is None:
                    raise ValueError("unknown predicted class index")
                preds.append({"category": name.replace(" ", "_"),
                              "xyxy": tuple(float(x) for x in coords)})
        known_pairs = assign(targets, preds, class_aware=True)
        region_pairs = assign(targets, preds, class_aware=False)
        paired_gt = {gi for gi, _, _ in known_pairs}
        paired_pred = {pi for _, pi, _ in known_pairs}
        region_gt = {gi for gi, _, _ in region_pairs}
        class_pred_counter = Counter(p["category"] for p in preds)
        for gi, target in enumerate(targets):
            c = counter[target.category]
            c["gt"] += 1
            c["matched_correct"] += gi in paired_gt
            c["matched_region"] += gi in region_gt
        for pi, p in enumerate(preds):
            if p["category"] in counter:
                counter[p["category"]]["pred_target"] += 1
                counter[p["category"]]["unmatched_pred"] += pi not in paired_pred
        if not targets:
            targetfree_pred_counts.append(sum(class_pred_counter[x] for x in TARGETS))
        if segment:
            masks = None if result.masks is None else result.masks.data.cpu().numpy()
            for gi, pi, _ in region_pairs:
                if masks is None or pi >= len(masks):
                    raise ValueError("missing predicted instance mask")
                mi, ri = mask_scores(targets[gi].segmentation, masks[pi],
                                     preds[pi]["xyxy"], case.width, case.height)
                seg_iou.append(mi)
                box_mask_iou.append(ri)
                mask_wins += mi > ri
                mask_evaluated += 1
        del result
    summary = {}
    for name, c in counter.items():
        gt, tp, rp, fp = (c[x] for x in (
            "gt", "matched_correct", "matched_region", "unmatched_pred"
        ))
        summary[name] = {
            "gt_instances": gt, "correct_class_tp": tp,
            "region_tp_any_label": rp, "unmatched_predictions_as_possible_fp": fp,
            "correct_recall": round(tp/gt, 4) if gt else None,
            "region_recall": round(rp/gt, 4) if gt else None,
            "precision_annotated_only": round(tp/(tp+fp), 4) if tp+fp else None,
        }
    key = [counter[x] for x in PRIORITY]
    num = sum(c["gt"] for c in key)
    overall = {
        "priority_gt": num,
        "priority_correct_recall": round(sum(c["matched_correct"] for c in key)/num, 4),
        "priority_region_recall": round(sum(c["matched_region"] for c in key)/num, 4),
        "host_end_to_end_ms_median": round(statistics.median(timing), 2),
        "host_end_to_end_ms_p95": round(_percentile(timing, .95), 2),
        "host_peak_rss_kib_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "targetfree_images": len(targetfree_pred_counts),
        "targetfree_five_class_predictions_total": sum(targetfree_pred_counts),
        "seg_mask_compared_instances": mask_evaluated,
        "seg_mask_mean_iou": round(statistics.mean(seg_iou), 4) if seg_iou else None,
        "same_box_rectangle_mean_iou": round(statistics.mean(box_mask_iou), 4) if box_mask_iou else None,
        "seg_mask_better_than_rectangle_fraction": round(mask_wins/mask_evaluated, 4)
        if mask_evaluated else None,
    }
    del model
    gc.collect()
    return {"model": model_name, "model_sha256": MODEL_SHA256[model_name],
            "classes": summary, "summary": overall}


def run(annotations_path: Path, weights_dir: Path) -> dict:
    from ultralytics import __version__ as ultralytics_version
    if ultralytics_version != "8.4.192":
        raise ValueError("unverified ultralytics runtime")
    raw = annotations_path.read_bytes()
    if not 128 <= len(raw) <= MAX_COCO_JSON_BYTES or hashlib.sha256(raw).hexdigest() != ANNOTATIONS_SHA256:
        raise ValueError("COCO GT hash mismatch")
    historical, data, _, prior = eighth_disjoint(raw)
    excluded = set(prior).union(x.image_id for x in historical)
    if len(excluded) != 132:
        raise ValueError("historical cohort mismatch")
    cases = select_cases(data, excluded)
    if len(cases) != NUM_IMAGES or len(set(c.image_id for c, _ in cases)) != NUM_IMAGES:
        raise ValueError("cohort cardinality mismatch")
    entries = [(case, gt, _official_jpeg(case)) for case, gt in cases]
    ids = [case.image_id for case, _, _ in entries]
    results = []
    for name in MODEL_SHA256:
        results.append(analyze(weights_dir/name, entries, model_name=name))
    del entries
    return {
        "study": "PER-P4_300_COCO2017_val", "robot": "Kwipi",
        "images": NUM_IMAGES, "target_per_class": PER_CLASS, "targetfree": NEGATIVES,
        "excluded_historical_image_ids": len(excluded),
        "overlap_historical_ids": len(set(ids)&excluded),
        "ids": ids, "coco_annotations_sha256": ANNOTATIONS_SHA256,
        "model_asset_release": "ultralytics/assets@v8.4.0",
        "ultralytics_version": ultralytics_version, "model_rights": LICENSE,
        "input_size": 640, "confidence": .25, "iou_nms_argument": .50,
        "image_license_required": "Flickr CC BY 2.0 (per COCO record)",
        "camera_height_verified": False, "independent_physical_scenes_verified": False,
        "actual_RK3566_or_NPU_test": False, "robot_motion": False,
        "private_media_saved": False, "memory_writes": 0, "qwen_calls": 0,
        "source": "COCO val2017, CC BY 4.0 annotations, official original JPEG URL",
        "results": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--weights-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    report = run(args.annotations, args.weights_dir)
    args.report.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2),
                           encoding="utf-8")
    print(json.dumps({"images": report["images"], "results": [
        {"model": x["model"], "classes": x["classes"], "summary": x["summary"]}
        for x in report["results"]]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
