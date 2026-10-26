"""Cat-A: host-only category DETECTOR evaluation, never instance identity.

Reuses existing F3-B reviewed CC0 photographs and F3/ABO CHAIR sources.
YOLOX-Nano/COCO pretrained weights are ephemeral, SHA256-pinned and Apache-2.0.
No ultralytics package, new SQLite, robotd/mediad, raw media archive or Qwen.
The test is IMAGE-level category presence, not box mAP or robot-low camera.
The bottom-half JPEG crop is an *artificial occlusion*, not an independent photo.
"""
from __future__ import annotations

from collections import Counter
from io import BytesIO
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import time

from .visual_photo_baseline import fetch_thumbnail, validate_catalog
from .visual_photo_catalog import PHOTO_CATALOG
from .visual_photo_mobilenet_demo import PhotoBaselineError
from .r2b_independent_capture_eval import (
    ABO_HOST, ABO_MAX_JPEG_BYTES, _abo_https_bytes, _abo_spin_sample,
)
from .r2b2_abo_confusables import SHARDS, LISTING_BASE, _read_metadata, _parse_listings

# Megvii YOLOX official release 0.1.1rc0 re-exported losslessly by SkillSafe.
# Copyright (c) 2021-2022 Megvii Inc.; Apache-2.0.
MODEL_URL = (
    "https://huggingface.co/skillsafe-ai/yolox-nano/"
    "resolve/8e308810ede488f742901a4ac597dc7796798e46/yolox_nano.onnx"
)
MODEL_SHA256 = "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
MODEL_LICENSE = "Apache-2.0"
SIZE = 416
# Official COCO 80-class indices. No "shoe", "hand", "foot", "human head"
# or arbitrary personal name is supported by this model.
CATEGORIES = {
    "person": 0, "cat": 15, "dog": 16,
    "sports_ball": 32, "chair": 56,
}
MIN_SCORE = 0.25  # Predeclared; NEVER adjusted after observing test metrics.
MAX_IMAGE_BYTES = 2_500_000
CHAIR_SPINS = 12
MODES = ("original", "bottom_half")
ALL_TARGET_IDS = frozenset(CATEGORIES.values())


def validate_model_file(path: Path) -> None:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise PhotoBaselineError("approved YOLOX ONNX file required")
    if not 3_000_000 <= path.stat().st_size <= 4_500_000:
        raise PhotoBaselineError("incorrect YOLOX model byte length")
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for part in iter(lambda: fp.read(128 * 1024), b""):
            digest.update(part)
    if digest.hexdigest() != MODEL_SHA256:
        raise PhotoBaselineError("YOLOX weights SHA256 mismatch")


