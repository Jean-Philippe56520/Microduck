"""OI-V7-HUMAN-1: source-only verification of candidate human labels + GT boxes.

Nothing here verifies individual photo rights, cross-dataset independence,
physical low view or the quality of any detector. Never log IDs/URLs/pixels.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from experiments.per_oi_v7_source_inventory import (
    _file, _rows, _md5, _HEX_ID, PHOTO_LICENSES, OpenImagesSourceStop,
)

TARGETS = ("Person", "Cat", "Dog", "Chair", "Bottle", "Book", "Tennis ball")
PINNED_3 = {
    "classes": "1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9",
    "images": "ed93a0e121fe345effdfc7359b848dbc64a1ff6778c8c73563157cb500b33a17",
    "boxes": "d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2",
}
MAX_BYTES = {"classes": 1_000_000, "images": 40_000_000,
             "boxes": 180_000_000, "human": 120_000_000}


def qualify_metadata(classes: Path, images: Path, boxes: Path, human: Path,
                     *, require_official_pins: bool = False) -> dict:
    """Aggregate verified positives with valid boxes; source pool, NOT accepted JPEGs."""
    paths = {"classes": classes, "images": images, "boxes": boxes, "human": human}
    hashes = {key: _file(p, MAX_BYTES[key]) for key, p in paths.items()}
    if require_official_pins and any(hashes[k] != v for k, v in PINNED_3.items()):
        raise OpenImagesSourceStop("STOP_SOURCE: three official pinned CSVs drifted")

    mids_by_name = {}
    seen_mids = set()
    count_classes = 0
    for row in _rows(classes, ("LabelName", "DisplayName")):
        mid, name = row["LabelName"], row["DisplayName"]
        if mid in seen_mids or not mid.startswith("/m/") or not name:
            raise OpenImagesSourceStop("STOP_SCHEMA: malformed or duplicate MID")
        seen_mids.add(mid)
        count_classes += 1
        if name in TARGETS:
            if name in mids_by_name:
                raise OpenImagesSourceStop("STOP_SCHEMA: duplicate target class name")
            mids_by_name[name] = mid
    if count_classes < 100 or set(mids_by_name) != set(TARGETS):
        raise OpenImagesSourceStop("STOP_SCHEMA: incomplete target taxonomy")
    name_by_mid = {mid: name for name, mid in mids_by_name.items()}

    eligible = set()
    all_ids = set()
    md5_seen = set()
    excluded = 0
    for row in _rows(images, (
        "ImageID", "Subset", "OriginalURL", "OriginalLandingURL",
        "License", "OriginalMD5", "Rotation",
    )):
        ident = row["ImageID"]
        if not _HEX_ID.fullmatch(ident) or ident in all_ids:
            raise OpenImagesSourceStop("STOP_SCHEMA: malformed or duplicate image ID")
        all_ids.add(ident)
        if row["Subset"] != "validation":
            raise OpenImagesSourceStop("STOP_SOURCE: wrong image split")
        digest = _md5(row["OriginalMD5"])
        approved = (row["License"] in PHOTO_LICENSES
                    and row["Rotation"] in ("0", "0.0")
                    and digest is not None
                    and row["OriginalURL"].startswith("https://")
                    and row["OriginalLandingURL"].startswith("https://"))
        if not approved or digest in md5_seen:
            excluded += 1
            continue
        md5_seen.add(digest)
        eligible.add(ident)
    if not 1000 <= len(all_ids) <= 200_000:
        raise OpenImagesSourceStop("STOP_SOURCE: wrong validation image volume")

    boxed = {name: set() for name in TARGETS}
    invalid_boxes = 0
    for row in _rows(boxes, (
        "ImageID", "LabelName", "Source", "Confidence", "XMin", "XMax",
        "YMin", "YMax", "IsGroupOf", "IsDepiction", "IsInside",
    )):
        name = name_by_mid.get(row["LabelName"])
        if name is None or row["ImageID"] not in eligible:
            continue
        if any(row[f] != "0" for f in ("IsGroupOf", "IsDepiction", "IsInside")):
            continue
        if row["Source"] not in ("xclick", "activemil") or row["Confidence"] != "1":
            raise OpenImagesSourceStop("STOP_SCHEMA: unverified bounding box source")
        try:
            x0, x1, y0, y1 = (float(row[f]) for f in ("XMin", "XMax", "YMin", "YMax"))
        except (ValueError, TypeError) as exc:
            raise OpenImagesSourceStop("STOP_SCHEMA: invalid bbox coordinates") from exc
        if not (all(math.isfinite(v) and 0 <= v <= 1 for v in (x0,x1,y0,y1))
                and x0 < x1 and y0 < y1):
            invalid_boxes += 1
            continue
        boxed[name].add(row["ImageID"])

    # A class can be positive, negative, or unknown on each image.
    # Conflicts are excluded; missing annotations NEVER count as negatives.
    human_states = {name: {} for name in TARGETS}
    n_valid_rows = 0
    for row in _rows(human, ("ImageID", "Source", "LabelName", "Confidence")):
        if row["Source"] not in ("verification", "crowdsource-verification"):
            raise OpenImagesSourceStop("STOP_SCHEMA: non-human label in human labels CSV")
        if row["Confidence"] not in ("0", "1") or not _HEX_ID.fullmatch(row["ImageID"]):
            raise OpenImagesSourceStop("STOP_SCHEMA: invalid verified label/confidence")
        n_valid_rows += 1
        name = name_by_mid.get(row["LabelName"])
        if name is None or row["ImageID"] not in eligible:
            continue
        states = human_states[name]
        prior = states.get(row["ImageID"])
        state = int(row["Confidence"])
        states[row["ImageID"]] = state if prior is None or prior == state else -1
    if n_valid_rows < 100:
        raise OpenImagesSourceStop("STOP_SOURCE: suspiciously few human label rows")

    counts = {}
    for name in TARGETS:
        states = human_states[name]
        b = boxed[name]
        verified_pos_box = sum(s == 1 and ident in b for ident, s in states.items())
        counts[name] = {
            "candidate_boxed_and_human_positive": verified_pos_box,
            "human_negative": sum(s == 0 for s in states.values()),
            "human_positive_without_valid_box": sum(s == 1 and ident not in b for ident, s in states.items()),
            "boxed_without_human_positive": sum(states.get(ident) != 1 for ident in b),
            "conflicting_human_labels_excluded": sum(s == -1 for s in states.values()),
        }
    six_per_class_possible_from_metadata = all(
        counts[name]["candidate_boxed_and_human_positive"] >= 6 for name in TARGETS)
    return {
        "status": ("METADATA_42_POSSIBLE_NOT_LICENSED" if six_per_class_possible_from_metadata
                   else "STOP_GT_POOL_LT6_NOT_LICENSED"),
        "source_sha256": hashes,
        "human_verified_rows_processed": n_valid_rows,
        "validation_image_metadata_rows": len(all_ids),
        "declared_license_eligible_metadata_only": len(eligible),
        "excluded_metadata": excluded,
        "invalid_target_boxes_excluded": invalid_boxes,
        "per_target": counts,
        "six_per_class_possible_from_metadata": six_per_class_possible_from_metadata,
        "exact_tennis_ball_only": True,
        "rights_verified_individually": False,
        "cross_corpus_dedup_verified": False,
        "cohort_selected": False,
        "scores_measured": False,
        "real_pixels_loaded": 0,
        "models_loaded": 0,
        "robot_rknn_validated": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-metadata", action="store_true")
    for key in ("classes", "images", "boxes", "human"):
        p.add_argument("--" + key, required=True, type=Path)
    p.add_argument("--official-pins", action="store_true")
    args = p.parse_args(argv)
    if not args.approved_public_metadata:
        p.error("explicit public metadata authorization required")
    r = qualify_metadata(args.classes, args.images, args.boxes, args.human,
                         require_official_pins=args.official_pins)
    print(json.dumps(r, allow_nan=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
