"""Cat-A2d: independent Open Images V7 human labels + box localization probe.

HOST RESEARCH ONLY. No private photos, no training, no robot, no SQLite writes.
Reuse Cat-A2c's historical 48-ID selection to exclude its validation photos.
Class labels must be human verified. Missing votes are NEVER negative labels.
Open Images 'Ball' is NOT COCO sports_ball, so that class is not scored.
A box with IsDepiction=1 is not proof of a physical object in the room.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO, StringIO
import json
import math
from pathlib import Path
import resource
import statistics
import time

from microduck_companion.cata2_bbox_eval import Box, decode_boxes, iou
from microduck_companion.cata2c_openimages_human_labels import (
    ALLOWED_HUMAN_SOURCE, ALLOWED_LICENSES, CLASS_MAPPING,
    IMAGE_ID_PATTERN, IMAGE_LIMIT, SOURCE_SHA256, _csv_rows,
    _official_jpeg, select_human_verified_cases,
)
from microduck_companion.cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, prepare_image, validate_model_file,
)
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError

SEED = "kwipi-oidv7-A2d-newholdout-v1-20261104"
PER_LABEL = 24
MAX_BOX_CSV_BYTES = 70_000_000
# Frozen after first real public CI #41842797778, before any repeat run.
BBOX_SOURCE_SHA256 = "d8bbd59410af14835d7733165a7bb8a3f0213981b22dd5077b0b9f7878991ff2"
CATEGORIES = ("person", "cat", "dog", "chair")
BBOX_FIELDS = frozenset({
    "ImageID", "Source", "LabelName", "Confidence",
    "XMin", "XMax", "YMin", "YMax", "IsOccluded",
    "IsTruncated", "IsGroupOf", "IsDepiction", "IsInside",
})
EXPECTED_MODEL_SHAPES = ([1, 3, SIZE, SIZE], [1, 3549, 85])


@dataclass(frozen=True)
class PublicBox:
    xyxy_normalized: tuple[float, float, float, float]
    depiction: str


@dataclass(frozen=True)
class PublicCase:
    image_id: str
    category: str
    present: bool
    boxes: tuple[PublicBox, ...]


def _sha_rank(category: str, positive: bool, image_id: str) -> bytes:
    return sha256(
        f"{SEED}/{category}/{int(positive)}/{image_id}".encode()
    ).digest()


def _class_mids(raw: bytes) -> dict[str, str]:
    if type(raw) is not bytes or not 16 <= len(raw) <= 150_000:
        raise PhotoBaselineError("invalid official class list size")
    try:
        reader = csv.reader(StringIO(raw.decode("utf-8-sig")), strict=True)
        by_name: dict[str, set[str]] = {}
        for i, row in enumerate(reader):
            if i == 0 and row == ["LabelName", "DisplayName"]:
                continue
            if len(row) != 2 or not row[0].startswith("/m/"):
                raise PhotoBaselineError("bad Open Images MID/name row")
            if row[1] in CLASS_MAPPING.values():
                by_name.setdefault(row[1], set()).add(row[0])
        mapping = {}
        for cat, name in CLASS_MAPPING.items():
            found = by_name.get(name, set())
            if len(found) != 1:
                raise PhotoBaselineError("ambiguous Open Images class map")
            mapping[next(iter(found))] = cat
        return mapping
    except (UnicodeError, ValueError, csv.Error) as exc:
        if isinstance(exc, PhotoBaselineError):
            raise
        raise PhotoBaselineError("invalid official class CSV") from exc


def _licensed_ids(raw: bytes) -> set[str]:
    good: set[str] = set()
    seen: set[str] = set()
    for row in _csv_rows(
        raw, required=frozenset({
            "ImageID", "Subset", "License", "OriginalSize", "Rotation"
        }), cap=45_000_000,
    ):
        image_id = row["ImageID"]
        if not IMAGE_ID_PATTERN.fullmatch(image_id) or image_id in seen:
            raise PhotoBaselineError("invalid/duplicate metadata ID")
        seen.add(image_id)
        if (row["Subset"] == "validation"
                and row["License"] in ALLOWED_LICENSES
                and row["Rotation"] in ("0", "0.0")
                and row["OriginalSize"].isdigit()
                and 100 <= int(row["OriginalSize"]) <= IMAGE_LIMIT):
            good.add(image_id)
    return good


def _bool_votes(raw: bytes, mids: dict[str, str], licensed: set[str]):
    votes: dict[tuple[str, str], set[bool]] = {}
    for row in _csv_rows(raw, required=frozenset({
        "ImageID", "Source", "LabelName", "Confidence",
    }), cap=55_000_000):
        cat = mids.get(row["LabelName"])
        if (cat is None or row["Source"] not in ALLOWED_HUMAN_SOURCE
                or row["ImageID"] not in licensed):
            continue
        score = row["Confidence"]
        if score not in ("0", "0.0", "1", "1.0"):
            raise PhotoBaselineError("nonbinary claimed human label")
        votes.setdefault((row["ImageID"], cat), set()).add(
            score in ("1", "1.0")
        )
    return votes


def _boxes(raw: bytes, mids: dict[str, str], licensed: set[str]):
    found: dict[tuple[str, str], list[PublicBox]] = {}
    for row in _csv_rows(raw, required=BBOX_FIELDS, cap=MAX_BOX_CSV_BYTES):
        cat = mids.get(row["LabelName"])
        if cat is None or row["ImageID"] not in licensed:
            continue
        if (row["Source"] not in ("xclick", "activemil")
                or row["Confidence"] not in ("1", "1.0")
                or any(row[k] not in ("0", "1", "-1")
                       for k in ("IsGroupOf", "IsInside", "IsDepiction"))):
            raise PhotoBaselineError("unsupported human box provenance")
        try:
            x0, x1, y0, y1 = (
                float(row[k]) for k in ("XMin", "XMax", "YMin", "YMax")
            )
        except (TypeError, ValueError) as exc:
            raise PhotoBaselineError("non-numeric official box") from exc
        if not (all(math.isfinite(v) for v in (x0, y0, x1, y1))
                and 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise PhotoBaselineError("invalid normalized official bbox")
        if row["IsGroupOf"] == "1" or row["IsInside"] == "1":
            continue  # cannot certify individual physical object
        found.setdefault((row["ImageID"], cat), []).append(
            PublicBox((x0, y0, x1, y1), row["IsDepiction"])
        )
    return found


def select_public_cases(
    classes: bytes, metadata: bytes, votes_raw: bytes, box_raw: bytes,
    *, excluded_ids: frozenset[str], per_label: int = PER_LABEL,
) -> tuple[PublicCase, ...]:
    """Selection uses source ground truth only, NEVER predictions or pixels."""
    if (type(per_label) is not int or not 1 <= per_label <= 24
            or type(excluded_ids) is not frozenset
            or any(type(x) is not str or not IMAGE_ID_PATTERN.fullmatch(x)
                   for x in excluded_ids)):
        raise PhotoBaselineError("invalid fixed cohort selector")
    mids = _class_mids(classes)
    licensed = _licensed_ids(metadata)
    votes = _bool_votes(votes_raw, mids, licensed)
    boxes = _boxes(box_raw, mids, licensed)
    pools: dict[tuple[str, bool], list[str]] = {
        (cat, label): [] for cat in CATEGORIES for label in (True, False)
    }
    for (image_id, cat), binary in votes.items():
        if len(binary) != 1 or image_id in excluded_ids:
            continue  # conflicting votes are not truth
        label = next(iter(binary))
        refs = boxes.get((image_id, cat), [])
        if (label and not refs) or (not label and refs):
            continue  # missing bbox or contradictory annotation
        pools[(cat, label)].append(image_id)

    selected: list[PublicCase] = []
    taken = set(excluded_ids)
    for cat in CATEGORIES:
        for present in (True, False):
            options = sorted(
                (image_id for image_id in pools[(cat, present)]
                 if image_id not in taken),
                key=lambda image_id: (
                    _sha_rank(cat, present, image_id), image_id
                ),
            )
            if len(options) < per_label:
                raise PhotoBaselineError(
                    "not enough official cases before inference: "
                    + json.dumps({
                        f"{klass}/{int(label)}": len(pool)
                        for (klass, label), pool in sorted(pools.items())
                    }, sort_keys=True)
                    + f"; first shortfall class={cat} "
                    + f"human_present={int(present)} available={len(options)} "
                    + f"required={per_label}"
                )
            for image_id in options[:per_label]:
                selected.append(PublicCase(
                    image_id, cat, present,
                    tuple(boxes.get((image_id, cat), ())),
                ))
                taken.add(image_id)
    if (len(selected) != per_label * len(CATEGORIES) * 2
            or len({s.image_id for s in selected}) != len(selected)):
        raise PhotoBaselineError("cohort uniqueness invariant failed")
    return tuple(selected)


def _source_bytes(path: Path, limit: int) -> bytes:
    if (path.is_symlink() or not path.is_file()
            or not 20 <= path.stat().st_size <= limit):
        raise PhotoBaselineError("invalid bounded public metadata file")
    with path.open("rb") as fp:
        data = fp.read(limit + 1)
    if len(data) > limit:
        raise PhotoBaselineError("oversize official metadata")
    return data


def _load_sources(classes: Path, metadata: Path, labels: Path, boxes: Path):
    data = {
        "class": _source_bytes(classes, 150_000),
        "metadata": _source_bytes(metadata, 45_000_000),
        "human_labels": _source_bytes(labels, 55_000_000),
        "bbox": _source_bytes(boxes, MAX_BOX_CSV_BYTES),
    }
    actual = {key: sha256(value).hexdigest() for key, value in data.items()}
    if actual["bbox"] != BBOX_SOURCE_SHA256:
        raise PhotoBaselineError("official box metadata digest changed")
    if any(actual[key] != hash_value
           for key, hash_value in SOURCE_SHA256.items()):
        raise PhotoBaselineError("previously pinned official metadata changed")
    old = select_human_verified_cases(
        data["class"], data["metadata"], data["human_labels"]
    )
    old_ids = frozenset(x.image_id for x in old)
    if len(old_ids) != 48:
        raise PhotoBaselineError("historical Cat-A2c exclusion changed")
    cases = select_public_cases(
        data["class"], data["metadata"], data["human_labels"], data["bbox"],
        excluded_ids=old_ids,
    )
    roster = "|".join(
        f"{x.image_id}/{x.category}/{int(x.present)}"
        for x in cases
    )
    return cases, actual, sha256(roster.encode()).hexdigest()


def _geometry(jpeg: bytes):
    from PIL import Image
    try:
        with Image.open(BytesIO(jpeg)) as im:
            if (im.format != "JPEG" or im.getexif().get(274, 1) != 1
                    or min(im.size) < 32 or max(im.size) > 4096):
                raise PhotoBaselineError("unsupported JPEG geometry/rotation")
            im.load()
            return im.size
    except (OSError, ValueError) as exc:
        if isinstance(exc, PhotoBaselineError):
            raise
        raise PhotoBaselineError("unreadable public JPEG") from exc


def _matched_boxes(
    category: str, refs: tuple[PublicBox, ...],
    pred: tuple[Box, ...], width: int, height: int,
) -> tuple[int, int]:
    """One-to-one IoU50, exact class; returns TP and TP on depicted boxes."""
    truth = tuple(
        Box(category, (
            b.xyxy_normalized[0] * width, b.xyxy_normalized[1] * height,
            b.xyxy_normalized[2] * width, b.xyxy_normalized[3] * height,
        )) for b in refs
    )
    matched: set[int] = set()
    depicted = 0
    for p in sorted(
        (p for p in pred if p.category == category),
        key=lambda p: -p.confidence,
    ):
        scores = [
            (iou(p, gt), i) for i, gt in enumerate(truth)
            if i not in matched
        ]
        overlap, idx = max(scores, default=(0., -1))
        if overlap >= 0.50:
            matched.add(idx)
            depicted += refs[idx].depiction == "1"
    return len(matched), depicted


def benchmark(
    *, classes: Path, metadata: Path, labels: Path, boxes: Path,
    model: Path | None, validate_only: bool,
) -> dict:
    cases, source_sha, roster_sha = _load_sources(
        classes, metadata, labels, boxes
    )
    base = {
        "status": "PRE_INFERENCE_SOURCE_GATE" if validate_only
                  else "PUBLIC_HOST_INFERENCE_COMPLETED",
        "selection_sha256": roster_sha,
        "source_sha256": source_sha,
        "public_images_selected": len(cases),
        "excluded_previous_cat_a2c_ids": 48,
        "category_names": list(CATEGORIES),
        "per_category_positive_and_negative": PER_LABEL,
        "ball_excluded_not_equivalent_to_sports_ball": True,
        "known_low_camera_height_images": 0,
        "physical_scene_independence_verified": False,
        "manual_per_image_license_verification": False,
        "robot_rknn_validated": False,
        "sqlite_writes": 0,
        "motor_commands": 0,
        "qwen_calls": 0,
        "raw_image_ids_or_pixels_published": False,
        "threshold": MIN_SCORE,
    }
    if validate_only:
        return base
    if model is None:
        raise PhotoBaselineError("approved model path is required")
    validate_model_file(model)

    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model), sess_options=opts,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or (session.get_inputs()[0].name, session.get_inputs()[0].shape)
            != ("images", EXPECTED_MODEL_SHAPES[0])
            or (session.get_outputs()[0].name, session.get_outputs()[0].shape)
            != ("output", EXPECTED_MODEL_SHAPES[1])):
        raise PhotoBaselineError("unverified YOLOX runtime interface")

    stats = {
        cat: {
            "positive_images": 0, "negative_images": 0,
            "positive_label_proposed": 0, "verified_negative_false_proposal": 0,
            "gt_instances": 0, "matched_iou50": 0,
            "gt_depiction_boxes": 0, "matched_depiction_boxes": 0,
        } for cat in CATEGORIES
    }
    times = []
    sha_images = []
    seen_images: set[str] = set()
    for case in cases:
        jpeg = _official_jpeg(case.image_id)
        digest = sha256(jpeg).hexdigest()
        if digest in seen_images:
            raise PhotoBaselineError("duplicate public image bytes")
        seen_images.add(digest)
        sha_images.append(digest)
        width, height = _geometry(jpeg)
        tensor = prepare_image(jpeg, mode="original")
        t0 = time.perf_counter()
        output = session.run(None, {"images": tensor})[0]
        times.append(1000 * (time.perf_counter() - t0))
        pred = decode_boxes(output, width=width, height=height)
        relevant = any(b.category == case.category for b in pred)
        d = stats[case.category]
        if case.present:
            d["positive_images"] += 1
            d["positive_label_proposed"] += int(relevant)
            d["gt_instances"] += len(case.boxes)
            d["gt_depiction_boxes"] += sum(
                x.depiction == "1" for x in case.boxes
            )
            matched, depiction = _matched_boxes(
                case.category, case.boxes, pred, width, height
            )
            d["matched_iou50"] += matched
            d["matched_depiction_boxes"] += depiction
        else:
            d["negative_images"] += 1
            d["verified_negative_false_proposal"] += int(relevant)
    reliable = True
    for cat, row in stats.items():
        if (row["positive_images"] != PER_LABEL
                or row["negative_images"] != PER_LABEL
                or row["gt_instances"] <= 0):
            raise PhotoBaselineError("unverified class denominator")
        row["positive_image_sensitivity"] = round(
            row["positive_label_proposed"] / PER_LABEL, 6
        )
        row["negative_false_presence_rate"] = round(
            row["verified_negative_false_proposal"] / PER_LABEL, 6
        )
        row["spatial_iou50_recall"] = round(
            row["matched_iou50"] / row["gt_instances"], 6
        )
        reliable &= (row["positive_image_sensitivity"] >= 0.70
                     and row["negative_false_presence_rate"] <= 0.10)
    base.update({
        "experiment": "Cat-A2d independent Open Images V7 bbox human vote host",
        "model_sha256": MODEL_SHA256,
        "classwise_results": stats,
        "prospective_reliability_gate": "PASS_HOST_ONLY" if reliable
                                        else "STOP_PROMOTION",
        "image_sha256_aggregate": sha256(
            "|".join(sha_images).encode()
        ).hexdigest(),
        "p50_host_inference_ms": round(statistics.median(times), 3),
        "p95_host_inference_ms": round(sorted(times)[
            min(len(times) - 1, math.ceil(0.95 * len(times)) - 1)
        ], 3),
        "host_peak_rss_kib_process": resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss,
        "inference_on_real_public_pixels": True,
        "image_gt_isdepiction_only_not_real_world_presence": True,
        "model_tuning_or_training": False,
    })
    return base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-public-media", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--classes", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--boxes", required=True, type=Path)
    parser.add_argument("--model", type=Path)
    args = parser.parse_args(argv)
    if not args.approved_public_media:
        parser.error("explicit public research usage confirmation required")
    if not args.validate_only and args.model is None:
        parser.error("provide --model for actual inference")
    print(json.dumps(benchmark(
        classes=args.classes, metadata=args.metadata, labels=args.labels,
        boxes=args.boxes, model=args.model, validate_only=args.validate_only,
    ), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
