"""Cat-A2c: public positive-photo *caption concordance* probe on PC only.

Reuses F3-D's 28 previously audited CC0 *declarations*, public-only JPEG
downloader and distinct author roster. Take a fixed 25-photo subset with
cat/dog/chair/ball descriptions plus 3 non-target subjects. Run the SAME
Cat-A YOLOX Nano, unchanged weights, score threshold, preprocessing and
Cat-A2a spatial decoder. Captions describe a visible subject but are NOT
independently audited, exhaustive bounding boxes or low-viewpoint evidence.

A matching proposed category is a caption-level *concordance candidate*,
NOT a true positive. Unmentioned classes are never labeled false positives.
No height for any sample is documented; this CANNOT validate 100-300 mm.
No photos, people identities, model weights or image coordinates are saved.
No camera, robotd, SQLite, Qwen, motor control, model training or tuning.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from io import BytesIO
import argparse
import json
import math
from pathlib import Path
import resource
import statistics
import time

from .cata2_bbox_eval import decode_boxes
from .cata_yolox_categories import (
    CATEGORIES, MIN_SCORE, MODEL_SHA256, SIZE,
    prepare_image, validate_model_file,
)
from .visual_photo_f3d_benchmark import (
    fetch_challenge_photo, host_peak_rss_kib,
)
from .visual_photo_f3d_catalog import (
    CHALLENGE_CATALOG, validate_challenge_catalog,
)
from .visual_photo_mobilenet_demo import PhotoBaselineError

# Deliberately not a new source catalog. Reuse 25 of the frozen F3-D
# public CC0 self-declarations, excluding 3 flowers and no new media.
NON_TARGET_NAMES = frozenset({
    "Flower_photos.jpg", "Silhouette_of_Bird.jpg", "A_lighting_bird.jpg",
})
TARGET_GROUPS = ("cat", "dog", "chair", "ball")
OBSERVED_GROUPS = TARGET_GROUPS + ("bird", "flower")
EXPECTED_GROUPS = {
    "cat": 8, "dog": 8, "chair": 4, "ball": 2, "bird": 2, "flower": 1,
}
EXPECTED_SUBJECT_CLASS = {
    "cat": "cat", "dog": "dog", "chair": "chair",
    "ball": "sports_ball", "bird": None, "flower": None,
}
PROBE_ROSTER = tuple(
    item for item in CHALLENGE_CATALOG
    if item.group in TARGET_GROUPS or item.photo.filename in NON_TARGET_NAMES
)


def validate_probe_roster(roster=PROBE_ROSTER) -> None:
    """Ensure no extra images, category, source or implicit split enters."""
    validate_challenge_catalog()
    if (type(roster) is not tuple or roster != PROBE_ROSTER
            or len(roster) != 25 or dict(Counter(x.group for x in roster)) != EXPECTED_GROUPS
            or len({x.photo.filename for x in roster}) != len(roster)
            or len({x.photo.author for x in roster}) != len(roster)
            or any(x.photo.license != "CC0-1.0" or x.photo.split != "test"
                   for x in roster)):
        raise PhotoBaselineError("non-frozen public challenge roster")


def summarize_caption_proposals(rows: tuple[tuple[str, tuple[str, ...]], ...]) -> dict:
    """Aggregate detector proposals WITHOUT inventing full image ground truth.

    Every image has one public-caption subject group. Other objects could
    appear and the caption author/height/accuracy was not independently
    verified. Never score TP/FP/FN, recall, precision or AP50 from this.
    """
    if (type(rows) is not tuple or len(rows) != len(PROBE_ROSTER)
            or any(type(r) is not tuple or len(r) != 2
                   or type(r[0]) is not str or type(r[1]) is not tuple
                   or r[0] not in EXPECTED_GROUPS
                   or any(type(x) is not str or x not in CATEGORIES for x in r[1])
                   for r in rows)
            or tuple(x[0] for x in rows) != tuple(x.group for x in PROBE_ROSTER)):
        raise PhotoBaselineError("wrong public caption/proposal roster")
    by_subject = {}
    all_proposals = Counter()
    for group in OBSERVED_GROUPS:
        entries = tuple(p for declared, p in rows if declared == group)
        if len(entries) != EXPECTED_GROUPS[group]:
            raise PhotoBaselineError("incomplete public subject group")
        intended = EXPECTED_SUBJECT_CLASS[group]
        for props in entries:
            all_proposals.update(props)
        by_subject[group] = {
            "source_caption_image_count": len(entries),
            "images_with_any_proposed_category": sum(bool(p) for p in entries),
            "images_without_proposed_category": sum(not p for p in entries),
            "images_with_caption_subject_proposed": (
                sum(intended in p for p in entries) if intended else None
            ),
            "other_proposals_not_verified_as_errors": sum(
                sum(q != intended for q in p) for p in entries
            ),
        }
    if sum(all_proposals.values()) > len(PROBE_ROSTER)*80:
        raise PhotoBaselineError("unbounded category output count")
    return {
        "status": "public_caption_agreement_host_not_low_camera_validation",
        "photos": len(rows),
        "by_public_caption_subject_not_independent_gt": by_subject,
        "proposed_boxes_by_yolox_category_not_tp": {
            name: all_proposals[name] for name in CATEGORIES
        },
        "declared_positive_photos": sum(
            EXPECTED_GROUPS[x] for x in TARGET_GROUPS
        ),
        "declared_non_target_photos_not_verified_negatives": (
            EXPECTED_GROUPS["bird"] + EXPECTED_GROUPS["flower"]
        ),
        "person_class_caption_positive_photos": 0,
        "proposed_other_classes_are_not_false_positives": True,
        "source_descriptions_independently_verified": False,
        "exhaustive_bbox_ground_truth_available": False,
        "precision_recall_f1_ap50": None,
        "optical_center_height_per_photo_mm": None,
        "photos_verified_camera_height_100_to_300mm": 0,
        "independent_scene_or_pretraining_overlap_audited": False,
    }


def run_public_caption_probe(*, model_path: Path) -> dict:
    """Evaluate 25 genuine public *source-catalog* photos on host Linux CPU.

    Any failed fetch or malformed photo aborts the entire experiment; no
    partial score and no reclassification of missing groups as negatives.
    """
    validate_probe_roster()
    validate_model_file(model_path)
    from PIL import Image
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]
            or session.get_providers() != ["CPUExecutionProvider"]):
        raise PhotoBaselineError("unsupported Cat-A YOLOX CPU signature")
    start = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    rows = []
    image_digests = set()
    inference_times = []
    raw_bytes = 0
    for entry in PROBE_ROSTER:
        jpeg = fetch_challenge_photo(entry.photo)
        digest = sha256(jpeg).hexdigest()
        if digest in image_digests:
            raise PhotoBaselineError("duplicate exact public thumbnail")
        image_digests.add(digest)
        raw_bytes += len(jpeg)
        with Image.open(BytesIO(jpeg)) as img:
            if (img.format != "JPEG" or min(img.size) < 32
                    or max(img.size) > 4096
                    or img.getexif().get(274, 1) != 1):
                raise PhotoBaselineError("bad public thumbnail geometry")
            img.load()
            width, height = img.size
        tensor = prepare_image(jpeg, mode="original")
        begin = time.perf_counter()
        raw = session.run(None, {"images": tensor})[0]
        inference_times.append((time.perf_counter() - begin)*1000)
        boxes = decode_boxes(raw, width=width, height=height)
        rows.append((entry.group, tuple(box.category for box in boxes)))
        del jpeg, tensor, raw, boxes
    if len(image_digests) != 25:
        raise PhotoBaselineError("missing public thumbnail")
    report = summarize_caption_proposals(tuple(rows))
    ordered = sorted(inference_times)
    after = resource.getrusage(resource.RUSAGE_SELF)
    report.update({
        "source": "F3-D_Wikimedia_Commons_CC0_operator_declarations",
        "same_frozen_F3D_catalog_no_new_media": True,
        "source_license_declarations_not_verified_legal_title": True,
        "thumbnail_bytes_change_without_pin": True,
        "model_sha256": MODEL_SHA256,
        "predeclared_yolox_min_score": MIN_SCORE,
        "photos_train_or_test_independently_verified": False,
        "host_cpu_inference_ms_median": round(statistics.median(ordered), 3),
        "host_cpu_inference_ms_p95": round(
            ordered[math.ceil(.95*len(ordered))-1], 3
        ),
        "host_process_peak_rss_kib": host_peak_rss_kib(),
        "host_process_user_cpu_s": round(after.ru_utime-before.ru_utime, 3),
        "host_wall_with_downloads_s": round(time.perf_counter()-start, 3),
        "transient_public_jpeg_total_bytes": raw_bytes,
        "thumbnail_sha256_digest_of_digests": sha256(
            "".join(sorted(image_digests)).encode("ascii")
        ).hexdigest(),
        "media_published_or_saved": False,
        "model_training_or_threshold_tuning": False,
        "robot_camera_or_rknn_validated": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
        "qwen_calls": 0,
    })
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--approved-public-cc0-media", action="store_true")
    args = parser.parse_args(argv)
    if not args.approved_public_cc0_media:
        parser.error("explicit public CC0 research permission gate required")
    print(json.dumps(
        run_public_caption_probe(model_path=args.model_path),
        sort_keys=True, allow_nan=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
