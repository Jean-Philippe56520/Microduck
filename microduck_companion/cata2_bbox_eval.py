"""Cat-A2a: bounded, real COCO-val bbox evaluation of existing Cat-A YOLOX.

This is a *host-only* benchmark, NOT a robot camera / low-height test:
COCO's camera height is unrecorded. Photos are fetched transiently and only
from the fixed official image hostname; annotations are SHA256 pinned and
source-image licenses are filtered to the explicit Creative Commons BY grant.
No new model, media archive, capture, SQLite, network on import, Qwen, robotd,
motion, NPU assumption, identity, or threshold tuning is introduced.

Metrics: classwise IoU>=0.5 one-to-one matching, micro precision/recall,
101-point interpolated AP50 for supported classes. These are NOT official COCO
mAP across its entire 5000-image validation set, and NOT low-height mAP.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import time
import urllib.request

from .cata_yolox_categories import (
    CATEGORIES, MAX_IMAGE_BYTES, MIN_SCORE, MODEL_SHA256, MODEL_LICENSE,
    MODEL_URL, SIZE, _grid, prepare_image, validate_model_file,
)
from .visual_photo_mobilenet_demo import PhotoBaselineError

# Annotations: COCO Consortium, CC BY 4.0, republished losslessly by LibreYOLO.
ANNOTATIONS_URL = (
    "https://huggingface.co/datasets/LibreYOLO/coco2017/resolve/"
    "main/instances_val2017.json"
)
ANNOTATIONS_SHA256 = (
    "e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aee fa635b8c810b6f"
).replace(" ", "")
# COCO annotation category_id != zero-based YOLO/ONNX class indices.
COCO_IDS = {"person": 1, "cat": 17, "dog": 18, "sports_ball": 37, "chair": 62}
# Conservative image-rights filter: CC BY 2.0 only (not BY-NC, BY-ND,
# unknown or derivative-unreviewed). Metadata is a declaration, not a grant
# independently proved for each Flickr original; no image is republished.
PHOTO_LICENSE_NAME = "Attribution License"
PHOTO_LICENSE_URL = "http://creativecommons.org/licenses/by/2.0/"
SEED = "kwipi-cat-a2a-unbiased-v1"
PER_CLASS = 4
NEGATIVES = 4
MAX_COCO_JSON_BYTES = 30_000_000
MAX_SELECTED = 25
MAX_RESULTS = 80
MAX_PRE_NMS = 160
NMS_IOU = 0.50
MATCH_IOU = 0.50
MAX_DIMENSION = 4096
IMAGE_HOST = "https://s3.amazonaws.com/images.cocodataset.org/val2017/"


@dataclass(frozen=True)
class Box:
    category: str
    xyxy: tuple[float, float, float, float]
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if (self.category not in CATEGORIES or type(self.xyxy) is not tuple
                or len(self.xyxy) != 4 or any(
                    type(v) not in (float, int) or not math.isfinite(v)
                    for v in self.xyxy
                ) or self.xyxy[2] <= self.xyxy[0]
                or self.xyxy[3] <= self.xyxy[1]
                or type(self.confidence) is not float
                or not math.isfinite(self.confidence)
                or not 0 <= self.confidence <= 1):
            raise PhotoBaselineError("invalid labeled detection/ground truth box")


@dataclass(frozen=True)
class CocoCase:
    image_id: int
    filename: str
    width: int
    height: int
    ground_truth: tuple[Box, ...]

    def __post_init__(self) -> None:
        if (type(self.image_id) is not int or self.image_id < 0
                or self.filename != f"{self.image_id:012d}.jpg"
                or any(type(d) is not int or d < 32 or d > MAX_DIMENSION
                       for d in (self.width, self.height))
                or type(self.ground_truth) is not tuple
                or any(not isinstance(b, Box)
                       or b.xyxy[0] < 0 or b.xyxy[1] < 0
                       or b.xyxy[2] > self.width
                       or b.xyxy[3] > self.height
                       for b in self.ground_truth)):
            raise PhotoBaselineError("invalid COCO sample/geometry")


def iou(a: Box, b: Box) -> float:
    """Exact xyxy intersection-over-union, no inclusive-pixel +1 fudge."""
    if not isinstance(a, Box) or not isinstance(b, Box):
        raise TypeError("two boxes required")
    left = max(a.xyxy[0], b.xyxy[0])
    top = max(a.xyxy[1], b.xyxy[1])
    right = min(a.xyxy[2], b.xyxy[2])
    bottom = min(a.xyxy[3], b.xyxy[3])
    intersection = max(0., right - left) * max(0., bottom - top)
    area_a = (a.xyxy[2] - a.xyxy[0]) * (a.xyxy[3] - a.xyxy[1])
    area_b = (b.xyxy[2] - b.xyxy[0]) * (b.xyxy[3] - b.xyxy[1])
    return intersection / (area_a + area_b - intersection)


def decode_boxes(raw: object, *, width: int, height: int) -> tuple[Box, ...]:
    """Use the existing Cat-A YOLOX heads / official top-left letterbox.

    Unlike the old image-level score this preserves multiple spatial boxes,
    clips padding away, NMS-filters per category and limits output. Inference
    weights and predeclared score threshold remain exactly as in Cat-A.
    """
    if any(type(v) is not int or not 32 <= v <= MAX_DIMENSION
           for v in (width, height)):
        raise PhotoBaselineError("original geometry must be verified first")
    import numpy as np
    data = np.asarray(raw)
    if (data.shape != (1, 3549, 85)
            or not np.issubdtype(data.dtype, np.floating)
            or not np.isfinite(data).all()):
        raise PhotoBaselineError("unexpected/nonfinite YOLOX head")
    a = data[0].astype(np.float32, copy=False)
    if np.any(a[:, 4:] < 0) or np.any(a[:, 4:] > 1):
        raise PhotoBaselineError("invalid YOLOX object/class probabilities")
    grid, stride = _grid()
    with np.errstate(over="ignore", invalid="ignore"):
        center = (a[:, :2] + grid) * stride
        size = np.exp(a[:, 2:4]) * stride
    if not np.isfinite(center).all() or not np.isfinite(size).all():
        raise PhotoBaselineError("YOLOX geometry overflow")
    ratio = min(SIZE / width, SIZE / height)
    rw = max(1, round(width * ratio))
    rh = max(1, round(height * ratio))
    sx, sy = width / rw, height / rh
    x1 = np.clip(center[:, 0] - size[:, 0] / 2, 0, rw) * sx
    x2 = np.clip(center[:, 0] + size[:, 0] / 2, 0, rw) * sx
    y1 = np.clip(center[:, 1] - size[:, 1] / 2, 0, rh) * sy
    y2 = np.clip(center[:, 1] + size[:, 1] / 2, 0, rh) * sy
    valid = (x2 > x1 + 1e-6) & (y2 > y1 + 1e-6)
    detections: list[Box] = []
    for name, coco_index in CATEGORIES.items():
        confidence = a[:, 4] * a[:, 5 + coco_index]
        candidates = np.flatnonzero(valid & (confidence >= MIN_SCORE))
        # Pre-NMS cap bounds the quadratic work on pathological outputs.
        order = sorted(
            candidates.tolist(), key=lambda i: (-float(confidence[i]), i)
        )[:MAX_PRE_NMS]
        retained: list[Box] = []
        for k in order:
            b = Box(
                name, (float(x1[k]), float(y1[k]), float(x2[k]), float(y2[k])),
                float(confidence[k]),
            )
            if all(iou(b, previous) <= NMS_IOU for previous in retained):
                retained.append(b)
            if len(retained) >= MAX_RESULTS:
                break
        detections.extend(retained)
    return tuple(sorted(
        detections, key=lambda b: (-b.confidence, b.category, b.xyxy)
    )[:MAX_RESULTS])


def _pair_unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for k, v in pairs:
        if k in result:
            raise PhotoBaselineError("duplicate COCO JSON key")
        result[k] = v
    return result


def _finite_number(x: object) -> bool:
    return type(x) in (int, float) and math.isfinite(x)


def select_coco_cases(blob: bytes, *, per_class: int = PER_CLASS,
                      negatives: int = NEGATIVES,
                      excluded_image_ids: frozenset[int] = frozenset()
                      ) -> tuple[CocoCase, ...]:
    """Small fixed selection from COCO 2017 VAL, never from training imagery.

    Select only image records declaring Flickr CC BY, check box geometry and
    exclude images with target 'iscrowd' or invalid target annotations.
    Split membership is defined by the pinned official annotation file, not
    by filename guesses. Image capture height remains UNKNOWN.
    """
    if (type(blob) is not bytes
            or not 128 <= len(blob) <= MAX_COCO_JSON_BYTES
            or type(per_class) is not int or not 1 <= per_class <= 4
            or type(negatives) is not int or not 1 <= negatives <= 4
            or type(excluded_image_ids) is not frozenset
            or len(excluded_image_ids) > MAX_SELECTED
            or any(type(i) is not int or i < 0
                   for i in excluded_image_ids)):
        raise PhotoBaselineError("invalid bounded COCO annotation input")
    try:
        data = json.loads(blob, object_pairs_hook=_pair_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              PhotoBaselineError("nonfinite COCO JSON")))
    except (UnicodeError, ValueError, RecursionError, TypeError) as e:
        raise PhotoBaselineError("invalid COCO JSON") from e
    if (type(data) is not dict
            or not all(type(data.get(k)) is list for k in (
                "images", "annotations", "licenses", "categories"
            ))):
        raise PhotoBaselineError("missing standard COCO lists")
    named = {}
    for record in data["categories"]:
        if type(record) is not dict or "id" not in record or "name" not in record:
            raise PhotoBaselineError("invalid COCO category schema")
        named[record["id"]] = record["name"]
    for target_name, target_id in COCO_IDS.items():
        if named.get(target_id) != target_name.replace("_", " "):
            raise PhotoBaselineError("COCO class order not expected")

    # Ensure this is the exact license grant type, rather than trusting the
    # numeric license id 4 alone (a modified annotation file could rename it).
    allowed_licences = {
        entry["id"] for entry in data["licenses"]
        if type(entry) is dict and entry.get("name") == PHOTO_LICENSE_NAME
        and entry.get("url") in {
            PHOTO_LICENSE_URL, PHOTO_LICENSE_URL.replace("http:", "https:")
        } and type(entry.get("id")) is int
    }
    if not allowed_licences:
        raise PhotoBaselineError("no reviewed per-image CC BY licenses")
    candidates = {}
    for image in data["images"]:
        if type(image) is not dict:
            raise PhotoBaselineError("invalid COCO image record")
        image_id = image.get("id")
        w, h = image.get("width"), image.get("height")
        if (type(image_id) is not int or type(w) is not int
                or type(h) is not int):
            raise PhotoBaselineError("untrusted image id/dimensions")
        if image.get("license") not in allowed_licences:
            continue
        filename = image.get("file_name")
        if (filename != f"{image_id:012d}.jpg"
                or not 32 <= w <= MAX_DIMENSION
                or not 32 <= h <= MAX_DIMENSION
                or image_id in candidates):
            continue
        candidates[image_id] = (filename, w, h)
    if not candidates:
        raise PhotoBaselineError("no eligible public COCO photos")
    classes_by_id = {v: k for k, v in COCO_IDS.items()}
    truth = defaultdict(list)
    invalid_ids = set()
    for ann in data["annotations"]:
        if type(ann) is not dict:
            raise PhotoBaselineError("invalid COCO annotation record")
        image_id, cat_id = ann.get("image_id"), ann.get("category_id")
        if image_id not in candidates or cat_id not in classes_by_id:
            continue
        if ann.get("iscrowd", 0) != 0:
            invalid_ids.add(image_id)
            continue
        values = ann.get("bbox")
        if (type(values) is not list or len(values) != 4
                or any(not _finite_number(v) for v in values)):
            invalid_ids.add(image_id)
            continue
        x, y, width, height = values
        _, w, h = candidates[image_id]
        if width <= 0 or height <= 0:
            invalid_ids.add(image_id)
            continue
        x1, y1 = max(0., float(x)), max(0., float(y))
        x2, y2 = min(float(w), float(x + width)), min(float(h), float(y + height))
        if x2 <= x1 or y2 <= y1:
            invalid_ids.add(image_id)
            continue
        truth[image_id].append(Box(
            classes_by_id[cat_id], (x1, y1, x2, y2)
        ))
    eligible = set(candidates) - invalid_ids - excluded_image_ids
    def random_order(ids):
        return sorted(ids, key=lambda i: (
            hashlib.sha256(f"{SEED}:{i}".encode()).digest(), i
        ))
    selected: list[int] = []
    used = set()
    for name in CATEGORIES:
        possible = random_order(
            i for i in eligible if any(b.category == name for b in truth[i])
            and i not in used
        )
        if len(possible) < per_class:
            raise PhotoBaselineError("insufficient licensed validation cases for " + name)
        chosen = possible[:per_class]
        selected.extend(chosen)
        used.update(chosen)
    unknown = random_order(i for i in eligible if not truth[i] and i not in used)
    if len(unknown) < negatives:
        raise PhotoBaselineError("insufficient licensed negatives")
    selected.extend(unknown[:negatives])
    if len(selected) > MAX_SELECTED or len(set(selected)) != len(selected):
        raise PhotoBaselineError("duplicate or oversized COCO sample")
    return tuple(CocoCase(
        i, candidates[i][0], candidates[i][1], candidates[i][2],
        tuple(truth[i]),
    ) for i in selected)


def evaluate_localization(
    results: tuple[tuple[CocoCase, tuple[Box, ...]], ...],
) -> dict:
    """One-to-one IoU50 assignment and 101-point interpolated AP50.

    An image may have multiple objects. Wrong classes remain FP+FN, not a
    forced correct image label. Every image is a COCO-val holdout image;
    category support=0 => AP=None, not a fabricated 100% score.
    """
    if (type(results) is not tuple or not 1 <= len(results) <= MAX_SELECTED):
        raise PhotoBaselineError("bounded nonempty image results required")
    if len({case.image_id for case, _ in results}) != len(results):
        raise PhotoBaselineError("duplicate image results")
    for case, predictions in results:
        if (not isinstance(case, CocoCase)
                or type(predictions) is not tuple
                or len(predictions) > MAX_RESULTS
                or any(not isinstance(p, Box)
                       or p.xyxy[0] < 0 or p.xyxy[1] < 0
                       or p.xyxy[2] > case.width
                       or p.xyxy[3] > case.height
                       for p in predictions)):
            raise PhotoBaselineError("invalid detector results or bbox coordinates")
    by_class = {}
    total_tp = total_fp = total_fn = 0
    for category in CATEGORIES:
        annotations = {
            case.image_id: tuple(
                b for b in case.ground_truth if b.category == category
            ) for case, _ in results
        }
        support = sum(len(v) for v in annotations.values())
        candidates = sorted(
            ((p.confidence, case.image_id, i, p)
             for case, predictions in results
             for i, p in enumerate(predictions) if p.category == category),
            key=lambda it: (-it[0], it[1], it[2]),
        )
        matched = defaultdict(set)
        tp_flags = []
        for _, ident, _, pred in candidates:
            choices = [
                (iou(pred, gt), k) for k, gt in enumerate(annotations[ident])
                if k not in matched[ident]
            ]
            overlap, gt_idx = max(choices, default=(0., -1))
            ok = overlap >= MATCH_IOU
            if ok:
                matched[ident].add(gt_idx)
            tp_flags.append(int(ok))
        tp = sum(tp_flags)
        fp = len(candidates) - tp
        fn = support - tp
        total_tp += tp
        total_fp += fp
        total_fn += fn
        ap50 = None
        if support:
            running_tp = 0
            precisions, recalls = [], []
            for i, is_tp in enumerate(tp_flags, 1):
                running_tp += is_tp
                precisions.append(running_tp / i)
                recalls.append(running_tp / support)
            ap50 = sum(
                max((p for p, r in zip(precisions, recalls)
                     if r >= recall_cutoff / 100), default=0.)
                for recall_cutoff in range(101)
            ) / 101
        by_class[category] = {
            "gt_instances": support, "detections": len(candidates),
            "tp_iou50": tp, "fp_iou50": fp, "fn_iou50": fn,
            "ap50_101point": round(ap50, 6) if ap50 is not None else None,
        }
    unknown_results = [
        len(predictions) for case, predictions in results
        if not case.ground_truth
    ]
    supported_ap = [
        v["ap50_101point"] for v in by_class.values()
        if v["ap50_101point"] is not None
    ]
    return {
        "images": len(results),
        "gt_instances": total_tp + total_fn,
        "proposed_boxes": total_tp + total_fp,
        "tp_iou50": total_tp, "fp_iou50": total_fp,
        "fn_iou50": total_fn,
        "precision_iou50": round(total_tp/(total_tp+total_fp), 6)
                           if total_tp+total_fp else None,
        "recall_iou50": round(total_tp/(total_tp+total_fn), 6)
                        if total_tp+total_fn else None,
        "macro_ap50_101point_present_classes": round(
            sum(supported_ap)/len(supported_ap), 6
        ) if supported_ap else None,
        "by_class": by_class,
        "images_with_no_gt_target": len(unknown_results),
        "empty_gt_images_without_false_alarm": sum(
            n == 0 for n in unknown_results
        ),
        "empty_gt_images_with_false_alarm": sum(
            n > 0 for n in unknown_results
        ),
    }


def _official_jpeg(case: CocoCase) -> bytes:
    """One bounded HTTPS fetch. Never archive, redirect via user input or log PII."""
    if not isinstance(case, CocoCase):
        raise TypeError("verified COCO case required")
    request = urllib.request.Request(
        IMAGE_HOST + case.filename,
        headers={"User-Agent": "Kwipi-Cat-A2-public-host-evaluation/1.0"},
    )
    with urllib.request.urlopen(request, timeout=25) as resp:
        if resp.status != 200:
            raise PhotoBaselineError("COCO image unavailable")
        raw = resp.read(MAX_IMAGE_BYTES + 1)
    if (not 100 <= len(raw) <= MAX_IMAGE_BYTES
            or not raw.startswith(b"\xff\xd8")
            or not raw.endswith(b"\xff\xd9")):
        raise PhotoBaselineError("COCO image invalid/oversized")
    from PIL import Image
    with Image.open(BytesIO(raw)) as image:
        # A rotated EXIF original would mismatch the COCO box coordinates;
        # fail, rather than secretly calculating wrong localization.
        if (image.format != "JPEG" or image.size != (case.width, case.height)
                or image.getexif().get(274, 1) != 1):
            raise PhotoBaselineError("COCO dimensions/orientation changed")
    return raw


def benchmark(*, model_path: Path, annotations_path: Path,
              cohort: str = "baseline") -> dict:
    """Real, non-low-height COCO bbox benchmark on 24 licensed val photos.

    File hashes are checked before reading or opening ONNX; never allow an
    unreviewed model/annotation or a train split into the evaluated cohort.
    """
    if type(cohort) is not str or cohort not in ("baseline", "disjoint_followup"):
        raise PhotoBaselineError("unapproved COCO evaluation cohort")
    validate_model_file(model_path)
    if (not isinstance(annotations_path, Path)
            or annotations_path.is_symlink()
            or not annotations_path.is_file()
            or not 128 <= annotations_path.stat().st_size <= MAX_COCO_JSON_BYTES):
        raise PhotoBaselineError("pinned COCO-val annotation file required")
    blob = annotations_path.read_bytes()
    annotation_digest = hashlib.sha256(blob).hexdigest()
    if annotation_digest != ANNOTATIONS_SHA256:
        raise PhotoBaselineError("COCO annotations SHA256 mismatch")
    original = select_coco_cases(blob) if cohort == "disjoint_followup" else ()
    excluded_ids = frozenset(case.image_id for case in original)
    cases = select_coco_cases(blob, excluded_image_ids=excluded_ids)
    if excluded_ids.intersection(case.image_id for case in cases):
        raise PhotoBaselineError("COCO followup leaked original images")
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise PhotoBaselineError("unreviewed YOLOX ONNX interface")
    times = []
    digests = []
    results = []
    t0 = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    for sample in cases:
        jpeg = _official_jpeg(sample)
        digests.append(hashlib.sha256(jpeg).hexdigest())
        image = prepare_image(jpeg, mode="original")
        ts = time.perf_counter()
        raw = session.run(None, {"images": image})[0]
        times.append((time.perf_counter() - ts) * 1000)
        results.append((sample, decode_boxes(
            raw, width=sample.width, height=sample.height
        )))
        del jpeg, image, raw
    after = resource.getrusage(resource.RUSAGE_SELF)
    scores = evaluate_localization(tuple(results))
    return {
        "scenario": "Cat-A2a fixed COCO2017 val bbox probe, NOT a 25cm camera test",
        "robot_name": "Kwipi",
        "model_url": MODEL_URL, "model_sha256": MODEL_SHA256,
        "model_license": MODEL_LICENSE,
        "annotation_url": ANNOTATIONS_URL,
        "annotation_sha256": annotation_digest,
        "annotation_license": "COCO Consortium CC BY 4.0",
        "source_photo_licence_declared": "Flickr CC BY 2.0",
        "photo_rights_independently_verified": False,
        "source_split": "COCO2017_val_not_train",
        "cohort_policy": f"{PER_CLASS} per class, {NEGATIVES} negatives, SHA-order fixed",
        "cohort": cohort,
        "excluded_original_images": len(excluded_ids),
        "original_cohort_overlap": len(excluded_ids.intersection(
            case.image_id for case in cases)),
        "image_ids_disjoint_not_scene_or_camera_independence": True,
        "no_gt_target_not_proven_empty_room": True,
        "independent_low_camera_annotations_available": False,
        "selected_image_ids": [case.image_id for case in cases],
        "image_sha256": digests,
        "categories": list(CATEGORIES),
        "coco_category_ids": COCO_IDS,
        "fixed_score_threshold": MIN_SCORE, "nms_iou": NMS_IOU,
        "iou_match": MATCH_IOU,
        "localization": scores,
        "camera_heights_measured": 0,
        "verified_25cm_camera_images": 0,
        "real_low_camera_performance": None,
        "full_coco_val_map": None,
        "image_labels_not_personal_identities": True,
        "model_pretraining_independence_unproven": True,
        "real_robot_or_rknn_validated": False,
        "host_cpu_onnx_ms_median": round(statistics.median(times), 3),
        "host_cpu_onnx_ms_p95": round(
            sorted(times)[min(len(times)-1, math.ceil(.95*len(times))-1)], 3
        ),
        "host_cpu_user_s_process": round(after.ru_utime-before.ru_utime, 3),
        "host_peak_rss_kib_process": after.ru_maxrss,
        "wall_s_includes_image_downloads": round(time.perf_counter()-t0, 3),
        "media_committed": False, "sqlite_writes": 0,
        "motor_commands": 0, "qwen_calls": 0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--annotations-path", type=Path, required=True)
    parser.add_argument("--approved-public-media", action="store_true")
    parser.add_argument("--cohort", choices=("baseline", "disjoint_followup"),
                        default="baseline")
    args = parser.parse_args(argv)
    if not args.approved_public_media:
        parser.error("public-media and source-license review opt-in required")
    print(json.dumps(
        benchmark(model_path=args.model_path, annotations_path=args.annotations_path,
                  cohort=args.cohort),
        allow_nan=False, sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
