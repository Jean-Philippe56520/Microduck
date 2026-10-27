"""Cat-A2b: tiny PUBLIC low-angle probe, never a supervised evaluation.

Three PNG source frames from the original UMD robot-ground project are
Git-blob-pinned at a source commit. Its README states an APPROXIMATE 12 cm
camera height for the corpus, not a verified height for each preview frame.
The files have NO annotations for Kwipi's five target categories; therefore
YOLOX boxes are PROPOSALS, not accuracy, false positives or true positives.

This research-only host probe retrieves bytes into RAM, validates the Git blob
SHA-1, transcodes PNG to JPEG in RAM for the existing Cat-A preprocessing,
and reuses Cat-A2a decoding. No photos, model weights, identities, SQLite,
robots, Qwen or private memories are persisted or transferred. Repository MIT
licensing does not independently establish photographic/subject rights.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
from io import BytesIO
import argparse
import json
import math
import re
import resource
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

from .cata2_bbox_eval import decode_boxes
from .cata_yolox_categories import (
    CATEGORIES, MAX_IMAGE_BYTES, MODEL_SHA256, MIN_SCORE, SIZE,
    prepare_image, validate_model_file,
)
from .visual_photo_mobilenet_demo import PhotoBaselineError

SOURCE_REPO = "adarshmalapaka/ground-plane-segmentation"
SOURCE_COMMIT = "473d261362901c944a65d630e3892abdeee2353b"
SOURCE_README = (
    "https://github.com/" + SOURCE_REPO + "/blob/" + SOURCE_COMMIT + "/README.md"
)
SOURCE_BASE = (
    "https://raw.githubusercontent.com/" + SOURCE_REPO + "/" + SOURCE_COMMIT
    + "/Code/training/data/orig_imgs/"
)
MAX_PNG_BYTES = 1_250_000
EXPECTED_GEOMETRY = (1280, 720)
NAME_RE = re.compile(r"A[0-9]{5}\.png\Z", re.ASCII)


@dataclass(frozen=True)
class PublicPreview:
    filename: str
    git_blob_sha1: str


# Identical byte hashes in the original and two forks; this list uses ONLY
# the ORIGINAL authors' repo, full immutable source commit and blob digest.
SAMPLES = (
    PublicPreview("A00001.png", "8f9b11d518b7ad24b34555853d6c521a8582fe47"),
    PublicPreview("A00002.png", "aee05238a8e8f6766bdcd342ba206ff6240c2b57"),
    PublicPreview("A00019.png", "59d9ef204c36a5ae0ae0f9355c0b696f53289518"),
)


def _load_verified_public_png(sample: PublicPreview) -> tuple[bytes, str]:
    """Read a fixed public research sample, never arbitrary operator URLs.

    A Git blob SHA checks exact source bytes; the additional SHA-256 is
    recorded as a digest of digests. No images are written to disk.
    """
    if (not isinstance(sample, PublicPreview) or sample not in SAMPLES
            or not NAME_RE.fullmatch(sample.filename)):
        raise PhotoBaselineError("unsupported public research sample")
    url = SOURCE_BASE + sample.filename
    request = urllib.request.Request(
        url, headers={"User-Agent": "Kwipi-research-low-camera/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise PhotoBaselineError("public research sample unavailable")
            raw = response.read(MAX_PNG_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise PhotoBaselineError("public research sample unavailable") from exc
    if (not 100 <= len(raw) <= MAX_PNG_BYTES
            or not raw.startswith(b"\x89PNG\r\n\x1a\n")
            or sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
                    ).hexdigest() != sample.git_blob_sha1):
        raise PhotoBaselineError("public research image bytes not source-pinned")
    source_sha256 = sha256(raw).hexdigest()
    from PIL import Image
    try:
        with Image.open(BytesIO(raw)) as image:
            if (image.format != "PNG" or image.size != EXPECTED_GEOMETRY
                    or image.getexif().get(274, 1) != 1):
                raise PhotoBaselineError("unexpected source PNG geometry/rotation")
            image.load()
            converted = BytesIO()
            # Existing Cat-A preprocessor accepts JPEG, not PNG. Re-encode
            # lossily IN MEMORY and explicitly disclose that limitation.
            image.convert("RGB").save(
                converted, format="JPEG", quality=95, subsampling=0,
            )
            jpeg = converted.getvalue()
    except (OSError, ValueError) as exc:
        if isinstance(exc, PhotoBaselineError):
            raise
        raise PhotoBaselineError("unreadable public source PNG") from exc
    if not 100 <= len(jpeg) <= MAX_IMAGE_BYTES:
        raise PhotoBaselineError("public PNG JPEG conversion exceeded budget")
    return jpeg, source_sha256


def probe_public_low_angle(*, model_path: Path) -> dict:
    """Measure unlabeled detector proposals on HOST CPU, never recognition TP.

    No train/validation/test claims: three published preview frames can be
    correlated and do not have category ground truth. This is not Cat-A2b's
    validated PRIVATE capture path, nor a benchmark of five categories.
    """
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
        raise PhotoBaselineError("unexpected approved Cat-A YOLOX ONNX signature")
    t0 = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    times = []
    proposals = {category: 0 for category in CATEGORIES}
    input_digests = []
    for sample in SAMPLES:
        jpeg, input_digest = _load_verified_public_png(sample)
        input_digests.append(input_digest)
        tensor = prepare_image(jpeg, mode="original")
        begin = time.perf_counter()
        raw_output = session.run(None, {"images": tensor})[0]
        times.append((time.perf_counter() - begin) * 1000)
        boxes = decode_boxes(
            raw_output, width=EXPECTED_GEOMETRY[0],
            height=EXPECTED_GEOMETRY[1],
        )
        for box in boxes:
            if box.category not in proposals:
                raise PhotoBaselineError("non-Cat-A output category")
            proposals[box.category] += 1
        del jpeg, tensor, raw_output, boxes
    after = resource.getrusage(resource.RUSAGE_SELF)
    if len(input_digests) != len(SAMPLES):
        raise PhotoBaselineError("incomplete fixed public research source")
    return {
        "status": "unlabeled_host_public_low_angle_proposals_only",
        "source_repository": SOURCE_REPO,
        "source_commit": SOURCE_COMMIT,
        "source_readme": SOURCE_README,
        "camera_height_author_reported_approx_mm": 120,
        "individual_frame_camera_height_independently_verified": False,
        "robot_camera_geometry_confirmed": False,
        "public_preview_frames": len(input_digests),
        "independent_source_scenes_verified": False,
        "public_source_rights_status": "repo_MIT_media_and_subject_rights_not_independently_verified",
        "input_sha256_digest_of_digests": sha256(
            "".join(sorted(input_digests)).encode("ascii")
        ).hexdigest(),
        "reencoded_png_to_jpeg_in_memory_quality": 95,
        "model_sha256": MODEL_SHA256,
        "model_threshold_fixed_from_cata": MIN_SCORE,
        "proposed_boxes_by_category_not_ground_truth": proposals,
        "ground_truth_annotations_for_five_categories": 0,
        "localization_metrics_tp_fp_fn_ap50": None,
        "qualitative_predictions_independently_checked": False,
        "model_evaluated_on_public_preview_frames": True,
        "real_robust_low_camera_category_accuracy_known": False,
        "host_cpu_inference_median_ms": round(statistics.median(times), 3),
        "host_cpu_inference_p95_ms": round(
            sorted(times)[min(len(times)-1, math.ceil(.95*len(times))-1)], 3),
        "host_process_peak_rss_kib": after.ru_maxrss,
        "host_process_cpu_user_s": round(after.ru_utime - before.ru_utime, 3),
        "host_wall_s_including_download": round(time.perf_counter() - t0, 3),
        "media_published_or_saved": False,
        "robot_or_rknn_validated": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
        "qwen_calls": 0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--approved-public-research-media", action="store_true")
    args = parser.parse_args(argv)
    if not args.approved_public_research_media:
        parser.error("explicit public research-media approval required")
    print(json.dumps(
        probe_public_low_angle(model_path=args.model_path),
        allow_nan=False, sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
