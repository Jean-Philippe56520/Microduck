"""VIS-ATT-2: host-only disjoint COCO category-vs-region test.

One frozen YOLOX-Nano inference per photo, two EXISTING decoders, GT only for
scoring. Candidate regions are unverified COCO proposals, not open-set objects.
No media is saved or published, no camera, robotd, Qwen, SQLite or F2 RPC.
"""
from __future__ import annotations

from collections import defaultdict
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import time

from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, COCO_IDS, CATEGORIES, MAX_COCO_JSON_BYTES,
    _official_jpeg, decode_boxes, select_coco_cases,
)
from microduck_companion.cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, prepare_image, validate_model_file,
)
from microduck_companion.perception import DETECTION_CONFIDENCE
from microduck_companion.yolox_attention_candidates import (
    _iou, decode_candidates,
)
from experiments.yolox_candidate_regions_sixth_coco import (
    _all_gt_boxes, _remove_previous_ids,
)

COHORT_SEQUENCE = (
    (4, 4), (4, 4), (3, 3),
    (2, 2), (2, 2), (2, 2), (2, 2),
)
EIGHTH_SPEC = (3, 3)  # 3 each of five categories + 3 target-free controls
SEVENTH_EXPECTED_IDS = (
    477288, 210299, 435299, 554291, 29393, 80153,
    85772, 177065, 325838, 74733, 186938, 496722,
)
MATCH_IOU = .5
K3_MIN_TARGET_HITS = 8
K3_MIN_NONBALL_HITS = 5
MIN_NEW_NONBALL_RESCUES = 1
MAX_UNMATCHED_GT_FRACTION = .70
MAX_POSTPROCESS_P95_MS = 15.


def eighth_disjoint(annotation_blob: bytes):
    """Replay seven historical SHA-order cohorts before selecting new photos.

    The independent 7th published COCO ID roster is an explicit provenance
    witness. No model output is consulted to select the eighth cohort.
    """
    if (type(annotation_blob) is not bytes
            or not 128 <= len(annotation_blob) <= MAX_COCO_JSON_BYTES
            or hashlib.sha256(annotation_blob).hexdigest() != ANNOTATIONS_SHA256):
        raise ValueError("COCO annotation digest or size not pinned")
    data = json.loads(annotation_blob)
    excluded = set()
    sizes = []
    for index, (per_class, negatives) in enumerate(COHORT_SEQUENCE):
        source = (_remove_previous_ids(data, excluded)
                  if excluded else annotation_blob)
        cohort = select_coco_cases(
            source, per_class=per_class, negatives=negatives)
        ids = tuple(item.image_id for item in cohort)
        if len(ids) != 5*per_class+negatives or len(set(ids)) != len(ids):
            raise ValueError("prior COCO cohort has incorrect size")
        if excluded.intersection(ids):
            raise ValueError("prior COCO cohort overlap")
        if index == 6 and ids != SEVENTH_EXPECTED_IDS:
            raise ValueError("seventh cohort does not match committed witness")
        excluded.update(ids)
        sizes.append(len(ids))
    if sizes != [24, 24, 18, 12, 12, 12, 12] or len(excluded) != 114:
        raise ValueError("first seven cohorts not independently disjoint")
    cases = select_coco_cases(
        _remove_previous_ids(data, excluded),
        per_class=EIGHTH_SPEC[0], negatives=EIGHTH_SPEC[1],
    )
    ids = [case.image_id for case in cases]
    if (len(ids) != 18 or len(set(ids)) != 18
            or set(ids).intersection(excluded)):
        raise ValueError("eighth cohort leaked or has wrong size")
    # The selector orders exactly three photos of each known target category
    # and three target-free controls; a control is NOT an empty room.
    for i, name in enumerate(CATEGORIES):
        for sample in cases[i*3:(i+1)*3]:
            if not any(box.category == name for box in sample.ground_truth):
                raise ValueError("eighth GT target missing")
    if any(case.ground_truth for case in cases[15:]):
        raise ValueError("eighth target-free images are not target-free")
    return cases, data, sizes, excluded


