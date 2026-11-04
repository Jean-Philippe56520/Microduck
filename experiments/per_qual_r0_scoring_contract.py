"""QUAL-R0: pure paired-GT scoring contract, never access media or models.

COCO labels use official category_id; YOLOX predictions use a zero-based
80-class head index. Source _index_boxes emits defaultdict(list), not only dict.
This fixture-only helper is not an OEM perception adapter or a model benchmark.
"""
from __future__ import annotations

import math
from collections import Counter

from experiments.per80_yolox_coco_public import COCO80_ID_ORDER, Proposal
from experiments.per_qual1_sama_gt_gate import (
    TARGETS, SAMPLES_PER_CLASS, SourceGateError, _paired_iou50,
)

N_IMAGES = len(TARGETS) * SAMPLES_PER_CLASS


def _box_is_valid(box: object) -> bool:
    if type(box) not in (tuple, list) or len(box) != 4:
        return False
    if not all(type(v) in (float, int) and math.isfinite(v) for v in box):
        return False
    return box[2] > box[0] and box[3] > box[1]


def _boxes_for(source: dict, image_id: int, coco_category_id: int) -> tuple:
    """Safe lookup without causing defaultdict to insert missing GT entries."""
    values = source.get((image_id, coco_category_id), ())
    if type(values) not in (tuple, list):
        raise SourceGateError("STOP_SCHEMA: invalid annotation box collection")
    if not all(_box_is_valid(box) for box in values):
        raise SourceGateError("STOP_SCHEMA: corrupt annotation geometry")
    return tuple(tuple(float(v) for v in box) for box in values)


def validate_paired_contract(cases: object, class_spaces: object,
                             coco_gt: object, sama_gt: object) -> dict:
    """Validate the complete real-reader contract BEFORE model/image access.

    No predictions are required. A missing box on a non-allocated image is
    unknown, never a human-verified negative. No SQLite or network I/O.
    """
    if (type(cases) is not tuple or len(cases) != N_IMAGES
            or type(class_spaces) is not dict
            or set(class_spaces) != set(TARGETS)
            or not isinstance(coco_gt, dict) or not isinstance(sama_gt, dict)):
        raise SourceGateError("STOP_SCHEMA: invalid paired source container")
    ids = set()
    allocated = Counter()
    for item in cases:
        if (type(item) is not tuple or len(item) != 2
                or type(item[0]) is not int or item[0] < 0
                or item[1] not in TARGETS or item[0] in ids):
            raise SourceGateError("STOP_SCHEMA: invalid or repeated image identity")
        ids.add(item[0])
        allocated[item[1]] += 1
    if set(allocated) != set(TARGETS) or any(
            allocated[name] != SAMPLES_PER_CLASS for name in TARGETS):
        raise SourceGateError("STOP_SCHEMA: unequal positive allocations")
    for name in TARGETS:
        space = class_spaces[name]
        if (type(space) is not dict
                or set(space) != {"coco_category_id", "yolox_head_idx"}
                or type(space["coco_category_id"]) is not int
                or type(space["yolox_head_idx"]) is not int
                or not 0 <= space["yolox_head_idx"] < len(COCO80_ID_ORDER)
                or COCO80_ID_ORDER[space["yolox_head_idx"]]
                    != space["coco_category_id"]):
            raise SourceGateError("STOP_SCHEMA: COCO category ID / YOLOX index confusion")
    if len({class_spaces[name]["coco_category_id"] for name in TARGETS}) != len(TARGETS):
        raise SourceGateError("STOP_SCHEMA: duplicate official category")
    positive_gt_counts = {name: {"coco": 0, "sama": 0} for name in TARGETS}
    for image_id, assigned in cases:
        for name in TARGETS:
            official_id = class_spaces[name]["coco_category_id"]
            ca = _boxes_for(coco_gt, image_id, official_id)
            sa = _boxes_for(sama_gt, image_id, official_id)
            if assigned == name:
                if not ca or not sa:
                    raise SourceGateError("STOP_SCHEMA: missing assigned positive GT")
                positive_gt_counts[name]["coco"] += len(ca)
                positive_gt_counts[name]["sama"] += len(sa)
    return {
        "status": "HOST_GT_CONTRACT_PASS_NO_INFERENCE",
        "source_reader_types": [type(coco_gt).__name__, type(sama_gt).__name__],
        "selected_photos": N_IMAGES,
        "allocated_per_class": SAMPLES_PER_CLASS,
        "positives_by_class": positive_gt_counts,
        "inferences_executed": 0,
        "photos_downloaded": 0,
        "robot_validated": False,
    }


def score_paired_contract(cases: tuple, class_spaces: dict, coco_gt: dict,
                          sama_gt: dict, predictions: object) -> dict:
    """Score one immutable synthetic/host prediction set against both GTs.

    Call validate_paired_contract *before* opening any model when reusing this
    routine in a future experimental runner. This function checks again.
    """
    validate_paired_contract(cases, class_spaces, coco_gt, sama_gt)
    if (type(predictions) is not dict
            or set(predictions) != {ident for ident, _ in cases}):
        raise SourceGateError("STOP_SCHEMA: incomplete or duplicated prediction set")
    for image_id, _ in cases:
        proposals = predictions[image_id]
        if type(proposals) is not tuple:
            raise SourceGateError("STOP_MODEL: decoded proposals must be immutable tuple")
        for p in proposals:
            if (not isinstance(p, Proposal)
                    or type(p.class_idx) is not int
                    or not 0 <= p.class_idx < len(COCO80_ID_ORDER)
                    or type(p.confidence) not in (float, int)
                    or not math.isfinite(p.confidence)
                    or not 0 <= p.confidence <= 1
                    or not _box_is_valid(p.box)):
                raise SourceGateError("STOP_MODEL: invalid YOLOX proposal")
    rows = {}
    for name in TARGETS:
        space = class_spaces[name]
        official_id = space["coco_category_id"]
        model_idx = space["yolox_head_idx"]
        row = {"allocated_photos": 0, "evaluated_photos": N_IMAGES,
               "coco_gt_boxes": 0, "sama_gt_boxes": 0, "proposals": 0,
               "matched_coco_iou50": 0, "matched_sama_iou50": 0,
               "unmatched_coco_not_proven_false": 0,
               "unmatched_sama_not_proven_false": 0}
        for image_id, allocated_name in cases:
            proposals = tuple(p.box for p in predictions[image_id]
                              if p.class_idx == model_idx)
            ca = _boxes_for(coco_gt, image_id, official_id)
            sa = _boxes_for(sama_gt, image_id, official_id)
            match_ca = _paired_iou50(proposals, ca)
            match_sa = _paired_iou50(proposals, sa)
            row["allocated_photos"] += int(allocated_name == name)
            row["proposals"] += len(proposals)
            row["coco_gt_boxes"] += len(ca)
            row["sama_gt_boxes"] += len(sa)
            row["matched_coco_iou50"] += match_ca
            row["matched_sama_iou50"] += match_sa
            row["unmatched_coco_not_proven_false"] += len(proposals) - match_ca
            row["unmatched_sama_not_proven_false"] += len(proposals) - match_sa
        row["recall_coco_iou50"] = round(
            row["matched_coco_iou50"] / row["coco_gt_boxes"], 6)
        row["recall_sama_iou50"] = round(
            row["matched_sama_iou50"] / row["sama_gt_boxes"], 6)
        row["delta_sama_minus_coco"] = round(
            row["recall_sama_iou50"] - row["recall_coco_iou50"], 6)
        rows[name] = row
    return rows
