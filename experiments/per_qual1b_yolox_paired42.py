"""PER-QUAL-1B: 42 new COCO photos, one YOLOX output, two correlated GTs.

Host-only, fixed YOLOX and labels, no image/weight/ID artifact, no OEM/robot.
Only a completed source preflight may authorize opening the ONNX model.
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

from experiments.per_qual1_sama_gt_gate import (
    FROZEN_COHORT_SHA256, SAMA_ANNOTATION_ZIP_SHA256,
    SAMPLES_PER_CLASS, TARGETS, SourceGateError, _frozen_sha256, _images,
    _paired_iou50, choose_paired_cohort, run_source_gate,
    unpack_sama_archive,
)

N_IMAGES = len(TARGETS) * SAMPLES_PER_CLASS


def _score_against_both(cases, class_idxs, first_gt, second_gt, outputs):
    """Only one stored prediction per ID; score that SAME output twice.

    All seven target classes are measured on each of the 42 photos, not just
    the assigned positive class. Missing GT never means human-verified absence.
    """
    if (len(cases) != N_IMAGES or len({i for i, _ in cases}) != N_IMAGES
            or set(outputs) != {i for i, _ in cases}
            or set(class_idxs) != set(TARGETS)
            or len(set(class_idxs.values())) != len(TARGETS)):
        raise SourceGateError("invalid prospective 42-photo paired scoring set")
    summary = {}
    for name in TARGETS:
        idx = class_idxs[name]
        row = dict(allocated_photos=0, evaluated_photos=N_IMAGES,
                   gt_coco_boxes=0, gt_sama_boxes=0, proposals=0,
                   matched_coco_iou50=0, matched_sama_iou50=0,
                   coco_unmatched_not_proven_false=0,
                   sama_unmatched_not_proven_false=0)
        for ident, assigned in cases:
            proposals = outputs[ident]
            if not isinstance(proposals, tuple):
                raise SourceGateError("missing immutable ONNX decoding output")
            boxes = []
            for p in proposals:
                if (type(p.class_idx) is not int or
                        type(p.box) is not tuple or len(p.box) != 4 or
                        not all(type(v) in (float, int) and math.isfinite(v)
                                for v in p.box)):
                    raise SourceGateError("invalid scored proposal")
                if p.class_idx == idx:
                    boxes.append(p.box)
            boxes = tuple(boxes)
            truth_a = tuple(first_gt.get((ident, idx), ()))
            truth_b = tuple(second_gt.get((ident, idx), ()))
            match_a = _paired_iou50(boxes, truth_a)
            match_b = _paired_iou50(boxes, truth_b)
            row["allocated_photos"] += (assigned == name)
            row["gt_coco_boxes"] += len(truth_a)
            row["gt_sama_boxes"] += len(truth_b)
            row["proposals"] += len(boxes)
            row["matched_coco_iou50"] += match_a
            row["matched_sama_iou50"] += match_b
            row["coco_unmatched_not_proven_false"] += len(boxes) - match_a
            row["sama_unmatched_not_proven_false"] += len(boxes) - match_b
        if row["allocated_photos"] != SAMPLES_PER_CLASS:
            raise SourceGateError("invalid number of assigned positive cases")
        row["recall_coco_iou50"] = (round(row["matched_coco_iou50"] /
                                         row["gt_coco_boxes"], 6)
                                    if row["gt_coco_boxes"] else None)
        row["recall_sama_iou50"] = (round(row["matched_sama_iou50"] /
                                         row["gt_sama_boxes"], 6)
                                    if row["gt_sama_boxes"] else None)
        row["recall_delta_sama_minus_coco"] = (
            round(row["recall_sama_iou50"] - row["recall_coco_iou50"], 6)
            if row["recall_sama_iou50"] is not None
            and row["recall_coco_iou50"] is not None else None)
        summary[name] = row
    return summary


def _load_frozen_cases(annotations: Path, sama_zip: Path):
    """Source gate FIRST, before model import, model hash or JPEG fetch."""
    source = run_source_gate(annotations, sama_zip)
    if (source["status"] != "SOURCE_GATE_PASS_NO_INFERENCE" or
            source["prospective_new_photos_selected"] != N_IMAGES or
            source["excluded_previous_coco_val_images"] != 1232 or
            source["sama_zip_sha256"] != SAMA_ANNOTATION_ZIP_SHA256 or
            source["cohort_selection_sha256"] != FROZEN_COHORT_SHA256):
        raise SourceGateError("STOP_SOURCE: frozen source gate did not pass")
    from experiments.per80_yolox_coco_public import (
        P4_IDS, _cohort_from_pinned_source, _valid_license_ids,
        check_class_order,
    )
    from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint
    blob = annotations.read_bytes()
    names, old_cases, _, _, _ = _cohort_from_pinned_source(blob)
    eighth, original, _, older = eighth_disjoint(blob)
    history = frozenset(older | {c.image_id for c in eighth} | P4_IDS |
                        {case.image_id for case, _ in old_cases})
    sama = unpack_sama_archive(sama_zip.read_bytes())
    cases, ids, coco_gt, sama_gt, _ = choose_paired_cohort(
        original, sama, old_ids=history,
        allowed_license_ids=_valid_license_ids(original))
    _frozen_sha256("|".join(f"{i}/{name}" for i, name in cases).encode(),
                   FROZEN_COHORT_SHA256, "prospective B cohort")
    if (len(history) != 1232 or check_class_order(original) != names or
            any(name not in names for name in TARGETS)):
        raise SourceGateError("STOP_SOURCE: class or exclusion changed")
    coco_idx = {name: names.index(name) for name in TARGETS}
    image_info = _images(original)
    return source, cases, image_info, coco_idx, ids, coco_gt, sama_gt


def benchmark(annotations: Path, sama_zip: Path, *, model_path: Path | None,
              validate_only: bool):
    src, cases, images, class_idxs, source_ids, coco_gt, sama_gt = (
        _load_frozen_cases(annotations, sama_zip))
    base = dict(source_sha256=src["sama_zip_sha256"],
                cohort_sha256=src["cohort_selection_sha256"],
                original_coco_annotation_sha256=src["original_coco_annotation_sha256"],
                prior_coco_images_excluded=1232, selected_photos=N_IMAGES,
                assigned_per_category=SAMPLES_PER_CLASS,
                evaluated_categories=list(TARGETS),
                viewpoint_height="unknown", camera_geometry_verified=False,
                ground_truth_processes_statistically_independent=False,
                physically_verified_negatives=0,
                no_private_photos=True, no_media_ids_boxes_weights_published=True,
                no_new_model_training_or_tuning=True,
                robot_rknn_validated=False, promotion=False,
                motor_commands=0, sqlite_writes=0, qwen_calls=0,
                inferences_executed=0, image_fetches=0)
    if validate_only:
        base["status"] = "SOURCE_GATE_PASS_NO_INFERENCE"
        return base
    if model_path is None:
        raise SourceGateError("model path required after successful source gate")
    from microduck_companion.cata_yolox_categories import (
        MODEL_SHA256, SIZE, prepare_image, validate_model_file,
    )
    from microduck_companion.cata2_bbox_eval import CocoCase, _official_jpeg
    from experiments.per80_yolox_coco_public import decode_all_classes
    validate_model_file(model_path)
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model_path), sess_options=options,
                                   providers=["CPUExecutionProvider"])
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1 or
            (session.get_inputs()[0].name, session.get_inputs()[0].shape)
            != ("images", [1, 3, SIZE, SIZE]) or
            (session.get_outputs()[0].name, session.get_outputs()[0].shape)
            != ("output", [1, 3549, 85])):
        raise SourceGateError("STOP_MODEL: unreviewed YOLOX ONNX shape")
    outputs, image_digests, timings = {}, [], []
    seen_jpg = set()
    for ident, assigned in cases:
        width, height, filename, _ = images[ident]
        image = CocoCase(ident, filename, width, height, ())
        jpeg = _official_jpeg(image)  # bounded official URL, EXIF and shape checked
        digest = sha256(jpeg).hexdigest()
        if digest in seen_jpg:
            raise SourceGateError("duplicate public JPEG content")
        seen_jpg.add(digest)
        image_digests.append(digest)
        tensor = prepare_image(jpeg, mode="original")
        begin = time.perf_counter()
        raw = session.run(None, {"images": tensor})[0]
        timings.append(1000. * (time.perf_counter() - begin))
        outputs[ident] = decode_all_classes(raw, width=width, height=height)
    if len(outputs) != N_IMAGES or len(image_digests) != N_IMAGES:
        raise SourceGateError("not all frozen JPEGs were inferred exactly once")
    scores = _score_against_both(cases, class_idxs, coco_gt, sama_gt, outputs)
    base.update(status="HOST_PAIRED_GT_SENSITIVITY_MEASURED",
                decision="STOP_PROMOTION", model_sha256=MODEL_SHA256,
                score_threshold=0.25, nms_iou=0.50, match_iou=0.50,
                classwise_scores=scores,
                inferences_executed=N_IMAGES, image_fetches=N_IMAGES,
                jpeg_content_sha256_aggregate=sha256(
                    "|".join(image_digests).encode()).hexdigest(),
                host_onnx_p50_ms=round(statistics.median(timings), 3),
                host_onnx_p95_ms=round(sorted(timings)[math.ceil(.95 * len(timings))-1], 3),
                host_peak_rss_kib_process=resource.getrusage(
                    resource.RUSAGE_SELF).ru_maxrss)
    return base


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-media", action="store_true")
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--sama-zip", type=Path, required=True)
    p.add_argument("--model", type=Path)
    args = p.parse_args(argv)
    if not args.approved_public_media:
        p.error("explicit public research authorization required")
    if not args.validate_only and args.model is None:
        p.error("--model required outside preflight")
    report = benchmark(args.annotations, args.sama_zip,
                       model_path=args.model, validate_only=args.validate_only)
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
