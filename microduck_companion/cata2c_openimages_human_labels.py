"""Cat-A2c: actual public Open Images V7 human-label cross-dataset CPU probe.

ONE bounded, deterministic, *real* image-level evaluation on a fixed COCO
YOLOX-Nano model. This probes a new PUBLIC photographic distribution, not
the 25 cm Microduck camera, not independent scenes, not object localization
mAP, not causal learning, and not an unknown-object rejection test.

All photos and the ONNX model stay transient in the runner. No private
captures, identities, labels per image, camera, robotd, SQLite, Qwen, or
robot action. Live downloads occur ONLY after explicit --approved-public-media.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO, StringIO
import argparse
import csv
import json
import math
from pathlib import Path
import re
import resource
import statistics
import time
import urllib.request

from .cata_yolox_categories import (
    MODEL_SHA256, MIN_SCORE, SIZE, prepare_image, validate_model_file,
)
from .cata2_bbox_eval import decode_boxes
from .visual_photo_mobilenet_demo import PhotoBaselineError

# Official Open Images. Metadata/annotations: Google, CC BY 4.0.
# Original photos: individually credited CC BY 2.0 *as declared* in metadata,
# which Google does NOT guarantee is a current permission for every photo.
# Never redistribute images. The use is a small transient research probe.
METADATA_URL = (
    "https://storage.googleapis.com/openimages/2018_04/validation/"
    "validation-images-with-rotation.csv"
)
HUMAN_LABELS_URL = (
    "https://storage.googleapis.com/openimages/v7/"
    "oidv7-val-annotations-human-imagelabels.csv"
)
CLASS_NAMES_URL = (
    "https://storage.googleapis.com/openimages/v7/"
    "oidv7-class-descriptions-boxable.csv"
)
IMAGE_URL_BASE = "https://open-images-dataset.s3.amazonaws.com/validation/"
ALLOWED_LICENSES = frozenset({
    "https://creativecommons.org/licenses/by/2.0/",
    "http://creativecommons.org/licenses/by/2.0/",
})
SEED = "kwipi-a2c-v1-human-verified-fixed-model-no-tuning"
# Not all Open Images "Ball" objects are COCO "sports_ball": exclude.
# These names *must* match the official metadata, not a guess at MIDs.
CLASS_MAPPING = {
    "person": "Person", "cat": "Cat", "dog": "Dog", "chair": "Chair",
}
SAMPLES_PER_BINARY_LABEL = 6
# Digests measured on the FIRST real, successful pilot CI run #40722697441.
# Freeze official metadata before using this as a reproducible holdout.
SOURCE_SHA256 = {
    "class": "1839e0e7e84130ae281f7f67413768601b031581c0c42e7fc17527b8e2a99aa9",
    "human_labels": "92ddbdfceb3626e044df5e89100b24f6c22a79c1888a4bddd00a6f231d86d56a",
    "metadata": "ed93a0e121fe345effdfc7359b848dbc64a1ff6778c8c73563157cb500b33a17",
}
COHORT_SHA256 = "608aa803df32cff206267fdc40c926a0c64783889dc79861cd0a92625d23627b"
# Hash of the 48 JPEG SHA-256 strings in frozen cohort order (no pixels published).
IMAGE_CONTENTS_SHA256 = "e5ea24c3c9db2b9fd13dd45287b41885ddfb4dd7fe5141f5ebcaa78d473b69e3"

META_LIMIT = 45_000_000
LABELS_LIMIT = 55_000_000
CLASS_LIMIT = 150_000
IMAGE_LIMIT = 2_500_000
MAX_DURATION = 40
IMAGE_ID_PATTERN = re.compile(r"[0-9a-f]{16}\Z", re.ASCII)
ALLOWED_HUMAN_SOURCE = frozenset({"verification", "crowdsource-verification"})


@dataclass(frozen=True)
class VerifiedCase:
    image_id: str
    category: str
    present: bool


def _csv_rows(raw: bytes, *, required: frozenset[str], cap: int):
    if type(raw) is not bytes or not 20 <= len(raw) <= cap:
        raise PhotoBaselineError("bounded official CSV required")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text), strict=True)
        if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise PhotoBaselineError("duplicate/missing CSV header")
        if not required.issubset(set(reader.fieldnames)):
            raise PhotoBaselineError("official CSV fields changed")
        for row in reader:
            if not isinstance(row, dict) or None in row:
                raise PhotoBaselineError("malformed CSV entry")
            yield row
    except (UnicodeError, csv.Error, ValueError) as exc:
        raise PhotoBaselineError("unreadable official CSV") from exc


def select_human_verified_cases(
    class_csv: bytes, metadata_csv: bytes, human_labels_csv: bytes,
    *, per_label: int = SAMPLES_PER_BINARY_LABEL,
) -> tuple[VerifiedCase, ...]:
    """Choose one frozen cohort BEFORE model inference (no prediction tuning).

    Every selected (image, class) label is explicitly verified as present
    or absent by a human in Open Images. No claim is made about the other
    class labels for that image or about a physically independent scene.
    """
    if type(per_label) is not int or not 1 <= per_label <= 6:
        raise PhotoBaselineError("bounded cohort size required")

    # Official boxable class-descriptions CSV has TWO columns WITHOUT a
    # header (unlike the image metadata and human labels CSV files).
    if type(class_csv) is not bytes or not 16 <= len(class_csv) <= CLASS_LIMIT:
        raise PhotoBaselineError("bounded official class descriptions required")
    try:
        class_rows = csv.reader(StringIO(class_csv.decode("utf-8-sig")), strict=True)
        ids_by_name: dict[str, set[str]] = {}
        for idx, row in enumerate(class_rows):
            # V7 source may include the official two-column CSV header;
            # older class description releases omit it.
            if idx == 0 and row == ["LabelName", "DisplayName"]:
                continue
            if len(row) != 2 or not row[0].startswith("/m/"):
                raise PhotoBaselineError("unexpected official MID/name format")
            mid, name = row
            if name in CLASS_MAPPING.values():
                ids_by_name.setdefault(name, set()).add(mid)
    except (UnicodeError, csv.Error, ValueError) as exc:
        raise PhotoBaselineError("invalid public class metadata") from exc
    mids = {}
    for category, target in CLASS_MAPPING.items():
        entries = ids_by_name.get(target, set())
        if len(entries) != 1:
            raise PhotoBaselineError("Open Images class mapping is ambiguous")
        mids[next(iter(entries))] = category

    # Public author/license metadata, never display the author, title or URL.
    # Explicit 0 rotation avoids a hidden image-frame mismatch.
    licensed: set[str] = set()
    seen_meta: set[str] = set()
    for row in _csv_rows(
        metadata_csv,
        required=frozenset({
            "ImageID", "Subset", "License", "OriginalSize", "Rotation",
        }), cap=META_LIMIT,
    ):
        image_id = row["ImageID"]
        if not IMAGE_ID_PATTERN.fullmatch(image_id) or image_id in seen_meta:
            raise PhotoBaselineError("invalid or duplicate public image ID")
        seen_meta.add(image_id)
        if (row["Subset"] != "validation"
                or row["License"] not in ALLOWED_LICENSES
                or row["Rotation"] not in {"0", "0.0"}
                or not row["OriginalSize"].isdigit()
                or not 100 <= int(row["OriginalSize"]) <= IMAGE_LIMIT):
            continue
        licensed.add(image_id)
    if len(licensed) < per_label * 2 * len(CLASS_MAPPING):
        raise PhotoBaselineError("too few eligible public photo licenses")

    # Strictly use human-verified binary image labels, not model labels,
    # missing annotations, or labels assumed negative from absence of a box.
    votes: dict[tuple[str, str], set[bool]] = {}
    for row in _csv_rows(
        human_labels_csv,
        required=frozenset({
            "ImageID", "Source", "LabelName", "Confidence",
        }), cap=LABELS_LIMIT,
    ):
        category = mids.get(row["LabelName"])
        if (category is None or row["Source"] not in ALLOWED_HUMAN_SOURCE
                or row["ImageID"] not in licensed):
            continue
        raw_confidence = row["Confidence"]
        if raw_confidence not in {"0", "1", "0.0", "1.0"}:
            raise PhotoBaselineError("nonbinary purported human annotation")
        votes.setdefault((row["ImageID"], category), set()).add(
            raw_confidence in {"1", "1.0"}
        )

    # Exclude contradictions instead of falsely adjudicating two humans.
    pools: dict[tuple[str, bool], list[str]] = {
        (c, b): [] for c in CLASS_MAPPING for b in (True, False)
    }
    for (image_id, category), values in votes.items():
        if len(values) == 1:
            pools[(category, next(iter(values)))].append(image_id)

    selected: list[VerifiedCase] = []
    taken: set[str] = set()
    for category in CLASS_MAPPING:
        for present in (True, False):
            candidates = sorted(
                (x for x in pools[(category, present)] if x not in taken),
                key=lambda x: (
                    sha256(f"{SEED}/{category}/{int(present)}/{x}".encode()).digest(),
                    x,
                ),
            )
            if len(candidates) < per_label:
                raise PhotoBaselineError("insufficient disjoint verified class samples")
            for image_id in candidates[:per_label]:
                selected.append(VerifiedCase(image_id, category, present))
                taken.add(image_id)
    return tuple(selected)


def binary_metrics(cases: tuple[VerifiedCase, ...], found: tuple[bool, ...]) -> dict:
    """Per-target 2x2 measured outcomes; never call this object-level AP."""
    if (type(cases) is not tuple or type(found) is not tuple
            or len(cases) != len(found) or not cases
            or any(type(v) is not bool for v in found)):
        raise PhotoBaselineError("invalid prediction/verification pairing")
    out = {}
    for category in CLASS_MAPPING:
        index = [i for i, c in enumerate(cases) if c.category == category]
        tp = sum(cases[i].present and found[i] for i in index)
        fn = sum(cases[i].present and not found[i] for i in index)
        tn = sum(not cases[i].present and not found[i] for i in index)
        fp = sum(not cases[i].present and found[i] for i in index)
        if not index or tp + fn == 0 or tn + fp == 0:
            raise PhotoBaselineError("missing positive or negative class control")
        out[category] = {
            "positive_images": tp + fn, "negative_images": tn + fp,
            "tp": tp, "fn": fn, "tn": tn, "fp": fp,
            "sensitivity": round(tp / (tp + fn), 6),
            "specificity": round(tn / (tn + fp), 6),
        }
    return out


def _official_jpeg(image_id: str) -> bytes:
    if type(image_id) is not str or not IMAGE_ID_PATTERN.fullmatch(image_id):
        raise PhotoBaselineError("invalid official image identifier")
    request = urllib.request.Request(
        IMAGE_URL_BASE + image_id + ".jpg",
        headers={"User-Agent": "MicroduckCompanion-PublicHostBenchmark/1.0"},
    )
    with urllib.request.urlopen(request, timeout=MAX_DURATION) as response:
        if response.url != IMAGE_URL_BASE + image_id + ".jpg":
            raise PhotoBaselineError("public image redirected to unapproved host")
        image = response.read(IMAGE_LIMIT + 1)
    if not 100 <= len(image) <= IMAGE_LIMIT:
        raise PhotoBaselineError("missing/oversize public JPEG")
    return image


def benchmark(*, model_path: Path, class_path: Path,
              metadata_path: Path, labels_path: Path) -> dict:
    validate_model_file(model_path)
    source_data = {
        "class": class_path.read_bytes(), "metadata": metadata_path.read_bytes(),
        "human_labels": labels_path.read_bytes(),
    }
    actual_digests = {
        key: sha256(value).hexdigest() for key, value in source_data.items()
    }
    if actual_digests != SOURCE_SHA256:
        raise PhotoBaselineError("official public metadata changed since pilot")
    cases = select_human_verified_cases(
        source_data["class"], source_data["metadata"], source_data["human_labels"],
    )
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
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise PhotoBaselineError("unverified YOLOX runtime/model interface")
    predictions: list[bool] = []
    times: list[float] = []
    digests: set[str] = set()
    ordered_image_hashes: list[str] = []
    start = time.perf_counter()
    for item in cases:
        image = _official_jpeg(item.image_id)
        sha = sha256(image).hexdigest()
        if sha in digests:
            raise PhotoBaselineError("duplicate public image bytes")
        digests.add(sha)
        ordered_image_hashes.append(sha)
        model_input = prepare_image(image, mode="original")
        t0 = time.perf_counter()
        raw = session.run(None, {"images": model_input})[0]
        times.append((time.perf_counter() - t0) * 1000)
        width, height = _image_size(image)
        boxes = decode_boxes(raw, width=width, height=height)
        predictions.append(any(box.category == item.category for box in boxes))
    cohort_roster = "|".join(
        f"{x.image_id}/{x.category}/{int(x.present)}" for x in cases
    )
    if sha256(cohort_roster.encode()).hexdigest() != COHORT_SHA256:
        raise PhotoBaselineError("selected public holdout roster changed")
    image_contents = sha256("|".join(ordered_image_hashes).encode()).hexdigest()
    if image_contents != IMAGE_CONTENTS_SHA256:
        raise PhotoBaselineError("public photo bytes differ from measured cohort")
    return {
        "experiment": "Cat-A2c Open Images V7 human-verified binary holdout",
        "category_results": binary_metrics(cases, tuple(predictions)),
        "total_public_images": len(cases),
        "source_file_sha256": {
            key: sha256(value).hexdigest() for key, value in source_data.items()
        },
        "roster_sha256": sha256(cohort_roster.encode()).hexdigest(),
        "image_contents_sha256": sha256("|".join(ordered_image_hashes).encode()).hexdigest(),
        "model_sha256": MODEL_SHA256,
        "threshold_unchanged": MIN_SCORE,
        "median_host_inference_ms": round(statistics.median(times), 3),
        "host_elapsed_s": round(time.perf_counter() - start, 3),
        "host_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "human_labels_verified_by_dataset_not_locally_adjudicated": True,
        "train_image_overlap_excluded_by_coco_vs_openimages": False,
        "independent_physical_scenes_verified": 0,
        "known_low_camera_height_images": 0,
        "sports_ball_class_tested": False,
        "unknown_object_rejection_tested": False,
        "bbox_map_validated": False,
        "model_trained_or_tuned_on_test": False,
        "robot_rknn_validated": False,
        "memory_generalization_c3_validated": False,
        "sqlite_writes": 0,
        "motor_commands": 0,
        "raw_images_or_ids_published": False,
    }


def _image_size(jpeg: bytes) -> tuple[int, int]:
    # Consume the same JPEG bytes; a second full decode is avoided by Pillow
    # lazy metadata access. EXIF orientation is irrelevant for image-level
    # presence; boxes and ground-truth rectangles are NOT evaluated here.
    from PIL import Image
    with Image.open(BytesIO(jpeg)) as image:
        if image.format != "JPEG":
            raise PhotoBaselineError("not JPEG")
        return image.size


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-media", action="store_true")
    p.add_argument("--model-path", type=Path, required=True)
    p.add_argument("--classes-path", type=Path, required=True)
    p.add_argument("--metadata-path", type=Path, required=True)
    p.add_argument("--labels-path", type=Path, required=True)
    args = p.parse_args(argv)
    if not args.approved_public_media:
        p.error("explicit public CC BY research use approval required")
    print(json.dumps(benchmark(
        model_path=args.model_path, class_path=args.classes_path,
        metadata_path=args.metadata_path, labels_path=args.labels_path,
    ), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
