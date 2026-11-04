"""PER-QUAL-1C1: freeze a NEW 42-image label-only COCO/Sama cohort.

No YOLOX model access, JPEG downloads, semantic promotion, SQLite or robot I/O.
The 42 images inferred in invalid PR #301 are excluded as already consumed.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from experiments.per_qual1_sama_gt_gate import (
    FROZEN_COHORT_SHA256, SAMA_ANNOTATION_ZIP_SHA256, SEED_C1,
    SAMPLES_PER_CLASS, TARGETS, SourceGateError, _frozen_sha256,
    choose_paired_cohort, run_source_gate, summarize_ground_truth,
    unpack_sama_archive, validate_dual_class_map,
)

PREVIOUS_COUNT = 1232
FAILED_RUN_CONSUMED = 42
TOTAL_EXCLUSIONS = PREVIOUS_COUNT + FAILED_RUN_CONSUMED
NEW_COUNT = SAMPLES_PER_CLASS * len(TARGETS)


def select_new_after_consumed(original, sama, *, names, historical_ids,
                              old_cases, allowed_license_ids):
    """Choose without reading images or scores, using the verified second seed."""
    from experiments.per80_yolox_coco_public import COCO80_ID_ORDER

    if (type(historical_ids) is not frozenset
            or len(historical_ids) != PREVIOUS_COUNT
            or type(old_cases) is not tuple
            or len(old_cases) != FAILED_RUN_CONSUMED):
        raise SourceGateError("STOP_SOURCE: old cohort counts changed")
    old_id_set = {i for i, _ in old_cases}
    if (len(old_id_set) != FAILED_RUN_CONSUMED
            or historical_ids.intersection(old_id_set)):
        raise SourceGateError("STOP_SOURCE: duplicate or leaked old COCO IDs")
    old_roster = "|".join(f"{ident}/{cat}" for ident, cat in old_cases)
    _frozen_sha256(old_roster.encode(), FROZEN_COHORT_SHA256,
                   "consumed previous 42-image roster")
    excluded = frozenset(historical_ids | old_id_set)
    if len(excluded) != TOTAL_EXCLUSIONS:
        raise SourceGateError("STOP_SOURCE: not exactly 1274 excluded images")

    chosen, coco_ids, original_gt, sama_gt, info = choose_paired_cohort(
        original, sama, old_ids=excluded,
        allowed_license_ids=allowed_license_ids, selection_seed=SEED_C1)
    if (len(chosen) != NEW_COUNT
            or len({image_id for image_id, _ in chosen}) != NEW_COUNT
            or any(image_id in excluded for image_id, _ in chosen)
            or {name for _, name in chosen} != set(TARGETS)):
        raise SourceGateError("STOP_SOURCE: prospective images overlap or absent")
    spaces = validate_dual_class_map(names, coco_ids, COCO80_ID_ORDER)
    paired = summarize_ground_truth(chosen, coco_ids, original_gt, sama_gt)
    if (set(paired) != set(TARGETS) or
            any(row["allocated_photos"] != SAMPLES_PER_CLASS or
                row["original_gt_boxes"] < SAMPLES_PER_CLASS or
                row["sama_gt_boxes"] < SAMPLES_PER_CLASS
                for row in paired.values())):
        raise SourceGateError("STOP_SCHEMA: each source must have six assigned boxes")
    return chosen, spaces, paired, info


def source_gate(annotations_path: Path, sama_zip_path: Path):
    """Trust the previously green frozen source gate BEFORE selecting anew."""
    from experiments.per80_yolox_coco_public import (
        P4_IDS, _cohort_from_pinned_source, _valid_license_ids,
    )
    from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint

    original_gate = run_source_gate(annotations_path, sama_zip_path)
    if (original_gate.get("status") != "SOURCE_GATE_PASS_NO_INFERENCE"
            or original_gate.get("cohort_selection_sha256") != FROZEN_COHORT_SHA256
            or original_gate.get("sama_zip_sha256") != SAMA_ANNOTATION_ZIP_SHA256
            or original_gate.get("excluded_previous_coco_val_images") != PREVIOUS_COUNT
            or original_gate.get("prospective_new_photos_selected") != FAILED_RUN_CONSUMED):
        raise SourceGateError("STOP_SOURCE: historical source is no longer pinned")
    # The same bounded files are now decoded a second time only for new GT selection.
    blob = annotations_path.read_bytes()
    names, historical_800, _, _, _ = _cohort_from_pinned_source(blob)
    eighth, original, _, old = eighth_disjoint(blob)
    historical = frozenset(old | {c.image_id for c in eighth} | P4_IDS |
                          {c.image_id for c, _ in historical_800})
    if len(historical) != PREVIOUS_COUNT:
        raise SourceGateError("STOP_SOURCE: 1232 old COCO exclusions diverged")
    sama = unpack_sama_archive(sama_zip_path.read_bytes())
    rights = _valid_license_ids(original)
    old_cases, _, _, _, _ = choose_paired_cohort(
        original, sama, old_ids=historical, allowed_license_ids=rights)
    cases, spaces, paired, info = select_new_after_consumed(
        original, sama, names=names, historical_ids=historical,
        old_cases=old_cases, allowed_license_ids=rights)

    prospective_roster = "|".join(f"{ident}/{label}" for ident, label in cases)
    return {
        "experiment": "PER-QUAL-1C1 frozen next public COCO/Sama cohort SOURCE ONLY",
        "status": "NEW_SOURCE_COHORT_SELECTED_NO_INFERENCE",
        "coco_source_sha256": original_gate["original_coco_annotation_sha256"],
        "sama_source_sha256": original_gate["sama_zip_sha256"],
        "previous_42_cohort_sha256": original_gate["cohort_selection_sha256"],
        "new_cohort_sha256": sha256(prospective_roster.encode()).hexdigest(),
        "selection_seed": SEED_C1,
        "historical_coco_images_excluded": PREVIOUS_COUNT,
        "failed_pr301_images_excluded": FAILED_RUN_CONSUMED,
        "total_coco_ids_excluded": TOTAL_EXCLUSIONS,
        "new_selected_photos": NEW_COUNT,
        "per_target_allocated": SAMPLES_PER_CLASS,
        "categories": list(TARGETS),
        "class_id_domains": spaces,
        "paired_annotations": paired,
        "source_inventory": info,
        "gt_processes_independent_of_yolox_predictions": True,
        "gt_processes_statistically_independent": False,
        "viewpoint_height": "unknown",
        "physically_verified_negatives": 0,
        "model_accessed": False, "image_fetches": 0,
        "inferences_executed": 0, "promotion": False,
        "robot_rknn_validated": False,
        "motor_commands": 0, "sqlite_writes": 0, "qwen_calls": 0,
        "no_media_or_ids_published": True,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-metadata", action="store_true")
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--sama-zip", type=Path, required=True)
    args = p.parse_args(argv)
    if not args.approved_public_metadata:
        p.error("public metadata confirmation required")
    report = source_gate(args.annotations, args.sama_zip)
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
