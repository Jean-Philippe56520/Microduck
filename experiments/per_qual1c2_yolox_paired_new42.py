"""PER-QUAL-1C2: one YOLOX pass per NEW JPEG, two correlated GT scorings.

Explicitly use COCO category_id for GT and YOLOX 0-based head_idx for
predictions. Source + cohort gates run BEFORE model/JPEG access.
No retraining, no robot, no model/media/IDs published.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import resource
import statistics
import time

from experiments.per80_yolox_coco_public import COCO80_ID_ORDER, Proposal
from experiments.per_qual1_sama_gt_gate import (
    FROZEN_COHORT_SHA256, SEED_C1, SAMPLES_PER_CLASS, TARGETS,
    SourceGateError, _frozen_sha256, _images, _paired_iou50,
    choose_paired_cohort, unpack_sama_archive, validate_dual_class_map,
)
from experiments.per_qual1c1_new42_source import (
    FROZEN_NEW_COHORT_SHA256, NEW_COUNT, TOTAL_EXCLUSIONS, source_gate,
)


def score_double_gt(cases, class_spaces, coco_gt, sama_gt, predictions):
    """The SAME immutable YOLOX outputs are scored twice, never retuned.

    All seven categories are evaluated across all 42 photographs. Each of
    the seven allotted positive subsets must have real GT in BOTH sources.
    """
    if (type(cases) is not tuple or len(cases) != NEW_COUNT
            or len({ident for ident, _ in cases}) != NEW_COUNT
            or {name for _, name in cases} != set(TARGETS)
            or type(predictions) is not dict
            or set(predictions) != {ident for ident, _ in cases}
            or type(class_spaces) is not dict
            or set(class_spaces) != set(TARGETS)
            or type(coco_gt) is not dict or type(sama_gt) is not dict):
        raise SourceGateError("STOP_SCHEMA: incorrect 42-image scoring contract")
    for name in TARGETS:
        domain = class_spaces[name]
        if (type(domain) is not dict
                or set(domain) != {"coco_category_id", "yolox_head_idx"}
                or type(domain["coco_category_id"]) is not int
                or type(domain["yolox_head_idx"]) is not int
                or not 0 <= domain["yolox_head_idx"] < 80
                or COCO80_ID_ORDER[domain["yolox_head_idx"]]
                    != domain["coco_category_id"]):
            raise SourceGateError("STOP_SCHEMA: COCO category_id != YOLOX head index")

    for ident, _ in cases:
        detections = predictions[ident]
        if type(detections) is not tuple:
            raise SourceGateError("STOP_MODEL: incomplete decoded output")
        for pred in detections:
            if (not isinstance(pred, Proposal)
                    or not 0 <= pred.class_idx < 80
                    or not math.isfinite(pred.confidence)
                    or not 0 <= pred.confidence <= 1
                    or len(pred.box) != 4
                    or not all(type(v) in (float, int) and math.isfinite(v)
                               for v in pred.box)
                    or pred.box[2] <= pred.box[0]
                    or pred.box[3] <= pred.box[1]):
                raise SourceGateError("STOP_MODEL: invalid YOLOX proposal")

    report = {}
    for name in TARGETS:
        official_coco_id = class_spaces[name]["coco_category_id"]
        model_head_idx = class_spaces[name]["yolox_head_idx"]
        row = dict(allocated_photos=0, evaluated_photos=NEW_COUNT,
                   gt_coco_boxes=0, gt_sama_boxes=0, proposals=0,
                   matched_coco_iou50=0, matched_sama_iou50=0,
                   unmatched_coco_not_proven_false=0,
                   unmatched_sama_not_proven_false=0)
        for ident, assigned in cases:
            # Critical guard introduced after invalid #301 scoring:
            # NEVER use model_head_idx to look up COCO annotation boxes.
            truth_coco = tuple(coco_gt.get((ident, official_coco_id), ()))
            truth_sama = tuple(sama_gt.get((ident, official_coco_id), ()))
            if assigned == name and (not truth_coco or not truth_sama):
                raise SourceGateError("STOP_SCHEMA: assigned positive GT missing")
            pred_boxes = tuple(p.box for p in predictions[ident]
                               if p.class_idx == model_head_idx)
            match_coco = _paired_iou50(pred_boxes, truth_coco)
            match_sama = _paired_iou50(pred_boxes, truth_sama)
            row["allocated_photos"] += int(assigned == name)
            row["gt_coco_boxes"] += len(truth_coco)
            row["gt_sama_boxes"] += len(truth_sama)
            row["proposals"] += len(pred_boxes)
            row["matched_coco_iou50"] += match_coco
            row["matched_sama_iou50"] += match_sama
            row["unmatched_coco_not_proven_false"] += len(pred_boxes) - match_coco
            row["unmatched_sama_not_proven_false"] += len(pred_boxes) - match_sama
        if (row["allocated_photos"] != SAMPLES_PER_CLASS
                or row["gt_coco_boxes"] < SAMPLES_PER_CLASS
                or row["gt_sama_boxes"] < SAMPLES_PER_CLASS):
            raise SourceGateError("STOP_SCHEMA: silent GT deficit")
        row["recall_coco_iou50"] = round(
            row["matched_coco_iou50"] / row["gt_coco_boxes"], 6)
        row["recall_sama_iou50"] = round(
            row["matched_sama_iou50"] / row["gt_sama_boxes"], 6)
        row["delta_sama_minus_coco"] = round(
            row["recall_sama_iou50"] - row["recall_coco_iou50"], 6)
        report[name] = row
    return report


def _source_and_truth(annotations: Path, sama_zip: Path):
    """Freeze 1274 exclusions, new roster and dual IDs BEFORE model use."""
    verified = source_gate(annotations, sama_zip)
    if (verified["status"] != "NEW_SOURCE_COHORT_SELECTED_NO_INFERENCE"
            or verified["new_cohort_sha256"] != FROZEN_NEW_COHORT_SHA256
            or verified["total_coco_ids_excluded"] != TOTAL_EXCLUSIONS
            or verified["new_selected_photos"] != NEW_COUNT):
        raise SourceGateError("STOP_SOURCE: source gate not passed")
    from experiments.per80_yolox_coco_public import (
        P4_IDS, _cohort_from_pinned_source, _valid_license_ids,
    )
    from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint

    blob = annotations.read_bytes()
    names, old_800, _, _, _ = _cohort_from_pinned_source(blob)
    eighth, original, _, old = eighth_disjoint(blob)
    history = frozenset(old | {x.image_id for x in eighth} | P4_IDS |
                        {case.image_id for case, _ in old_800})
    if len(history) != 1232:
        raise SourceGateError("STOP_SOURCE: historical exclusions drifted")
    sama = unpack_sama_archive(sama_zip.read_bytes())
    rights = _valid_license_ids(original)
    already_used, _, _, _, _ = choose_paired_cohort(
        original, sama, old_ids=history, allowed_license_ids=rights)
    _frozen_sha256("|".join(f"{ident}/{cat}" for ident,cat in already_used).encode(),
                   FROZEN_COHORT_SHA256, "previous 42 consumed")
    historical_1274 = frozenset(history | {ident for ident, _ in already_used})
    if len(historical_1274) != TOTAL_EXCLUSIONS:
        raise SourceGateError("STOP_SOURCE: consumed IDs leaked")
    cases, coco_ids, boxes_coco, boxes_sama, _ = choose_paired_cohort(
        original, sama, old_ids=historical_1274,
        allowed_license_ids=rights, selection_seed=SEED_C1)
    _frozen_sha256("|".join(f"{ident}/{cat}" for ident,cat in cases).encode(),
                   FROZEN_NEW_COHORT_SHA256, "new 42 photo roster")
    mapped = validate_dual_class_map(names, coco_ids, COCO80_ID_ORDER)
    if mapped != verified["class_id_domains"]:
        raise SourceGateError("STOP_SCHEMA: frozen category mappings drifted")
    images = _images(original)
    return verified, cases, mapped, boxes_coco, boxes_sama, images


def benchmark(annotations: Path, sama_zip: Path, *, model_path: Path | None,
              validate_only: bool):
    source, cases, maps, boxes_coco, boxes_sama, images = (
        _source_and_truth(annotations, sama_zip))
    base = dict(experiment="PER-QUAL-1C2 fixed YOLOX vs COCO/Sama paired 42",
                source_sha256=source["sama_source_sha256"],
                coco_source_sha256=source["coco_source_sha256"],
                cohort_sha256=source["new_cohort_sha256"],
                prior_coco_ids_excluded=TOTAL_EXCLUSIONS,
                photos_allocated=NEW_COUNT,
                per_target_allocated=SAMPLES_PER_CLASS,
                evaluated_categories=list(TARGETS),
                viewpoint_height="unknown",
                ground_truth_processes_statistically_independent=False,
                physically_verified_negatives=0,
                no_private_photos=True,
                no_media_ids_boxes_weights_published=True,
                robot_rknn_validated=False, promotion=False,
                motor_commands=0, sqlite_writes=0, qwen_calls=0,
                inferences_executed=0, image_fetches=0)
    if validate_only:
        base["status"] = "NEW_SOURCE_COHORT_SELECTED_NO_INFERENCE"
        return base
    if model_path is None:
        raise SourceGateError("STOP_MODEL: model required after source gate")
    from experiments.per80_yolox_coco_public import decode_all_classes
    from microduck_companion.cata_yolox_categories import (
        MODEL_SHA256, SIZE, prepare_image, validate_model_file,
    )
    from microduck_companion.cata2_bbox_eval import CocoCase, _official_jpeg
    validate_model_file(model_path)
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model_path), sess_options=opts,
                                   providers=["CPUExecutionProvider"])
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or (session.get_inputs()[0].name, session.get_inputs()[0].shape)
                != ("images", [1, 3, SIZE, SIZE])
            or (session.get_outputs()[0].name, session.get_outputs()[0].shape)
                != ("output", [1, 3549, 85])):
        raise SourceGateError("STOP_MODEL: unexpected frozen YOLOX I/O")
    outputs, digests, observed_times = {}, [], []
    seen_photos = set()
    for ident, _assigned in cases:
        width, height, filename, _license = images[ident]
        image = CocoCase(ident, filename, width, height, ())
        jpeg = _official_jpeg(image)
        digest = sha256(jpeg).hexdigest()
        if digest in seen_photos:
            raise SourceGateError("STOP_SOURCE: duplicate actual JPEG content")
        seen_photos.add(digest)
        digests.append(digest)
        tensor = prepare_image(jpeg, mode="original")
        start = time.perf_counter()
        raw = session.run(None, {"images":tensor})[0]
        observed_times.append((time.perf_counter()-start)*1000.)
        outputs[ident] = decode_all_classes(raw, width=width, height=height)
    if len(outputs) != NEW_COUNT or len(digests) != NEW_COUNT:
        raise SourceGateError("STOP_EVALUATION: not exactly 42 real inferences")
    scored = score_double_gt(cases, maps, boxes_coco, boxes_sama, outputs)
    base.update(status="HOST_PAIRED_GT_VALIDLY_SCORED",
                decision="STOP_PROMOTION",
                model_sha256=MODEL_SHA256,
                score_threshold=0.25, nms_iou=0.50, match_iou=0.50,
                classwise_scores=scored,
                inferences_executed=NEW_COUNT, image_fetches=NEW_COUNT,
                jpeg_sha256_aggregate=sha256("|".join(digests).encode()).hexdigest(),
                host_onnx_p50_ms=round(statistics.median(observed_times),3),
                host_onnx_p95_ms=round(sorted(observed_times)[
                    math.ceil(.95*len(observed_times))-1],3),
                host_peak_rss_kib_process=resource.getrusage(
                    resource.RUSAGE_SELF).ru_maxrss)
    return base


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-media",action="store_true")
    p.add_argument("--validate-only",action="store_true")
    p.add_argument("--annotations",type=Path,required=True)
    p.add_argument("--sama-zip",type=Path,required=True)
    p.add_argument("--model",type=Path)
    a=p.parse_args(argv)
    if not a.approved_public_media:
        p.error("public research confirmation required")
    if a.model is None and not a.validate_only:
        p.error("--model required for actual fixed inference")
    print(json.dumps(benchmark(a.annotations,a.sama_zip,
                model_path=a.model,validate_only=a.validate_only),
                sort_keys=True,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
