"""Cat-A2b: PRIVATE two-review annotation disagreement gate, not ground truth.

Reuses the approved local JPEG/SHA/split verification and Cat-A2a IoU.
Two *declared* blind review files may detect disagreements, but their
human authorship, actual blindness, scene independence and the optical
height have NOT been independently authenticated. No agreement unlocks
model scoring, C3 memory credit, Qwen, robotd or motor actions.

No private file names, sample IDs, digests or boxes appear in reports.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from .cata2_bbox_eval import Box, MATCH_IOU, iou
from .cata2b_private_low import (
    BOX_FIELDS, GROUP_RE, MAX_BOXES, SAMPLE_RE, SHA_RE, VISIBILITY,
    LowDataset, _bounded_data, _reject_duplicate_pairs,
    _reject_nonfinite, load_private_low_dataset,
)
from .cata_yolox_categories import CATEGORIES
from .visual_photo_mobilenet_demo import PhotoBaselineError

REVIEW_VERSION = 1
REVIEW_SOURCE = "declared_blind_manual_test_review"
REVIEW_LIMIT = 256 * 1024
REVIEW_FILE_RE = r"r-[0-9a-f]{16}\.json"
HEADER_FIELDS = frozenset({
    "schema_version", "source", "role", "review_session_id",
    "blind_to_model_predictions_declared",
    "manual_independent_review_declared", "samples",
})
SAMPLE_FIELDS = frozenset({
    "sample_id", "image_sha256", "boxes",
    "all_targets_reviewed", "uncertain",
})


def _read_review(dataset: LowDataset, path: Path, role: str):
    """Strict bounded local-only TEST review. Never expose original labels."""
    if (not isinstance(path, Path)
            or path.parent != dataset.root / "reviews"
            or re.fullmatch(REVIEW_FILE_RE, path.name) is None
            or path.parent.is_symlink() or path.is_symlink()
            or not path.parent.is_dir()):
        raise PhotoBaselineError("private review must be an opaque local file")
    raw = _bounded_data(path, REVIEW_LIMIT)
    try:
        obj = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs,
                         parse_constant=_reject_nonfinite)
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise PhotoBaselineError("invalid private review JSON") from exc
    if (type(obj) is not dict or set(obj) != HEADER_FIELDS
            or type(obj["schema_version"]) is not int
            or obj["schema_version"] != REVIEW_VERSION
            or obj["source"] != REVIEW_SOURCE or obj["role"] != role
            or type(obj["review_session_id"]) is not str
            or GROUP_RE.fullmatch(obj["review_session_id"]) is None
            or obj["blind_to_model_predictions_declared"] is not True
            or obj["manual_independent_review_declared"] is not True
            or type(obj["samples"]) is not list):
        raise PhotoBaselineError("invalid blind review metadata or declarations")
    test = {s.sample_id: s for s in dataset.test()}
    if len(obj["samples"]) != len(test):
        raise PhotoBaselineError("incomplete blind test review")
    parsed = {}
    for row in obj["samples"]:
        if type(row) is not dict or set(row) != SAMPLE_FIELDS:
            raise PhotoBaselineError("unknown or missing review fields")
        sid = row["sample_id"]
        if (type(sid) is not str or SAMPLE_RE.fullmatch(sid) is None
                or sid not in test or sid in parsed
                or type(row["image_sha256"]) is not str
                or SHA_RE.fullmatch(row["image_sha256"]) is None
                or row["image_sha256"] != test[sid].image_sha256
                or row["all_targets_reviewed"] is not True
                or type(row["uncertain"]) is not bool):
            raise PhotoBaselineError("duplicate, mismatched or incomplete review item")
        raw_boxes = row["boxes"]
        if type(raw_boxes) is not list or len(raw_boxes) > MAX_BOXES:
            raise PhotoBaselineError("invalid bounded review boxes")
        boxes = []
        for record in raw_boxes:
            if type(record) is not dict or set(record) != BOX_FIELDS:
                raise PhotoBaselineError("invalid private review box schema")
            coords = record["xyxy"]
            name, vis = record["category"], record["visibility"]
            if (type(name) is not str or name not in CATEGORIES
                    or type(vis) is not str or vis not in VISIBILITY
                    or type(coords) is not list or len(coords) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v)
                           for v in coords)):
                raise PhotoBaselineError("invalid private review category or box")
            x0, y0, x1, y1 = (float(v) for v in coords)
            sample = test[sid]
            if not (0 <= x0 < x1 <= sample.width
                    and 0 <= y0 < y1 <= sample.height):
                raise PhotoBaselineError("review box outside original JPEG geometry")
            boxes.append((Box(name, (x0, y0, x1, y1)), vis))
        parsed[sid] = (tuple(boxes), row["uncertain"])
    if set(parsed) != set(test):
        raise PhotoBaselineError("missing blind TEST sample")
    return obj["review_session_id"], parsed


def _matched_boxes(left, right) -> int:
    """Max one-to-one IoU50 matching, including class AND visibility.

    Avoid greedy order-dependence when multiple boxes of one class overlap.
    Bounded by the existing 40-box-per-image private annotation limit.
    """
    links = [
        [j for j, (second, second_visibility) in enumerate(right)
         if first.category == second.category
         and first_visibility == second_visibility
         and iou(first, second) >= MATCH_IOU]
        for first, first_visibility in left
    ]
    right_owners = {}

    def assign(left_idx: int, seen: set[int]) -> bool:
        for right_idx in links[left_idx]:
            if right_idx in seen:
                continue
            seen.add(right_idx)
            owner = right_owners.get(right_idx)
            if owner is None or assign(owner, seen):
                right_owners[right_idx] = left_idx
                return True
        return False

    return sum(int(assign(i, set())) for i in range(len(left)))


def review_blind_test_annotations(
    manifest_path: Path, *, first_review_path: Path, second_review_path: Path,
) -> dict:
    """Inspect independently *declared* blind reviews locally and fail closed.

    The primary manifest may already have been contaminated by seeing YOLOX
    predictions: compare it only as an existing, NOT independent, reference.
    Identical reviews are not an independent truth or an authorization to run
    inference, pick thresholds, promote C3 memories or actuate a robot.
    """
    dataset = load_private_low_dataset(manifest_path)
    if (first_review_path == second_review_path
            or first_review_path.parent != second_review_path.parent):
        raise PhotoBaselineError("two distinct local blind review files required")
    first_id, first = _read_review(dataset, first_review_path, "first")
    second_id, second = _read_review(dataset, second_review_path, "second")
    if first_id == second_id:
        raise PhotoBaselineError("review sessions must have distinct opaque IDs")

    counts = {
        "test_images": 0, "agreed_images": 0, "agreed_negative_images": 0,
        "disagreement_images": 0, "uncertain_images": 0,
        "matched_boxes_iou50_class_and_visibility": 0,
        "first_review_boxes": 0, "second_review_boxes": 0,
        "primary_manifest_disagreements_with_first": 0,
        "primary_manifest_disagreements_with_second": 0,
    }
    for sample in dataset.test():
        first_boxes, first_uncertain = first[sample.sample_id]
        second_boxes, second_uncertain = second[sample.sample_id]
        primary = tuple(zip(sample.ground_truth, sample.visibility))
        pair_count = _matched_boxes(first_boxes, second_boxes)
        agree = (pair_count == len(first_boxes) == len(second_boxes)
                 and not first_uncertain and not second_uncertain)
        counts["test_images"] += 1
        counts["first_review_boxes"] += len(first_boxes)
        counts["second_review_boxes"] += len(second_boxes)
        counts["matched_boxes_iou50_class_and_visibility"] += pair_count
        counts["agreed_images"] += int(agree)
        counts["agreed_negative_images"] += int(
            agree and not first_boxes and not second_boxes)
        counts["disagreement_images"] += int(
            pair_count != len(first_boxes) or pair_count != len(second_boxes))
        counts["uncertain_images"] += int(first_uncertain or second_uncertain)
        counts["primary_manifest_disagreements_with_first"] += int(
            _matched_boxes(primary, first_boxes) != len(primary)
            or len(primary) != len(first_boxes))
        counts["primary_manifest_disagreements_with_second"] += int(
            _matched_boxes(primary, second_boxes) != len(primary)
            or len(primary) != len(second_boxes))
    return {
        "status": "declared_blind_review_disagreement_audit_only",
        "reviewer_independence_authenticated": False,
        "blindness_to_predictions_authenticated": False,
        "camera_height_independently_verified": False,
        "independent_scenes_verified": 0,
        "ground_truth_adjudicated": False,
        "benchmark_authorized_by_this_review": False,
        "c3_generalization_validated": False,
        "robot_or_rknn_validated": False,
        "media_or_ids_in_report": False,
        "model_inference_calls": 0,
        "qwen_calls": 0,
        "sqlite_writes": 0,
        "motor_commands": 0,
        **counts,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--review-first", type=Path, required=True)
    parser.add_argument("--review-second", type=Path, required=True)
    parser.add_argument("--approved-private-local-media", action="store_true")
    args = parser.parse_args(argv)
    if not args.approved_private_local_media:
        parser.error("explicit consent for private local review required")
    report = review_blind_test_annotations(
        args.manifest, first_review_path=args.review_first,
        second_review_path=args.review_second,
    )
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
