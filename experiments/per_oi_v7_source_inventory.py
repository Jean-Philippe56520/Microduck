"""PER-OI-V7-SRC-0: independent public Open Images V7 metadata preflight.

Read *only* official CSV annotations and per-image license declarations.
No pixels, model inference, private data, COCO-ID equivalence, SQL, or motors.
Source metadata does not establish rights of each original Flickr photograph.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
from pathlib import Path
import re

SOURCE = (
    "https://storage.googleapis.com/openimages/web/download_v7.html"
)
PHOTO_LICENSES = frozenset((
    "http://creativecommons.org/licenses/by/2.0/",
    "https://creativecommons.org/licenses/by/2.0/",
))
BOXABLE_LABELS = (
    "Person", "Cat", "Dog", "Chair", "Bottle", "Book",
    "Ball", "Football", "Basketball", "Baseball", "Tennis ball", "Soccer ball",
)
EXACT_CANDIDATES = ("Person", "Cat", "Dog", "Chair", "Bottle", "Book")
MAX_CLASSES = 1_000_000
MAX_IMAGES = 40_000_000
MAX_BOXES = 180_000_000
_HEX_ID = re.compile(r"[0-9a-f]{16}\Z")


class OpenImagesSourceStop(ValueError):
    """A source or taxonomy precondition did not pass."""


def _file(path: Path, upper: int) -> str:
    if (not isinstance(path, Path) or path.is_symlink() or not path.is_file()
            or not 64 <= path.stat().st_size <= upper):
        raise OpenImagesSourceStop("STOP_SOURCE: missing, symlinked or oversized CSV")
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path, fields: tuple[str, ...]):
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fp:
            source = csv.DictReader(fp)
            if (source.fieldnames is None
                    or not set(fields).issubset(source.fieldnames)
                    or len(source.fieldnames) != len(set(source.fieldnames))):
                raise OpenImagesSourceStop("STOP_SCHEMA: invalid CSV columns")
            for row in source:
                if None in row or not all(isinstance(row[f], str) for f in fields):
                    raise OpenImagesSourceStop("STOP_SCHEMA: malformed CSV record")
                yield row
    except (UnicodeError, csv.Error) as exc:
        raise OpenImagesSourceStop("STOP_SCHEMA: undecodable CSV source") from exc


def _md5(value: str) -> str | None:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error):
        return None
    return raw.hex() if len(raw) == 16 else None


def source_inventory(classes: Path, images: Path, boxes: Path) -> dict:
    """Bounded source-only class counts; no untrusted model scores enter."""
    checksums = {
        "class_descriptions_sha256": _file(classes, MAX_CLASSES),
        "validation_images_sha256": _file(images, MAX_IMAGES),
        "validation_bbox_sha256": _file(boxes, MAX_BOXES),
    }
    labels = {}
    for row in _rows(classes, ("LabelName", "DisplayName")):
        key, name = row["LabelName"], row["DisplayName"]
        if key in labels or not key.startswith("/m/") or not name:
            raise OpenImagesSourceStop("STOP_SCHEMA: malformed or duplicate class")
        labels[key] = name
    if len(labels) < 100:
        raise OpenImagesSourceStop("STOP_SCHEMA: incomplete boxable taxonomy")
    candidate = {mid: name for mid, name in labels.items()
                 if name in BOXABLE_LABELS}
    if len(candidate) != len(set(candidate.values())):
        raise OpenImagesSourceStop("STOP_SCHEMA: ambiguous class display names")
    if any(name not in candidate.values() for name in EXACT_CANDIDATES):
        raise OpenImagesSourceStop("STOP_SCHEMA: mandatory common class absent")
    image_licensed = {}
    seen = set()
    excluded_metadata = 0
    eligible_md5 = set()
    for row in _rows(images, (
        "ImageID", "Subset", "License", "OriginalMD5", "Rotation",
        "OriginalURL",
    )):
        ident = row["ImageID"]
        if not _HEX_ID.fullmatch(ident) or ident in seen:
            raise OpenImagesSourceStop("STOP_SCHEMA: invalid/duplicate image ID")
        seen.add(ident)
        if row["Subset"] != "validation":
            raise OpenImagesSourceStop("STOP_SOURCE: source not validation split")
        md5 = _md5(row["OriginalMD5"])
        eligible = (
            row["License"] in PHOTO_LICENSES
            and row["Rotation"] in ("0", "0.0")
            and md5 is not None
            and row["OriginalURL"].startswith("https://")
        )
        if eligible:
            if md5 in eligible_md5:
                excluded_metadata += 1
                continue
            eligible_md5.add(md5)
            image_licensed[ident] = md5
        else:
            excluded_metadata += 1
    if not 1000 <= len(seen) <= 200_000:
        raise OpenImagesSourceStop("STOP_SOURCE: unexpected validation volume")
    positives = {name: set() for name in candidate.values()}
    boxes_per_name = {name: 0 for name in candidate.values()}
    box_skips = {
        "not_candidate_class": 0, "not_eligible_image": 0,
        "group_depiction_or_inside": 0, "invalid_rect": 0,
    }
    for row in _rows(boxes, (
        "ImageID", "LabelName", "Source", "Confidence", "XMin", "XMax",
        "YMin", "YMax", "IsGroupOf", "IsDepiction", "IsInside",
    )):
        name = candidate.get(row["LabelName"])
        if name is None:
            box_skips["not_candidate_class"] += 1
            continue
        ident = row["ImageID"]
        if ident not in image_licensed:
            box_skips["not_eligible_image"] += 1
            continue
        if any(row[f] != "0" for f in ("IsGroupOf", "IsDepiction", "IsInside")):
            box_skips["group_depiction_or_inside"] += 1
            continue
        if row["Source"] not in ("xclick", "activemil") or row["Confidence"] != "1":
            raise OpenImagesSourceStop("STOP_SCHEMA: unsupported positive bbox source")
        try:
            x0, x1, y0, y1 = (float(row[k]) for k in ("XMin", "XMax", "YMin", "YMax"))
        except (ValueError, TypeError) as exc:
            raise OpenImagesSourceStop("STOP_SCHEMA: malformed bbox") from exc
        if not (all(math.isfinite(v) and 0 <= v <= 1
                    for v in (x0, x1, y0, y1)) and x0 < x1 and y0 < y1):
            box_skips["invalid_rect"] += 1
            continue
        positives[name].add(ident)
        boxes_per_name[name] += 1
    by_label = {
        label: {
            "validation_images_with_licensed_declared_gt": len(positives[label]),
            "bounding_boxes": boxes_per_name[label],
        } for label in sorted(positives)
    }
    return {
        "status": "OI_V7_METADATA_INVENTORY_ONLY_NOT_QUALIFIED",
        "official_description_url": SOURCE,
        "source_sha256": checksums,
        "boxable_classes_total": len(labels),
        "candidate_labels_found": sorted(candidate.values()),
        "exact_label_candidates_for_coco": list(EXACT_CANDIDATES),
        "sports_ball_coco_mapping": "UNKNOWN_NOT_INFERRED_FROM_BALL",
        "per_label": by_label,
        "validation_image_metadata_rows": len(seen),
        "per_image_declared_cc_by_2_valid_md5_zero_rotation": len(image_licensed),
        "excluded_image_metadata_or_duplicate_md5": excluded_metadata,
        "skipped_annotations": box_skips,
        "metadata_rights_are_proof_of_ownership": False,
        "image_rights_independently_verified": False,
        "cross_dataset_duplicate_absence_verified": False,
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
    p.add_argument("--classes", type=Path, required=True)
    p.add_argument("--images", type=Path, required=True)
    p.add_argument("--boxes", type=Path, required=True)
    args = p.parse_args(argv)
    if not args.approved_public_metadata:
        p.error("explicit approval of public metadata study required")
    print(json.dumps(source_inventory(args.classes, args.images, args.boxes),
                     sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