def summarize(rows: list[dict]) -> dict:
    """Predeclared metrics, including explicit invalid-data refusal."""
    categories = tuple(CATEGORIES)
    if (type(rows) is not list or len(rows) != 18
            or len({row.get("image_id") for row in rows}) != 18):
        raise ValueError("expected 18 distinct COCO observations")
    for i, row in enumerate(rows):
        name = categories[i // 3] if i < 15 else "target_free"
        if row.get("evaluated_target") != name:
            raise ValueError("target order not frozen")
        if (type(row.get("gt_target_count")) is not int
                or (name == "target_free") != (row["gt_target_count"] == 0)):
            raise ValueError("missing or misclassified independent target GT")
        if (type(row.get("class_correct_hit")) is not bool
                or type(row.get("region_high_confidence_target_hit")) is not bool):
            raise ValueError("invalid class/region control flags")
        if name == "target_free" and (
                row["class_correct_hit"]
                or row["region_high_confidence_target_hit"]):
            raise ValueError("target-free category promoted into a hit")
        hits = [row.get(f"region_k{k}_target_hit") for k in (1, 3, 5)]
        if any(type(x) is not bool for x in hits) or hits != sorted(hits):
            raise ValueError("top1/3/5 region hits must be monotonic")
        if row["region_high_confidence_target_hit"] and not hits[1]:
            raise ValueError("high-confidence hit absent from top3")
        if name == "target_free" and any(hits):
            raise ValueError("target-free image cannot be a target hit")
        count, matched = row.get("top3_candidate_count"), row.get(
            "top3_matched_to_any_coco_annotation")
        if (type(count) is not int or type(matched) is not int
                or not 0 <= matched <= count <= 3):
            raise ValueError("invalid bounded region/annotation count")
        strong = row.get("top3_score_above_f2_mock_threshold_count")
        if type(strong) is not int or not 0 <= strong <= count:
            raise ValueError("unverified region scores misrepresented")

    positives = rows[:15]
    nonball = rows[:12]
    grouped = {}
    for i, name in enumerate(categories):
        selected = positives[i*3:(i+1)*3]
        grouped[name] = {
            "images": len(selected),
            "class_correct_IoU50_images": sum(row["class_correct_hit"]
                                              for row in selected),
            "region_top1_IoU50_images": sum(row["region_k1_target_hit"]
                                           for row in selected),
            "region_top3_IoU50_images": sum(row["region_k3_target_hit"]
                                           for row in selected),
            "region_top5_IoU50_images": sum(row["region_k5_target_hit"]
                                           for row in selected),
            "class_miss_rescued_by_top3_images": sum(
                row["region_k3_target_hit"] and not row["class_correct_hit"]
                for row in selected),
        }
    all_regions = sum(row["top3_candidate_count"] for row in rows)
    matched_gt = sum(row["top3_matched_to_any_coco_annotation"]
                     for row in rows)
    unmatched = (all_regions - matched_gt) / all_regions if all_regions else None
    rescued_nonball = sum(
        row["region_k3_target_hit"] and not row["class_correct_hit"]
        for row in nonball)
    target_hits = sum(row["region_k3_target_hit"] for row in positives)
    nonball_hits = sum(row["region_k3_target_hit"] for row in nonball)
    return {
        "per_category": grouped,
        "target_images": 15,
        "target_free_images": 3,
        "target_images_correct_category_localized": sum(
            row["class_correct_hit"] for row in positives),
        "top1_target_images_localized": sum(
            row["region_k1_target_hit"] for row in positives),
        "top3_target_images_localized": target_hits,
        "top5_target_images_localized": sum(
            row["region_k5_target_hit"] for row in positives),
        "top3_nonball_target_images_localized": nonball_hits,
        "top3_nonball_rescued_from_class_miss": rescued_nonball,
        "top3_nonball_new_value_gate": rescued_nonball >= MIN_NEW_NONBALL_RESCUES,
        "top3_target_recall_gate": target_hits >= K3_MIN_TARGET_HITS
            and nonball_hits >= K3_MIN_NONBALL_HITS,
        "top3_candidates_all_images": all_regions,
        "top3_candidates_matching_any_80class_GT": matched_gt,
        "top3_not_matched_to_80class_GT_NOT_proved_false":
            all_regions-matched_gt,
        "top3_unmatched_annotation_fraction": (
            round(unmatched, 4) if unmatched is not None else None),
        "unmatched_annotation_gate": (
            unmatched is not None and unmatched <= MAX_UNMATCHED_GT_FRACTION),
        "target_free_with_top3_region": sum(
            row["top3_candidate_count"] > 0 for row in rows[15:]),
        "target_free_with_region_eligible_for_mock_F2": sum(
            row["top3_score_above_f2_mock_threshold_count"] > 0
            for row in rows[15:]),
        "high_confidence_region_hit_targets": sum(
            row["region_high_confidence_target_hit"] for row in positives),
        "not_object_free_nor_false_positive_measurement": True,
    }


def evaluate(*, annotation_path: Path, model_path: Path) -> dict:
    import onnxruntime as ort

    if (annotation_path.is_symlink() or not annotation_path.is_file()
            or not 128 <= annotation_path.stat().st_size <= MAX_COCO_JSON_BYTES):
        raise ValueError("missing pinned COCO-val annotations")
    blob = annotation_path.read_bytes()
    cases, annotations, prior_sizes, prior_ids = eighth_disjoint(blob)
    validate_model_file(model_path)

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1
            or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].name != "output"
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise ValueError("YOLOX ONNX contract changed")

    by_id = defaultdict(list)
    for ann in annotations["annotations"]:
        by_id[ann["image_id"]].append(ann)

    rows = []
    cpu_post_ms, cpu_onnx_ms = [], []
    for i, case in enumerate(cases):
        target = list(CATEGORIES)[i//3] if i < 15 else "target_free"
        jpg = _official_jpeg(case)
        prepared = prepare_image(jpg, mode="original")
        start = time.perf_counter()
        raw = session.run(None, {"images": prepared})[0]
        cpu_onnx_ms.append((time.perf_counter()-start)*1000)
        start = time.perf_counter()
        classified = decode_boxes(raw, width=case.width, height=case.height)
        proposals = decode_candidates(
            raw, width=case.width, height=case.height, max_results=5)
        cpu_post_ms.append((time.perf_counter()-start)*1000)
        # None of the independent annotations influence proposal selection.
        full_gt = _all_gt_boxes(by_id[case.image_id], case.width, case.height)
        target_gt = [
            item["xyxy"] for item in full_gt
            if item["category_id"] == COCO_IDS.get(target)
        ] if target != "target_free" else []
        if target != "target_free" and not target_gt:
            raise ValueError("expected frozen target GT missing")
        def match_xy(box) -> bool:
            return bool(target_gt) and any(
                _iou(box, gt) >= MATCH_IOU for gt in target_gt
            )
        class_hit = any(
            x.category == target and match_xy(x.xyxy) for x in classified)
        hits = {
            f"region_k{k}_target_hit": any(
                match_xy(p["xyxy"]) for p in proposals[:k])
            for k in (1, 3, 5)
        }
        high_hit = any(
            p["score"] >= DETECTION_CONFIDENCE and match_xy(p["xyxy"])
            for p in proposals[:3])
        annotation_matched = sum(any(
            _iou(p["xyxy"], g["xyxy"]) >= MATCH_IOU for g in full_gt)
            for p in proposals[:3])
        rows.append({
            "image_id": case.image_id,
            "evaluated_target": target,
            "gt_target_count": len(target_gt),
            "gt_all_80_categories_count": len(full_gt),
            "class_correct_hit": bool(class_hit),
            **hits,
            "region_high_confidence_target_hit": bool(high_hit),
            "top3_candidate_count": len(proposals[:3]),
            "top3_matched_to_any_coco_annotation": annotation_matched,
            "top3_score_above_f2_mock_threshold_count": sum(
                p["score"] >= DETECTION_CONFIDENCE for p in proposals[:3]),
        })
        del jpg, prepared, raw, classified, proposals

    metric = summarize(rows)
    p95 = sorted(cpu_post_ms)[math.ceil(len(cpu_post_ms)*.95)-1]
    gates = {
        "eighth_18_images_new_vs_first_114": (
            len(cases) == 18 and not (
                {x.image_id for x in cases} & prior_ids)),
        "eight_of_fifteen_targets_and_five_of_twelve_nonballs":
            metric["top3_target_recall_gate"],
        "at_least_one_nonball_class_miss_rescued":
            metric["top3_nonball_new_value_gate"],
        "unmatched_COCO_GT_fraction_at_most_point70":
            metric["unmatched_annotation_gate"],
        "combined_postprocessing_p95_host_at_most_15ms":
            p95 <= MAX_POSTPROCESS_P95_MS,
    }
    return {
        "study": "VIS-ATT-2_eighth_disjoint_COCO_category_vs_region",
        "status": "bounded_localization_gain_proved" if all(gates.values())
                  else "insufficient_for_targeted_generalization",
        "predeclared_gates": gates,
        "predeclared_gate_met": all(gates.values()),
        "images": len(cases),
        "previous_cohort_sizes": prior_sizes,
        "excluded_previous_COCO_image_ids_count": len(prior_ids),
        "selected_image_ids": [c.image_id for c in cases],
        "annotation_sha256": ANNOTATIONS_SHA256,
        "model_sha256": MODEL_SHA256,
        "fixed_yolox_joint_score": MIN_SCORE,
        "fixed_bbox_iou": MATCH_IOU,
        "f2_mock_threshold_not_used_to_change_detection": DETECTION_CONFIDENCE,
        "ground_truth_only_used_after_both_decoders": True,
        "one_onnx_inference_per_image": True,
        "cohort_disjoint_does_not_prove_independent_physical_scenes": True,
        "coco_target_free_not_object_free": True,
        "full_coco_validation_mAP_not_measured": True,
        "physical_robot_mediad_RKNN_or_25cm_not_validated": True,
        "source_photos_saved_or_published": False,
        "semantic_unknown_detection_verified": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
        "qwen_calls": 0,
        "inference_host_ms_median": round(statistics.median(cpu_onnx_ms), 3),
        "postprocess_both_decoders_host_ms_p95": round(p95, 3),
        "host_peak_rss_kib_process": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "metrics": metric,
        "rows": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations-path", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-public-media", action="store_true")
    args = parser.parse_args(argv)
    if not args.approved_public_media:
        parser.error("explicit licensed public media authorization required")
    if args.output.exists() or args.output.is_symlink():
        parser.error("refuse to overwrite evaluation report")
    result = evaluate(
        annotation_path=args.annotations_path, model_path=args.model_path)
    text = json.dumps(result, allow_nan=False, sort_keys=True) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(json.dumps(result, allow_nan=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