def prepare_image(jpeg: bytes, *, mode: str):
    """Official YOLOX letterbox: BGR float32, raw 0..255, top-left align."""
    import numpy as np
    from PIL import Image, ImageOps

    if (type(jpeg) is not bytes or not 100 <= len(jpeg) <= MAX_IMAGE_BYTES
            or not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9")
            or mode not in MODES):
        raise PhotoBaselineError("invalid bounded JPEG or crop mode")
    try:
        with Image.open(BytesIO(jpeg)) as source:
            if (source.format != "JPEG" or min(source.size) < 32
                    or max(source.size) > 4096):
                raise PhotoBaselineError("invalid original JPEG geometry")
            rgb = ImageOps.exif_transpose(source).convert("RGB")
        if mode == "bottom_half":
            # Deterministic synthetic occlusion; never claim a real 25cm view.
            rgb = rgb.crop((0, rgb.height // 2, rgb.width, rgb.height))
        ratio = min(SIZE / rgb.width, SIZE / rgb.height)
        width = max(1, round(rgb.width * ratio))
        height = max(1, round(rgb.height * ratio))
        resized = rgb.resize((width, height), Image.Resampling.BILINEAR)
        padded = np.full((SIZE, SIZE, 3), 114, dtype=np.uint8)
        padded[:height, :width] = np.asarray(resized, dtype=np.uint8)
        chw_bgr = np.transpose(padded[:, :, ::-1], (2, 0, 1))[None, ...]
        return np.ascontiguousarray(chw_bgr, dtype=np.float32)
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, PhotoBaselineError):
            raise
        raise PhotoBaselineError("invalid JPEG preprocess") from exc


def _grid():
    import numpy as np
    matrices, steps = [], []
    for stride in (8, 16, 32):
        d = SIZE // stride
        y, x = np.meshgrid(np.arange(d), np.arange(d), indexing="ij")
        matrices.append(np.stack((x, y), axis=-1).reshape(-1, 2))
        steps.append(np.full((d * d, 1), stride))
    return np.concatenate(matrices).astype(np.float32), np.concatenate(steps).astype(np.float32)


def decode_categories(raw) -> tuple[str, float, dict]:
    """Decode raw YOLOX heads. Output is *unverified* detector category."""
    import numpy as np
    data = np.asarray(raw)
    if (data.shape != (1, 3549, 85) or not np.isfinite(data).all()
            or not np.issubdtype(data.dtype, np.floating)):
        raise PhotoBaselineError("unexpected/nonfinite YOLOX prediction layout")
    a = data[0].astype(np.float32)
    grid, step = _grid()
    with np.errstate(over="ignore", invalid="ignore"):
        xy = (a[:, :2] + grid) * step
        wh = np.exp(a[:, 2:4]) * step
    if not np.isfinite(xy).all() or not np.isfinite(wh).all():
        raise PhotoBaselineError("YOLOX box decode overflow")
    if (np.any(a[:, 4:] < 0) or np.any(a[:, 4:] > 1)):
        raise PhotoBaselineError("YOLOX object and class scores are not probabilities")
    scores = a[:, 4:5] * a[:, 5:]
    # A box must actually overlap the 416 px input. No sensor/localization proof.
    valid = ((wh > 1).all(axis=1)
             & (xy[:, 0] + wh[:, 0] / 2 > 0)
             & (xy[:, 1] + wh[:, 1] / 2 > 0)
             & (xy[:, 0] - wh[:, 0] / 2 < SIZE)
             & (xy[:, 1] - wh[:, 1] / 2 < SIZE))
    confidences = {
        category: float(np.max(scores[valid, index])) if valid.any() else 0.0
        for category, index in CATEGORIES.items()
    }
    label, score = max(confidences.items(), key=lambda x: (x[1], x[0]))
    # An image can contain multiple categories. This toy image-level label
    # chooses exactly one largest score; separate box mAP is *not* evaluated.
    return (label if score >= MIN_SCORE else "unknown",
            round(score, 6), confidences)


def _metrics(rows: list[tuple[str, str]]) -> dict:
    if not rows:
        raise PhotoBaselineError("nonempty holdout required")
    truth_counts = Counter(a for a, _ in rows)
    correct_by_class = Counter(a for a, b in rows if a == b)
    mistakes = Counter((a, b) for a, b in rows if a != b)
    return {
        "samples": len(rows), "correct": sum(a == b for a, b in rows),
        "accuracy_image_level": round(sum(a == b for a, b in rows) / len(rows), 6),
        "per_truth": {
            k: {"count": n, "correct": correct_by_class[k],
                "rejected_as_unknown": sum(a == k and b == "unknown" for a, b in rows)}
            for k, n in sorted(truth_counts.items())
        },
        "errors": [
            {"expected": a, "predicted": b, "count": n}
            for (a, b), n in sorted(mistakes.items())
        ],
    }


def evaluate(*, model_path: Path, with_abo_chairs: bool = True) -> dict:
    """Apply fixed score to the pre-existing author-separated CC0 test split.

    Auxiliary ABO chair images are a separately reported catalogue-labelled
    domain probe and must not be mixed with the author-separated CC0 scores.
    """
    validate_model_file(model_path)
    validate_catalog()
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=options,
        providers=["CPUExecutionProvider"])
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise PhotoBaselineError("unreviewed YOLOX ONNX interface")
    start = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    times = []
    rows: dict[str, dict[str, list[tuple[str,str]]]] = {
        split: {mode: [] for mode in MODES}
        for split in ("train", "validation", "test")}
    digests = []
    cc0_digests = []
    abo_digests = []
    abo_spin_roster_digest = None
    def score_one(jpeg: bytes, truth: str, split: str) -> None:
        digest = hashlib.sha256(jpeg).hexdigest()
        digests.append(digest)
        cc0_digests.append(digest)
        for mode in MODES:
            image = prepare_image(jpeg, mode=mode)
            t0 = time.perf_counter()
            prediction = session.run(None, {"images": image})[0]
            times.append((time.perf_counter() - t0) * 1000)
            predicted, _, _ = decode_categories(prediction)
            rows[split][mode].append((truth, predicted))

    for photo in PHOTO_CATALOG:
        jpeg = fetch_thumbnail(photo)
        score_one(jpeg, photo.category, photo.split)

    extras = {}
    if with_abo_chairs:
        chunks = tuple(_read_metadata(LISTING_BASE.format(i)) for i in SHARDS)
        catalogue = _parse_listings(chunks)
        selected = _abo_spin_sample(
            allowed_spin_ids=frozenset(catalogue), source_count=CHAIR_SPINS)
        if len(selected) != CHAIR_SPINS or len({catalogue[x] for x, _ in selected}) != CHAIR_SPINS:
            raise PhotoBaselineError("ABO chair catalogue item separation failed")
        abo_spin_roster_digest = hashlib.sha256(
            "|".join(spin for spin, _ in selected).encode()).hexdigest()
        chair_records: dict[str, list[tuple[str, str]]] = {m: [] for m in MODES}
        for _, views in selected:
            # One fixed angle per catalog item, *not* a multi-view claim.
            raw = _abo_https_bytes(
                "https://" + ABO_HOST + "/spins/original/" + views[0],
                limit=ABO_MAX_JPEG_BYTES)
            digest = hashlib.sha256(raw).hexdigest()
            digests.append(digest)
            abo_digests.append(digest)
            for mode in MODES:
                image = prepare_image(raw, mode=mode)
                t0 = time.perf_counter()
                prediction = session.run(None, {"images": image})[0]
                times.append((time.perf_counter() - t0) * 1000)
                label, _, _ = decode_categories(prediction)
                chair_records[mode].append(("chair", label))
        extras = {
            "label_source": "ABO_product_type_CHAIR_not_manual_boxes",
            "distinct_catalogue_item_ids_not_physical_instances": CHAIR_SPINS,
            "camera_height_not_known": True,
            "metrics": {m: _metrics(v) for m,v in chair_records.items()},
        }
    after = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "scenario": "Cat-A host-only YOLOX-nano public CC0 photo categories",
        "robot_name": "Kwipi",
        "model_url": MODEL_URL,
        "model_sha256": MODEL_SHA256,
        "model_license": MODEL_LICENSE,
        "model_bytes": model_path.stat().st_size,
        "coco_class_mapping": CATEGORIES,
        "unsupported_requested_classes": [
            "shoe", "hand", "foot", "forearm", "paw", "human_head"],
        "threshold_fixed_a_priori": MIN_SCORE,
        "cc0_photo_split": {"train": 8, "validation": 6, "test": 6},
        "cc0_source_label_limitations": "file-page declarative CC0/photographer, image-level",
        "cc0_metrics": {
            split: {mode: _metrics(v) for mode, v in groups.items()}
            for split, groups in rows.items()
        },
        "abo_chair_probe": extras,
        "synthetic_partial_view": "bottom_half_crop_same_real_photo_not_independent_capture",
        "real_low_height_camera_images": 0,
        "person_and_ball_annotated_test_images": 0,
        "person_face_or_individual_identity_inference": False,
        "true_bbox_detection_map": None,
        "media_downloads_not_saved": True,
        "unique_original_jpegs": len(digests),
        "repeated_original_jpegs": len(digests) - len(set(digests)),
        "media_sha256_digest_of_digests": hashlib.sha256(
            "".join(sorted(digests)).encode()).hexdigest(),
        "cc0_media_digest": hashlib.sha256(
            "".join(cc0_digests).encode()).hexdigest(),
        "abo_media_digest": hashlib.sha256(
            "".join(abo_digests).encode()).hexdigest() if abo_digests else None,
        "abo_spin_roster_digest": abo_spin_roster_digest,
        "cc0_ordered_image_sha256": cc0_digests,
        "abo_ordered_image_sha256": abo_digests,
        "host_onnx_ms_median": round(statistics.median(times), 3),
        "host_onnx_ms_max": round(max(times), 3),
        "host_cpu_user_s_includes_preprocess": round(after.ru_utime-before.ru_utime, 3),
        "host_rss_peak_kib_process": after.ru_maxrss,
        "wall_s_includes_downloads": round(time.perf_counter()-start, 3),
        "hardware_or_robot_validated": False,
        "motor_commands": 0, "sqlite_writes": 0, "qwen_calls": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--approved-public-media", action="store_true")
    parser.add_argument("--no-chair-probe", action="store_true")
    options = parser.parse_args(argv)
    if not options.approved_public_media:
        parser.error("explicit public-license/media audit approval required")
    result = evaluate(model_path=options.model_path,
                      with_abo_chairs=not options.no_chair_probe)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
