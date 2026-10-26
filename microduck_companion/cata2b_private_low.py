"""Cat-A2b: PRIVATE low-camera category benchmark; reuse Cat-A2a YOLOX/IoU.

No media, model weights, personal identities, photographs or measurements are
bundled. The operator must capture and label INDEPENDENT real scenes locally.
The strict JSON manifest and its media stay outside Git (see .gitignore).
A ruler photograph and its SHA do not independently verify the camera height;
the report uses 'operator_declared', never 'robot_validated'.

The evaluator loads the approved Cat-A SHA-pinned ONNX model and delegates
box decode and matching to cata2_bbox_eval. It DOES NOT train, capture,
move a robot, make Qwen calls, or write a second SQLite database.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import argparse
import json
import math
from pathlib import Path
import re
import resource
import statistics
import time

from .cata2_bbox_eval import (
    Box, CocoCase, decode_boxes, evaluate_localization,
)
from .cata_yolox_categories import (
    CATEGORIES, MAX_IMAGE_BYTES, MODEL_SHA256, MIN_SCORE, SIZE,
    prepare_image, validate_model_file,
)
from .visual_photo_mobilenet_demo import PhotoBaselineError

VERSION = 1
SOURCE = "operator_private_capture"
MAX_MANIFEST_BYTES = 256 * 1024
MAX_SAMPLES = 128
MAX_TEST_SAMPLES = 25  # evaluate_localization is deliberately limited to 25.
MAX_SESSIONS = 48
MAX_BOXES = 40
MIN_HEIGHT_MM = 100
MAX_HEIGHT_MM = 300
MAX_EVIDENCE_BYTES = 2_500_000
MAX_DIMENSION = 4096
ID_RE = re.compile(r"[sg]-[0-9a-f]{16}\Z", re.ASCII)
SAMPLE_RE = re.compile(r"s-[0-9a-f]{16}\Z", re.ASCII)
GROUP_RE = re.compile(r"g-[0-9a-f]{16}\Z", re.ASCII)
EVIDENCE_RE = re.compile(r"e-[0-9a-f]{16}\.jpg\Z", re.ASCII)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
SPLITS = frozenset({"train", "validation", "test"})
VISIBILITY = frozenset({"full", "partial"})
SESSION_FIELDS = frozenset({
    "session_id", "site_group_id", "camera_height_mm",
    "ruler_evidence_file", "ruler_evidence_sha256",
    "measurement_method",
})
SAMPLE_FIELDS = frozenset({
    "sample_id", "session_id", "scene_group_id", "split", "image_sha256",
    "image_width", "image_height", "boxes", "all_targets_reviewed",
    "privacy_and_consent_reviewed",
})
BOX_FIELDS = frozenset({"category", "xyxy", "visibility"})


@dataclass(frozen=True)
class LowSession:
    session_id: str
    site_group_id: str
    camera_height_mm: int
    ruler_evidence_file: str
    ruler_evidence_sha256: str


@dataclass(frozen=True)
class LowSample:
    sample_id: str
    session_id: str
    scene_group_id: str
    split: str
    width: int
    height: int
    ground_truth: tuple[Box, ...]
    visibility: tuple[str, ...]
    image_sha256: str


@dataclass(frozen=True)
class LowDataset:
    root: Path
    sessions: tuple[LowSession, ...]
    samples: tuple[LowSample, ...]
    manifest_sha256: str

    def test(self) -> tuple[LowSample, ...]:
        return tuple(s for s in self.samples if s.split == "test")


def _reject_duplicate_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise PhotoBaselineError("duplicate JSON key")
        result[k] = v
    return result


def _reject_nonfinite(_):
    raise PhotoBaselineError("nonfinite JSON is forbidden")


def _bounded_data(path: Path, limit: int) -> bytes:
    if (path.is_symlink() or not path.is_file()
            or not 1 <= path.stat().st_size <= limit):
        raise PhotoBaselineError("missing, linked or oversized private file")
    with path.open("rb") as fp:
        raw = fp.read(limit + 1)
    if not 1 <= len(raw) <= limit:
        raise PhotoBaselineError("oversized private input")
    return raw


def _hex_string(value: object, pattern) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        raise PhotoBaselineError("invalid opaque id, filename or SHA")
    return value


def _integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise PhotoBaselineError("invalid measurement, count or image geometry")
    return value


def _private_root_guard(root: Path):
    """A dataset within the checkout MUST be in its existing ignored dirs."""
    if root.is_symlink() or not root.is_dir():
        raise PhotoBaselineError("private local directory required")
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            rel = root.relative_to(ancestor).parts
            if not (rel[:1] == (".local_visual_data",)
                    or rel[:2] in (("datasets", "private"),
                                  ("datasets", "local"))):
                raise PhotoBaselineError(
                    "private media inside checkout must be Git-ignored")
            break


def _jpeg_dimensions(blob: bytes) -> tuple[int, int]:
    """Require Pillow to verify dimensions; no guessing from declared metadata."""
    try:
        from PIL import Image
        with Image.open(BytesIO(blob)) as im:
            if im.format != "JPEG" or im.getexif().get(274, 1) != 1:
                raise PhotoBaselineError("not a nonrotated JPEG")
            if min(im.size) < 32 or max(im.size) > MAX_DIMENSION:
                raise PhotoBaselineError("out-of-bounds actual JPEG dimensions")
            # Decode here to detect truncated media before any ONNX request.
            im.load()
            return im.size
    except (OSError, ValueError) as e:
        if isinstance(e, PhotoBaselineError):
            raise
        raise PhotoBaselineError("unreadable or corrupt local JPEG") from e


def load_private_low_dataset(manifest_path: Path) -> LowDataset:
    """Strictly read one *local* manifest and recheck all private media SHA.

    Camera optical-center heights and measurement photographs are DECLARED,
    not calibrated/independently witnessed. Never print private filenames or
    use image EXIF, images, locations, names or identifiers as robot facts.
    """
    if not isinstance(manifest_path, Path) or manifest_path.is_symlink():
        raise PhotoBaselineError("local manifest path required")
    root = manifest_path.parent
    _private_root_guard(root)
    raw = _bounded_data(manifest_path, MAX_MANIFEST_BYTES)
    try:
        data = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs,
                          parse_constant=_reject_nonfinite)
    except (UnicodeError, ValueError, RecursionError, TypeError) as e:
        raise PhotoBaselineError("invalid private metadata JSON") from e
    if (type(data) is not dict
            or set(data) != {"schema_version", "source", "sessions", "samples"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != VERSION
            or data["source"] != SOURCE
            or type(data["sessions"]) is not list
            or not 1 <= len(data["sessions"]) <= MAX_SESSIONS
            or type(data["samples"]) is not list
            or not 4 <= len(data["samples"]) <= MAX_SAMPLES):
        raise PhotoBaselineError("invalid low-camera manifest schema or budget")

    if ((root / "images").is_symlink()
            or (root / "evidence").is_symlink()
            or not (root / "images").is_dir()
            or not (root / "evidence").is_dir()):
        raise PhotoBaselineError("private media directories cannot be linked")
    sessions = {}
    for v in data["sessions"]:
        if type(v) is not dict or set(v) != SESSION_FIELDS:
            raise PhotoBaselineError("unknown/private fields in session")
        sid = _hex_string(v["session_id"], GROUP_RE)
        place = _hex_string(v["site_group_id"], GROUP_RE)
        height = _integer(v["camera_height_mm"], MIN_HEIGHT_MM, MAX_HEIGHT_MM)
        evidence = _hex_string(v["ruler_evidence_file"], EVIDENCE_RE)
        digest = _hex_string(v["ruler_evidence_sha256"], SHA_RE)
        if v["measurement_method"] != "ruler_at_optical_center":
            raise PhotoBaselineError("camera lens height measurement required")
        if sid in sessions:
            raise PhotoBaselineError("duplicate camera session")
        evidence_blob = _bounded_data(root / "evidence" / evidence,
                                      MAX_EVIDENCE_BYTES)
        if sha256(evidence_blob).hexdigest() != digest:
            raise PhotoBaselineError("local measurement evidence hash mismatch")
        _jpeg_dimensions(evidence_blob)
        sessions[sid] = LowSession(sid, place, height, evidence, digest)

    photos = set()
    sample_ids = set()
    sample_groups = {}
    site_groups = {}
    sessions_splits = {}
    split_counts = {split: 0 for split in SPLITS}
    samples = []
    for row in data["samples"]:
        if type(row) is not dict or set(row) != SAMPLE_FIELDS:
            raise PhotoBaselineError("unknown/private fields in sample")
        sid = _hex_string(row["sample_id"], SAMPLE_RE)
        session_id = _hex_string(row["session_id"], GROUP_RE)
        scene_id = _hex_string(row["scene_group_id"], GROUP_RE)
        split = row["split"]
        digest = _hex_string(row["image_sha256"], SHA_RE)
        w = _integer(row["image_width"], 32, MAX_DIMENSION)
        h = _integer(row["image_height"], 32, MAX_DIMENSION)
        if (sid in sample_ids or session_id not in sessions
                or type(split) is not str or split not in SPLITS
                or type(row["all_targets_reviewed"]) is not bool
                or not row["all_targets_reviewed"]
                or type(row["privacy_and_consent_reviewed"]) is not bool
                or not row["privacy_and_consent_reviewed"]):
            raise PhotoBaselineError("unreviewed, duplicate or invalid sample")
        sample_ids.add(sid)
        for lookup, group in (
            (sample_groups, scene_id),
            (site_groups, sessions[session_id].site_group_id),
            (sessions_splits, session_id),
        ):
            if group in lookup and lookup[group] != split:
                raise PhotoBaselineError("scene, site or session split leakage")
            lookup[group] = split
        boxes_raw = row["boxes"]
        if type(boxes_raw) is not list or len(boxes_raw) > MAX_BOXES:
            raise PhotoBaselineError("invalid box annotation list")
        boxes, visible = [], []
        for obj in boxes_raw:
            if type(obj) is not dict or set(obj) != BOX_FIELDS:
                raise PhotoBaselineError("unreviewed bbox annotation")
            cat, coords, vis = obj["category"], obj["xyxy"], obj["visibility"]
            if (type(cat) is not str or cat not in CATEGORIES
                    or type(vis) is not str or vis not in VISIBILITY
                    or type(coords) is not list or len(coords) != 4
                    or any(type(x) not in (int, float) or not math.isfinite(x)
                           for x in coords)):
                raise PhotoBaselineError("unsupported class or corrupt bbox")
            x0, y0, x1, y1 = map(float, coords)
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                raise PhotoBaselineError("bbox outside validated JPEG")
            boxes.append(Box(cat, (x0, y0, x1, y1)))
            visible.append(vis)
        path = root / "images" / (sid + ".jpg")
        blob = _bounded_data(path, MAX_IMAGE_BYTES)
        if sha256(blob).hexdigest() != digest or digest in photos:
            raise PhotoBaselineError("image checksum mismatch or duplicate")
        photos.add(digest)
        if _jpeg_dimensions(blob) != (w, h):
            raise PhotoBaselineError("manifest/image geometry mismatch")
        split_counts[split] += 1
        samples.append(LowSample(
            sid, session_id, scene_id, split, w, h,
            tuple(boxes), tuple(visible), digest,
        ))

    if (any(split_counts[s] < 1 for s in ("train", "validation"))
            or split_counts["test"] < 2
            or split_counts["test"] > MAX_TEST_SAMPLES
            or not any(s.ground_truth for s in samples if s.split == "test")
            or not any(not s.ground_truth for s in samples if s.split == "test")):
        raise PhotoBaselineError("incomplete test: target, unknown and split required")
    return LowDataset(root, tuple(sessions.values()), tuple(samples),
                      sha256(raw).hexdigest())


def summarize_private_dataset(data: LowDataset) -> dict:
    if not isinstance(data, LowDataset):
        raise TypeError("validated private dataset required")
    counts = {
        k: sum(s.split == k for s in data.samples)
        for k in ("train", "validation", "test")
    }
    test = data.test()
    return {
        "status": "validated_local_file_integrity_not_vision_accuracy",
        "manifest_sha256": data.manifest_sha256,
        "test_image_count": len(test),
        "declared_low_optical_center_range_mm": [
            min(s.camera_height_mm for s in data.sessions),
            max(s.camera_height_mm for s in data.sessions),
        ],
        "operator_height_declarations_checked_against_local_ruler_photo": False,
        "ruler_evidence_file_sha256_checked": True,
        "independent_height_validation": False,
        "robot_camera_viewpoint_confirmed": False,
        "all_local_jpegs_hashes_and_dimensions_checked": True,
        "dataset_splits": counts,
        "test_partial_objects": sum(
            v == "partial" for s in test for v in s.visibility
        ),
        "test_full_objects": sum(
            v == "full" for s in test for v in s.visibility
        ),
        "test_negative_images": sum(not s.ground_truth for s in test),
        "source": SOURCE,
        "personal_media_published": False,
        "model_evaluated": False,
        "robot_or_rknn_validated": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
        "qwen_calls": 0,
    }


def benchmark_private_low_dataset(data: LowDataset, *, model_path: Path) -> dict:
    """Infer only TEST, no model fitting/threshold tuning and no media archiving.

    The simple image-level partial/full breakdown is diagnostic only; mixed
    partial/full images count in 'has_partial' and not 'full_only'.
    """
    if not isinstance(data, LowDataset):
        raise TypeError("validated low-camera manifest required")
    validate_model_file(model_path)
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
        raise PhotoBaselineError("unexpected Cat-A YOLOX ONNX signature")
    times, results, groups = [], [], {"has_partial": [], "full_only": [], "no_target": []}
    start = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    for index, sample in enumerate(data.test(), 1):
        # Read again in case private input changed between validation and run.
        blob = _bounded_data(
            data.root / "images" / (sample.sample_id + ".jpg"),
            MAX_IMAGE_BYTES,
        )
        if (sha256(blob).hexdigest() != sample.image_sha256
                or _jpeg_dimensions(blob) != (sample.width, sample.height)):
            raise PhotoBaselineError("private photo changed after manifest verification")
        tensor = prepare_image(blob, mode="original")
        tic = time.perf_counter()
        output = session.run(None, {"images": tensor})[0]
        times.append((time.perf_counter() - tic)*1000)
        detections = decode_boxes(
            output, width=sample.width, height=sample.height,
        )
        # Internal ephemeral integer IDs are unrelated to sample IDs, images,
        # track IDs or physical objects. Names are never returned or logged.
        case = CocoCase(index, f"{index:012d}.jpg", sample.width,
                        sample.height, sample.ground_truth)
        result = (case, detections)
        results.append(result)
        subgroup = ("no_target" if not sample.ground_truth
                    else "has_partial" if "partial" in sample.visibility
                    else "full_only")
        groups[subgroup].append(result)
        del blob, tensor, output
    after = resource.getrusage(resource.RUSAGE_SELF)
    report = summarize_private_dataset(data)
    report.update({
        "status": "host_only_unindependently_attested_low_camera_detection",
        "model_sha256": MODEL_SHA256,
        "threshold_kept_from_cata": MIN_SCORE,
        "test_metrics": evaluate_localization(tuple(results)),
        "subgroups_image_level_not_instance_level": {
            key: evaluate_localization(tuple(items)) if items else None
            for key, items in groups.items()
        },
        "model_evaluated": True,
        "independent_camera_height_verified": False,
        "host_cpu_inference_ms_median": round(statistics.median(times), 3),
        "host_cpu_inference_ms_p95": round(
            sorted(times)[min(len(times)-1, math.ceil(.95*len(times))-1)],
            3,
        ),
        "host_process_peak_rss_kib": after.ru_maxrss,
        "host_process_cpu_user_s": round(after.ru_utime-before.ru_utime, 3),
        "host_wall_s": round(time.perf_counter()-start, 3),
    })
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--approved-private-local-media", action="store_true")
    args = parser.parse_args(argv)
    if not args.approved_private_local_media:
        parser.error("explicit private-local-media and consent approval required")
    if not args.validate_only and args.model_path is None:
        parser.error("--model-path required for real local inference")
    data = load_private_low_dataset(args.manifest)
    result = (summarize_private_dataset(data) if args.validate_only
              else benchmark_private_low_dataset(data, model_path=args.model_path))
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
