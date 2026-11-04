"""PER-OI-V7-COHORT-1: freeze 42 independent-of-predictions GT IDs, no JPEGs.

Uses only the exact official Open Images V7 CSVs already qualified by #311.
No cross-dataset image independence or individual-photo rights are proved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path

from experiments.per_oi_v7_source_inventory import (
    _HEX_ID, _md5, _rows, PHOTO_LICENSES, OpenImagesSourceStop,
    source_inventory,
)

SEED = "kwipi-per-oi-v7-20261104-v1"
TARGETS = (
    "Tennis ball", "Book", "Bottle", "Chair", "Cat", "Dog", "Person",
)
EXACT_COCO_CANDIDATES = (
    "Book", "Bottle", "Chair", "Cat", "Dog", "Person",
)
PER_TARGET = 6
EXPECTED_TOTAL = len(TARGETS) * PER_TARGET
EXPECTED_SOURCE_SHA = {
    "class_descriptions_sha256": "1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9",
    "validation_images_sha256": "ed93a0e121fe345effdfc7359b848dbc64a1ff6778c8c73563157cb500b33a17",
    "validation_bbox_sha256": "d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2",
}
BOX_COLUMNS = (
    "ImageID", "LabelName", "Source", "Confidence", "XMin", "XMax",
    "YMin", "YMax", "IsGroupOf", "IsDepiction", "IsInside",
    "IsOccluded", "IsTruncated",
)
IMAGE_COLUMNS = (
    "ImageID", "Subset", "License", "OriginalMD5", "Rotation", "OriginalURL",
)


def _taxonomy(classes: Path) -> dict[str, str]:
    """Exact MID->label map; never reinterpret 'Football' as COCO sports_ball."""
    names = {}
    mids = set()
    for row in _rows(classes, ("LabelName", "DisplayName")):
        mid, name = row["LabelName"], row["DisplayName"]
        if mid in mids or not mid.startswith("/m/") or not name:
            raise OpenImagesSourceStop("STOP_SCHEMA: invalid or repeated MID")
        mids.add(mid)
        if name in TARGETS:
            if name in names:
                raise OpenImagesSourceStop("STOP_SCHEMA: repeated target class")
            names[name] = mid
    if set(names) != set(TARGETS):
        raise OpenImagesSourceStop("STOP_SCHEMA: incomplete target taxonomy")
    return {mid: name for name, mid in names.items()}


def _eligible_images(images: Path) -> dict[str, str]:
    """Only original HTTPS, declared CC BY 2.0 and stable MD5; drop MD5 twins."""
    seen_ids = set()
    md5_images: dict[str, list[str]] = defaultdict(list)
    for row in _rows(images, IMAGE_COLUMNS):
        ident = row["ImageID"]
        if not _HEX_ID.fullmatch(ident) or ident in seen_ids:
            raise OpenImagesSourceStop("STOP_SCHEMA: invalid/duplicate image ID")
        seen_ids.add(ident)
        if row["Subset"] != "validation":
            raise OpenImagesSourceStop("STOP_SOURCE: not the validation split")
        md5 = _md5(row["OriginalMD5"])
        if (row["License"] not in PHOTO_LICENSES
                or row["Rotation"] not in ("0", "0.0")
                or md5 is None or not row["OriginalURL"].startswith("https://")):
            continue
        md5_images[md5].append(ident)
    # Remove ALL duplicate MD5s, not only the later duplicate:
    # this prevents either representation from entering our holdout.
    return {ids[0]: digest for digest, ids in md5_images.items()
            if len(ids) == 1}


def _valid_boxes(boxes: Path, mids: dict[str, str],
                 eligible: dict[str, str]) -> dict[tuple[str, str], tuple]:
    found = defaultdict(list)
    for row in _rows(boxes, BOX_COLUMNS):
        name = mids.get(row["LabelName"])
        ident = row["ImageID"]
        if name is None or ident not in eligible:
            continue
        if any(row[f] not in ("0", "1") for f in (
                "IsGroupOf", "IsDepiction", "IsInside",
                "IsOccluded", "IsTruncated")):
            raise OpenImagesSourceStop("STOP_SCHEMA: nonbinary annotation flag")
        if any(row[f] == "1" for f in ("IsGroupOf", "IsDepiction", "IsInside")):
            continue
        if row["Source"] not in ("xclick", "activemil") or row["Confidence"] != "1":
            raise OpenImagesSourceStop("STOP_SCHEMA: unapproved positive box")
        try:
            x0, x1, y0, y1 = (
                float(row[f]) for f in ("XMin", "XMax", "YMin", "YMax"))
        except (ValueError, TypeError) as exc:
            raise OpenImagesSourceStop("STOP_SCHEMA: malformed target box") from exc
        if (not all(math.isfinite(v) and 0. <= v <= 1.
                    for v in (x0, x1, y0, y1))
                or not x0 < x1 or not y0 < y1):
            raise OpenImagesSourceStop("STOP_SCHEMA: invalid target box")
        found[(ident, name)].append((
            (x1-x0)*(y1-y0),
            row["IsOccluded"] == "1",
            row["IsTruncated"] == "1",
        ))
    return {key: tuple(value) for key, value in found.items()}


def select_frozen_roster(mids: dict[str, str], eligible: dict[str, str],
                         boxes: dict[tuple[str, str], tuple]):
    """Pure GT-only roster selection; never open model outputs or images."""
    if set(mids.values()) != set(TARGETS) or not eligible:
        raise OpenImagesSourceStop("STOP_SCHEMA: missing labels or images")
    pools = {
        name: frozenset(ident for (ident, label), values in boxes.items()
                        if label == name and values and ident in eligible)
        for name in TARGETS
    }
    ordered_names = sorted(TARGETS, key=lambda n: (len(pools[n]), TARGETS.index(n)))
    chosen = []
    taken = set()
    for name in ordered_names:
        free = pools[name] - taken
        ordered = sorted(free, key=lambda ident: (
            sha256(f"{SEED}/{name}/{ident}".encode("ascii")).digest(), ident))
        if len(ordered) < PER_TARGET:
            raise OpenImagesSourceStop(
                f"STOP_SOURCE: class={name} available={len(ordered)} required={PER_TARGET}")
        for ident in ordered[:PER_TARGET]:
            chosen.append((ident, name))
            taken.add(ident)
    if (len(chosen) != EXPECTED_TOTAL
            or len(taken) != EXPECTED_TOTAL
            or len({eligible[i] for i in taken}) != EXPECTED_TOTAL):
        raise OpenImagesSourceStop("STOP_SOURCE: duplicate or incomplete roster")
    return tuple(chosen), {k: len(v) for k, v in pools.items()}


def freeze_cohort(classes: Path, images: Path, boxes: Path) -> dict:
    base = source_inventory(classes, images, boxes)
    if base["source_sha256"] != EXPECTED_SOURCE_SHA:
        raise OpenImagesSourceStop("STOP_SOURCE: official Open Images SHA drift")
    mids = _taxonomy(classes)
    eligible = _eligible_images(images)
    truth = _valid_boxes(boxes, mids, eligible)
    chosen, available = select_frozen_roster(mids, eligible, truth)
    area = {"tiny_lt_1pct": 0, "medium_1_to_10pct": 0, "large_gt_10pct": 0}
    occluded = truncated = same_label_multi = multi_target = 0
    total_boxes = 0
    selected_image_ids = {ident for ident, _ in chosen}
    for ident, allocated in chosen:
        for size, occ, trunc in truth[(ident, allocated)]:
            total_boxes += 1
            area["tiny_lt_1pct" if size < .01 else
                 "medium_1_to_10pct" if size < .10 else
                 "large_gt_10pct"] += 1
            occluded += int(occ)
            truncated += int(trunc)
        same_label_multi += int(len(truth[(ident, allocated)]) >= 2)
        multi_target += int(sum(len(truth.get((ident, n), ()))
                                for n in TARGETS) >= 2)
    if selected_image_ids != {ident for ident, _ in chosen}:
        raise OpenImagesSourceStop("STOP_SOURCE: id collision")
    digest = sha256("|".join(
        f"{label}/{ident}" for ident, label in chosen
    ).encode("ascii")).hexdigest()
    return {
        "status": "GT_ONLY_42_ROSTER_FROZEN_NO_PIXELS_NO_MODEL",
        "selection_seed": SEED,
        "source_sha256": base["source_sha256"],
        "roster_sha256": digest,
        "cohort_images": len(chosen),
        "assigned_per_label": {n: PER_TARGET for n in TARGETS},
        "eligible_image_metadata_with_unique_md5": len(eligible),
        "candidate_gt_images_per_label": available,
        "selected_target_boxes": total_boxes,
        "selected_target_box_area_bins": area,
        "selected_target_boxes_occluded_flagged": occluded,
        "selected_target_boxes_truncated_flagged": truncated,
        "selected_images_with_multiple_assigned_label_boxes": same_label_multi,
        "selected_images_with_multiple_target_boxes": multi_target,
        "candidate_semantic_mapping": {
            "Tennis ball": "POSSIBLE_COCO_SPORTS_BALL_SUBTYPE_UNVERIFIED",
            **{n: "NAME_MATCH_ONLY_NOT_AUDITED" for n in EXACT_COCO_CANDIDATES},
        },
        "commercial_image_rights_individually_verified": False,
        "cross_dataset_image_duplicate_absence_verified": False,
        "gt_independent_of_model_predictions": True,
        "photo_license_declarations_validated": True,
        "camera_height": "unknown",
        "images_fetched": 0,
        "model_inferences": 0,
        "robot_rknn_validated": False,
        "model_promoted": False,
        "sqlite_writes": 0,
        "motor_commands": 0,
        "qwen_calls": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-metadata", action="store_true")
    p.add_argument("--classes", type=Path, required=True)
    p.add_argument("--images", type=Path, required=True)
    p.add_argument("--boxes", type=Path, required=True)
    args = p.parse_args(argv)
    if not args.approved_public_metadata:
        p.error("public source metadata authorization required")
    print(json.dumps(freeze_cohort(args.classes, args.images, args.boxes),
                     sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
