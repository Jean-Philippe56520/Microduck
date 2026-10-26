"""R2-B: independently captured COIL-20 views, with optional local WAV takes.

A HOST-ONLY, read-only evaluation. Reuses M1-A/M1-B fingerprints and M1-B2
ONNX descriptors/scoring; writes NO SQLite (M1-B only accepts SYNTHETIC
fixture source claims). COIL-20 views are real turntable captures from a
single session, NOT home conditions or verified pet/child identities.
Audio source labels in private local manifests are claims, NOT proof.
No camera, OEM service, motors, LLM, persistent images or audio exports.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import gzip
from io import BytesIO, TextIOWrapper
import hashlib
import json
import math
from pathlib import Path
import re
import resource
import statistics
import time
import wave
import zipfile

from .compact_multimodal_memory import image_fingerprint
from .m1b2_host_embeddings import (
    _audio_baseline, _audio_learned, _image_baseline,
    _image_learned, _latency, _score, conservative_threshold,
)
from .visual_dataset import _parse_json
from .visual_photo_mobilenet_demo import check_model_file
from .m1b2_host_embeddings import check_audio_model

ABO_CC_BY_SOURCE = "https://amazon-berkeley-objects.s3.amazonaws.com/index.html"
ABO_METADATA = ("https://amazon-berkeley-objects.s3.us-east-1."
                "amazonaws.com/spins/metadata/spins.csv.gz")
ABO_HOST = "amazon-berkeley-objects.s3.us-east-1.amazonaws.com"
ABO_SOURCE_COUNT = 12
ABO_POSES = (0, 9, 18, 36, 45, 54)
ABO_REFS = (0, 36)
ABO_QUERIES = (9, 18, 45, 54)
ABO_MAX_JPEG_BYTES = 3_000_000

COIL20_SOURCE = ("https://www.cs.columbia.edu/CAVE/databases/"
                 "SLAM_coil-20_coil-100/coil-20/coil-20-proc.zip")
# Columbia's official page does not publish a verified archive SHA-256.
# Require an externally reviewed, explicitly supplied expectation. A digest
# supplied by the user is tamper detection, NOT license/provenance validation.
COIL20_LICENSE_SCOPE = "noncommercial_research_only"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_PNG_BYTES = 90_000
REFERENCE_POSES = (0, 36)
QUERY_POSES = (9, 18, 27, 45, 54, 63)
VAL_IDS = tuple(range(1, 9))
VAL_UNKNOWN_IDS = tuple(range(9, 11))
TEST_KNOWN_IDS = tuple(range(11, 17))
TEST_UNKNOWN_IDS = tuple(range(17, 21))
ALL_POSES = REFERENCE_POSES + QUERY_POSES
MAX_MANIFEST_BYTES = 64 * 1024
MAX_WAV_BYTES = 48_000
MAX_LOCAL_PNG_BYTES = 1_000_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
FILE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,45}\.(?:wav|png)\Z", re.ASCII)
SOURCE_RE = re.compile(r"s-[a-z0-9]{3,24}\Z", re.ASCII)
TAKE_RE = re.compile(r"t-[a-z0-9]{3,24}\Z", re.ASCII)
SPLITS = ("validation", "validation_unknown", "test_known", "test_unknown")


class R2BEvidenceError(ValueError):
    """Unsupported rights, provenance, or potentially leaky test data."""


def _digest(path: Path, *, max_bytes: int) -> str:
    if (not isinstance(path, Path) or not path.is_file()
            or not 1 <= path.stat().st_size <= max_bytes):
        raise R2BEvidenceError("missing or unbounded local research file")
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _coil_name(obj: int, pose: int) -> str:
    if (type(obj) is not int or type(pose) is not int
            or obj not in range(1, 21) or pose not in range(72)):
        raise R2BEvidenceError("invalid COIL20 source/pose")
    return f"coil-20-proc/obj{obj}__{pose}.png"


def _image_samples(archive: Path, *, expected_sha256: str, model=None):
    if type(expected_sha256) is not str or not HEX64.fullmatch(expected_sha256):
        raise R2BEvidenceError(
            "a reviewed external COIL20 SHA256 expectation is required")
    if _digest(archive, max_bytes=MAX_ARCHIVE_BYTES) != expected_sha256:
        raise R2BEvidenceError("COIL20 archive digest mismatch")
    # Validate rights and archive integrity before requiring optional Pillow.
    from PIL import Image
    np = None
    if model is not None:
        import numpy as np
    collected = {}
    timings: list[float] = []
    file_hashes: set[str] = set()
    names = {_coil_name(obj, pose)
             for obj in range(1, 21) for pose in ALL_POSES}
    with zipfile.ZipFile(archive) as zf:
        entries = [info for info in zf.infolist()
                   if info.filename in names]
        if len(entries) != len(names) or len({i.filename for i in entries}) != len(names):
            raise R2BEvidenceError("missing/duplicate official multi-view image")
        for entry in entries:
            if (entry.file_size < 100 or entry.file_size > MAX_PNG_BYTES
                    or entry.compress_size > MAX_PNG_BYTES
                    or entry.is_dir()):
                raise R2BEvidenceError("oversized/corrupt COIL20 member")
        for obj in range(1, 21):
            for pose in ALL_POSES:
                with zf.open(_coil_name(obj, pose)) as reader:
                    png = reader.read(MAX_PNG_BYTES + 1)
                if (len(png) > MAX_PNG_BYTES
                        or not png.startswith(b"\x89PNG\r\n\x1a\n")):
                    raise R2BEvidenceError("invalid research PNG")
                digest = hashlib.sha256(png).hexdigest()
                if digest in file_hashes:
                    raise R2BEvidenceError("duplicate exact image across views")
                file_hashes.add(digest)
                with Image.open(BytesIO(png)) as src:
                    if src.format != "PNG" or src.size != (128, 128):
                        raise R2BEvidenceError("unexpected COIL20 image shape")
                    src.load()
                    image = src.convert("RGB").resize(
                        (224, 224), Image.Resampling.BILINEAR)
                baseline = image_fingerprint(_image_baseline(image))
                record = {"legacy": baseline}
                if model is not None:
                    record["learned"] = _image_learned(
                        model, image, np, timings)
                collected[(obj, pose)] = record
    return collected, timings


def _ref_query(samples: dict, known_ids, unknown_ids=()):
    refs = {source: tuple(samples[(source, p)]
                           for p in REFERENCE_POSES)
            for source in known_ids}
    queries = tuple((source, pose, samples[(source, pose)])
                    for source in (*known_ids, *unknown_ids)
                    for pose in QUERY_POSES)
    return refs, queries


def _score_groups(refs: dict, candidate: dict, *, kind: str):
    return sorted(((max(_score(candidate[kind], ref[kind], kind)
                        for ref in exemplars), source)
                   for source, exemplars in refs.items()),
                  key=lambda item: (-item[0], item[1]))


def _negative_scores(refs, queries, *, kind):
    scores: list[float] = []
    for real_source, _, candidate in queries:
        matches = _score_groups(refs, candidate, kind=kind)
        scores.extend(float(score) for score, source in matches
                      if source != real_source)
    return tuple(scores)


def _predict(refs, sample, *, kind, threshold):
    if type(threshold) is not float or not math.isfinite(threshold):
        raise R2BEvidenceError("threshold must be finite float")
    matches = _score_groups(refs, sample, kind=kind)
    if not matches:
        return None, "unknown"
    best, source = matches[0]
    if not best > threshold:
        return None, "unknown"
    # Reuse the AMBIGUITY_GAP logic from M1-A/M1-B; a near tie abstains.
    from .compact_multimodal_memory import AMBIGUITY_GAP
    if len(matches) > 1 and best - matches[1][0] < AMBIGUITY_GAP:
        return None, "ambiguous"
    return source, "matched"


def _metrics(refs, queries, *, kind, cutoff) -> dict:
    known = wrong = unknown = unknown_rejected = 0
    accepted_known = right = false_known = ambiguous = 0
    per_pose: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for actual, pose, candidate in queries:
        is_known = actual in refs
        predicted, status = _predict(
            refs, candidate, kind=kind, threshold=cutoff)
        if status == "ambiguous":
            ambiguous += 1
        if is_known:
            known += 1
            per_pose[pose][0] += 1
            if predicted is not None:
                accepted_known += 1
            if predicted == actual:
                right += 1
                per_pose[pose][1] += 1
            elif predicted is not None:
                wrong += 1
        else:
            unknown += 1
            if predicted is None:
                unknown_rejected += 1
            else:
                false_known += 1
    if not known or not unknown:
        raise R2BEvidenceError("known and unknown independent captures required")
    return {
        "known_queries": known, "correct_known": right,
        "known_recall": right / known,
        "accepted_known": accepted_known,
        "cross_object_misidentifications": wrong,
        "unknown_queries": unknown, "unknown_rejected": unknown_rejected,
        "unknown_recall": unknown_rejected / unknown,
        "false_known_on_unknown": false_known,
        "ambiguous_abstentions": ambiguous,
        "known_recall_by_pose_index": {
            str(p): {"correct": a[1], "total": a[0]}
            for p, a in sorted(per_pose.items())
        },
    }


def evaluate_captures(samples: dict, *, kinds=("legacy",)) -> dict:
    """Freeze thresholds on VAL objects, evaluate only distinct TEST objects.

    No 'best of test' selection and no identity label model training.
    """
    if (type(samples) is not dict or type(kinds) is not tuple
            or len(set(kinds)) != len(kinds)
            or any(type(k) is not str or k not in ("legacy", "learned")
                   for k in kinds)
            or not kinds):
        raise R2BEvidenceError("unsupported descriptor study")
    required = {(obj, pose) for obj in range(1, 21) for pose in ALL_POSES}
    if set(samples) != required:
        raise R2BEvidenceError("exact COIL20 roster required; no partial scores")
    val_ref, val_queries = _ref_query(samples, VAL_IDS, VAL_UNKNOWN_IDS)
    test_ref, test_queries = _ref_query(
        samples, TEST_KNOWN_IDS, TEST_UNKNOWN_IDS)
    results = {}
    for kind in kinds:
        for record in samples.values():
            if kind not in record:
                raise R2BEvidenceError("incomplete descriptor set")
        negative = _negative_scores(val_ref, val_queries, kind=kind)
        threshold = conservative_threshold(negative)
        results[kind] = {
            "threshold_frozen_on_validation_only": threshold,
            "validation_negative_pairs": len(negative),
            "validation": _metrics(
                val_ref, val_queries, kind=kind, cutoff=threshold),
            "test": _metrics(test_ref, test_queries,
                             kind=kind, cutoff=threshold),
        }
    return {
        "method": "COIL20_independent_turntable_frames_open_set",
        "val_enrolled_sources": len(VAL_IDS),
        "val_unknown_sources": len(VAL_UNKNOWN_IDS),
        "test_enrolled_sources": len(TEST_KNOWN_IDS),
        "test_unseen_sources": len(TEST_UNKNOWN_IDS),
        "reference_pose_indices": list(REFERENCE_POSES),
        "query_pose_indices": list(QUERY_POSES),
        "same_physical_object_views_as_labeled_by_corpus": True,
        "independent_sessions_or_domestic_lighting": False,
        "manual_license_review_required_for_any_redistribution": True,
        "image_or_audio_saved_to_sqlite": False,
        "motor_commands": 0, "pc_requests": 0,
        "hardware_validated": False,
        "candidates": results,
    }


def _capture_manifest(raw: bytes, *, media_ext: str):
    if media_ext not in ("wav", "png"):
        raise R2BEvidenceError("unsupported licensed-media format")
    if type(raw) is not bytes or len(raw) > MAX_MANIFEST_BYTES:
        raise R2BEvidenceError("bounded JSON manifest required")
    data = _parse_json(raw)
    if (set(data) != {"schema_version", "rights_basis", "source_evidence",
                      "recordings"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1):
        raise R2BEvidenceError("manifest schema not recognized")
    if (data["rights_basis"] not in
            ("locally_reviewed_license", "documented_consent")
            or data["source_evidence"] != "independent_takes_reviewed_locally"):
        raise R2BEvidenceError("rights and independent-take provenance required")
    items = data["recordings"]
    if type(items) is not list or not 10 <= len(items) <= 120:
        raise R2BEvidenceError("enough bounded independent audio takes required")
    names: set[str] = set()
    hashes: set[str] = set()
    take_ids: set[str] = set()
    groups: dict[tuple[str, str], list] = defaultdict(list)
    source_splits: dict[str, str] = {}
    for item in items:
        required = {"file", "source_id", "session_id", "take_id",
                    "split", "role", "sha256"}
        if type(item) is not dict or set(item) != required:
            raise R2BEvidenceError("unexpected audio record keys")
        filename, group, session, take = (
            item[k] for k in ("file", "source_id", "session_id", "take_id"))
        if (type(filename) is not str or not FILE_RE.fullmatch(filename)
                or not filename.endswith("." + media_ext)
                or type(group) is not str or not SOURCE_RE.fullmatch(group)
                or type(session) is not str or not TAKE_RE.fullmatch(session)
                or type(take) is not str or not TAKE_RE.fullmatch(take)
                or item["split"] not in SPLITS
                or item["role"] not in ("reference", "query")
                or type(item["sha256"]) is not str
                or not HEX64.fullmatch(item["sha256"])
                or filename in names or item["sha256"] in hashes
                or take in take_ids):
            raise R2BEvidenceError("unsafe, duplicate or invalid audio take")
        if group in source_splits and source_splits[group] != item["split"]:
            raise R2BEvidenceError("physical source leaks between splits")
        source_splits[group] = item["split"]
        names.add(filename)
        hashes.add(item["sha256"])
        take_ids.add(take)
        groups[(item["split"], group)].append(item)
    for split in SPLITS:
        sources = [group for (sp, group) in groups if sp == split]
        minimum = 2 if split in ("validation", "test_known") else 1
        if len(sources) < minimum:
            raise R2BEvidenceError("insufficient source-separated audio data")
        for source in sources:
            takes = groups[(split, source)]
            refs = [e for e in takes if e["role"] == "reference"]
            queries = [e for e in takes if e["role"] == "query"]
            if split in ("test_unknown", "validation_unknown"):
                if refs or not queries:
                    raise R2BEvidenceError("unknown source must not be enrolled")
            elif len(refs) < 1 or len(queries) < 1:
                raise R2BEvidenceError("same source needs independent ref/query")
            if len({e["session_id"] for e in takes}) != len(takes):
                raise R2BEvidenceError("reused session is not independent take")
    return tuple(items)


def _audio_manifest(raw: bytes):
    """Compatibility name; use the one shared local capture manifest parser."""
    return _capture_manifest(raw, media_ext="wav")


def _checked_take_path(media_root: Path, filename: str, extension: str) -> Path:
    if (not isinstance(media_root, Path) or not media_root.is_dir()
            or type(filename) is not str or not FILE_RE.fullmatch(filename)
            or not filename.endswith("." + extension)):
        raise R2BEvidenceError("approved local media directory required")
    target = media_root / filename
    if target.is_symlink() or target.resolve().parent != media_root.resolve():
        raise R2BEvidenceError("path traversal or media symlink forbidden")
    return target


def _read_png_take(media_root: Path, filename: str, sha: str):
    from PIL import Image
    target = _checked_take_path(media_root, filename, "png")
    if _digest(target, max_bytes=MAX_LOCAL_PNG_BYTES) != sha:
        raise R2BEvidenceError("PNG take checksum mismatch")
    with Image.open(target) as src:
        if (src.format != "PNG" or not 32 <= src.width <= 1024
                or not 32 <= src.height <= 1024):
            raise R2BEvidenceError("unsafe local PNG dimensions")
        src.load()
        return src.convert("RGB").resize(
            (224, 224), Image.Resampling.BILINEAR)


def _read_wav_take(media_root: Path, filename: str, sha: str):
    target = _checked_take_path(media_root, filename, "wav")
    if _digest(target, max_bytes=MAX_WAV_BYTES) != sha:
        raise R2BEvidenceError("WAV take checksum mismatch")
    import struct
    with wave.open(str(target), "rb") as src:
        if (src.getnchannels() != 1 or src.getsampwidth() != 2
                or src.getframerate() != 16000
                or src.getnframes() != 16000
                or src.getcomptype() != "NONE"):
            raise R2BEvidenceError("expected exactly 1 second PCM16 16kHz mono")
        pcm = src.readframes(16001)
    if len(pcm) != 32000:
        raise R2BEvidenceError("invalid PCM data")
    return struct.unpack("<16000h", pcm)


def _evaluate_manifest_descriptors(items, descriptors, *, kinds):
    """One shared source/session-separated evaluator for images AND audio."""
    split_groups = defaultdict(lambda: defaultdict(list))
    for item in items:
        split_groups[item["split"]][item["source_id"]].append(item)
    result = {}
    for kind in kinds:
        def cohort(split, *, known):
            refs = {
                group: tuple(descriptors[t["file"]] for t in takes
                             if t["role"] == "reference")
                for group, takes in split_groups[split].items()
                if known
            }
            queries = tuple(
                (group, idx, descriptors[t["file"]])
                for group, takes in split_groups[split].items()
                for idx, t in enumerate(takes) if t["role"] == "query"
            )
            return refs, queries
        val_r, val_q = cohort("validation", known=True)
        _, val_unknown = cohort("validation_unknown", known=False)
        test_r, test_q = cohort("test_known", known=True)
        _, unk_q = cohort("test_unknown", known=False)
        threshold = conservative_threshold(
            _negative_scores(val_r, val_q + val_unknown, kind=kind))
        result[kind] = {
            "threshold_frozen_on_validation_only": threshold,
            "validation": _metrics(
                val_r, val_q + val_unknown, kind=kind, cutoff=threshold),
            "test": _metrics(test_r, test_q + unk_q,
                             kind=kind, cutoff=threshold),
        }
    return result


def run_audio_manifest(manifest: Path, media_root: Path, audio_model=None):
    if (not isinstance(manifest, Path) or not manifest.is_file()
            or manifest.is_symlink()
            or not 1 <= manifest.stat().st_size <= MAX_MANIFEST_BYTES):
        raise R2BEvidenceError("manifest file required")
    items = _audio_manifest(manifest.read_bytes())
    np = None
    if audio_model is not None:
        import numpy as np
    descriptors = {}
    timings: list[float] = []
    before = resource.getrusage(resource.RUSAGE_SELF)
    started = time.perf_counter()
    for item in items:
        samples = _read_wav_take(
            media_root, item["file"], item["sha256"])
        record = {"legacy": _audio_baseline(samples)}
        if audio_model is not None:
            record["learned"] = _audio_learned(
                audio_model, samples, np, timings)
        descriptors[item["file"]] = record
    kinds = ("legacy", "learned") if audio_model is not None else ("legacy",)
    result = _evaluate_manifest_descriptors(items, descriptors, kinds=kinds)
    after = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "scenario": "local_independent_audio_manifest_self_attested",
        "rights_and_source_independence": "declared_not_authenticated",
        "manifest_entries": len(items),
        "audio_model_onnx": audio_model is not None,
        "audio_inference_host": _latency(timings) if timings else None,
        "host_cpu_user_s": round(after.ru_utime-before.ru_utime, 3),
        "host_cpu_system_s": round(after.ru_stime-before.ru_stime, 3),
        "host_peak_rss_kib_whole_process": after.ru_maxrss,
        "host_wall_s_excludes_media_collection": round(
            time.perf_counter()-started, 3),
        "raw_audio_committed_or_saved_to_sqlite": False,
        "motor_commands": 0, "pc_requests": 0,
        "hardware_validated": False, "candidates": result,
    }


def run_image_manifest(manifest: Path, media_root: Path, model_file: Path | None = None):
    """Evaluate independent local PNG takes with the same protocol as WAV.

    Source/session/rights labels are SELF-ATTESTED; no image, box, label,
    source ID or path is written back to disk or the report.
    """
    if (not isinstance(manifest, Path) or not manifest.is_file()
            or manifest.is_symlink()
            or not 1 <= manifest.stat().st_size <= MAX_MANIFEST_BYTES):
        raise R2BEvidenceError("approved private image manifest required")
    items = _capture_manifest(manifest.read_bytes(), media_ext="png")
    session = None
    np = None
    if model_file is not None:
        check_model_file(model_file)
        import onnxruntime as ort
        import numpy as np
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(model_file), sess_options=opts,
            providers=["CPUExecutionProvider"])
    before = resource.getrusage(resource.RUSAGE_SELF)
    started = time.perf_counter()
    timings: list[float] = []
    descriptors = {}
    for item in items:
        image = _read_png_take(media_root, item["file"], item["sha256"])
        record = {"legacy": image_fingerprint(_image_baseline(image))}
        if session is not None:
            record["learned"] = _image_learned(
                session, image, np, timings)
        descriptors[item["file"]] = record
    kinds = ("legacy", "learned") if session is not None else ("legacy",)
    results = _evaluate_manifest_descriptors(
        items, descriptors, kinds=kinds)
    after = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "scenario": "local_independent_png_capture_manifest_self_attested",
        "rights_and_source_independence": "declared_not_authenticated",
        "manifest_entries": len(items),
        "image_model_onnx": session is not None,
        "host_onnx_inference": _latency(timings) if timings else None,
        "host_cpu_user_s": round(after.ru_utime-before.ru_utime, 3),
        "host_cpu_system_s": round(after.ru_stime-before.ru_stime, 3),
        "host_peak_rss_kib_whole_process": after.ru_maxrss,
        "host_wall_s_excludes_capture": round(
            time.perf_counter()-started, 3),
        "raw_media_committed_or_saved_to_sqlite": False,
        "motor_commands": 0, "pc_requests": 0,
        "hardware_validated": False, "candidates": results,
    }


def _abo_https_bytes(url: str, *, limit: int) -> bytes:
    """Only the official public ABO S3 bucket. No user-defined URLs."""
    from urllib.parse import urlparse
    from urllib.request import Request, urlopen
    if (type(url) is not str or not url.startswith(
            "https://" + ABO_HOST + "/")
            or urlparse(url).hostname != ABO_HOST
            or not 1 <= limit <= ABO_MAX_JPEG_BYTES):
        raise R2BEvidenceError("unsupported external ABO URL or byte budget")
    with urlopen(Request(url, headers={
        "User-Agent": "MicroduckCompanion-R2B-CCBY-research/1",
    }), timeout=25) as response:
        target = urlparse(response.geturl())
        if target.scheme != "https" or target.hostname != ABO_HOST:
            raise R2BEvidenceError("untrusted remote media redirect")
        data = response.read(limit + 1)
    if not 100 <= len(data) <= limit:
        raise R2BEvidenceError("invalid or oversized ABO media")
    return data


def _abo_spin_sample():
    """Select first 12 COMPLETE distinct spin sequences deterministically.

    The metadata belongs to the official CC BY 4.0 ABO dataset. Spin IDs
    signify *sequences*; two distinct spin IDs are NOT independently proven
    distinct physical objects. We intentionally do not read names/listings.
    """
    from urllib.request import Request, urlopen
    from urllib.parse import urlparse
    allowed = re.compile(r"[0-9a-f]{8}\Z", re.ASCII)
    groups: dict[str, dict[int, str]] = {}
    order: list[str] = []
    with urlopen(Request(ABO_METADATA, headers={
        "User-Agent": "MicroduckCompanion-R2B-CCBY-research/1",
    }), timeout=30) as response:
        target = urlparse(response.geturl())
        if target.scheme != "https" or target.hostname != ABO_HOST:
            raise R2BEvidenceError("ABO metadata redirected outside provider")
        with gzip.GzipFile(fileobj=response) as compressed:
            with TextIOWrapper(compressed, encoding="utf-8", newline="") as data:
                reader = csv.DictReader(data)
                if reader.fieldnames != [
                    "spin_id", "azimuth", "image_id", "height",
                    "width", "path",
                ]:
                    raise R2BEvidenceError("ABO metadata column schema changed")
                for index, row in enumerate(reader):
                    if index > 650_000:
                        raise R2BEvidenceError("ABO metadata row budget exceeded")
                    spin = row.get("spin_id")
                    if type(spin) is not str or not allowed.fullmatch(spin):
                        raise R2BEvidenceError("invalid official ABO spin ID")
                    if spin not in groups:
                        if len(groups) >= 48:
                            continue
                        groups[spin] = {}
                        order.append(spin)
                    try:
                        angle = int(row["azimuth"])
                    except (TypeError, ValueError) as exc:
                        raise R2BEvidenceError("invalid ABO azimuth") from exc
                    if angle not in ABO_POSES:
                        continue
                    expected = (f"{spin[:2]}/{spin}/"
                                f"{spin}_{angle:02d}.jpg")
                    if row["path"] != expected or angle in groups[spin]:
                        raise R2BEvidenceError("ABO metadata path collision")
                    groups[spin][angle] = expected
                    if sum(len(v) == len(ABO_POSES) for v in groups.values()) >= (
                        ABO_SOURCE_COUNT
                    ):
                        break
    selected = [spin for spin in order
                if len(groups[spin]) == len(ABO_POSES)][:ABO_SOURCE_COUNT]
    if len(selected) != ABO_SOURCE_COUNT:
        raise R2BEvidenceError("not enough complete original ABO spin sequences")
    return tuple((spin, groups[spin]) for spin in selected)


def run_public_abo(*, model_file: Path | None = None):
    """Opt-in public CC BY 4.0 photograph study. No media persistence.

    Only 12 physical-product turntable sequences; same-session frames,
    no independent filming session and no household recognition claimed.
    """
    from PIL import Image
    model = None
    np = None
    if model_file is not None:
        check_model_file(model_file)
        import numpy as np
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        model = ort.InferenceSession(
            str(model_file), sess_options=options,
            providers=["CPUExecutionProvider"])
    before = resource.getrusage(resource.RUSAGE_SELF)
    started = time.perf_counter()
    selected = _abo_spin_sample()
    all_hashes: set[str] = set()
    sample_hashes = []
    vectors = {}
    times: list[float] = []
    for spin, paths in selected:
        for angle in ABO_POSES:
            url = ("https://" + ABO_HOST + "/spins/original/"
                   + paths[angle])
            jpg = _abo_https_bytes(url, limit=ABO_MAX_JPEG_BYTES)
            if not (jpg.startswith(b"\xff\xd8") and jpg.endswith(b"\xff\xd9")):
                raise R2BEvidenceError("invalid ABO JPEG payload")
            digest = hashlib.sha256(jpg).hexdigest()
            if digest in all_hashes:
                raise R2BEvidenceError("exact duplicate independent ABO views")
            all_hashes.add(digest)
            sample_hashes.append(digest)
            with Image.open(BytesIO(jpg)) as source:
                if (source.format != "JPEG" or source.width > 4096
                        or source.height > 4096
                        or min(source.size) < 32):
                    raise R2BEvidenceError("invalid ABO JPEG geometry")
                image = source.convert("RGB").resize(
                    (224, 224), Image.Resampling.BILINEAR)
            record = {"legacy": image_fingerprint(_image_baseline(image))}
            if model is not None:
                record["learned"] = _image_learned(model, image, np, times)
            vectors[(spin, angle)] = record
    val = tuple(spin for spin, _ in selected[:5])
    val_unknown = tuple(spin for spin, _ in selected[5:6])
    test_known = tuple(spin for spin, _ in selected[6:10])
    test_unknown = tuple(spin for spin, _ in selected[10:12])

    def cohort(enrolled, unseen=()):
        refs = {sid: tuple(vectors[(sid, a)] for a in ABO_REFS)
                for sid in enrolled}
        query = tuple((sid, angle, vectors[(sid, angle)])
                      for sid in (*enrolled, *unseen)
                      for angle in ABO_QUERIES)
        return refs, query

    val_ref, val_q = cohort(val, val_unknown)
    test_ref, test_q = cohort(test_known, test_unknown)
    results = {}
    for kind in ("legacy", "learned") if model is not None else ("legacy",):
        threshold = conservative_threshold(
            _negative_scores(val_ref, val_q, kind=kind))
        results[kind] = {
            "threshold_frozen_on_validation_only": threshold,
            "validation": _metrics(
                val_ref, val_q, kind=kind, cutoff=threshold),
            "test": _metrics(
                test_ref, test_q, kind=kind, cutoff=threshold),
        }
    after = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "scenario": "ABO_CC_BY_4_public_turntable_same_session_views",
        "license_source": ABO_CC_BY_SOURCE,
        "citation": ("Amazon.com, Guillaumin et al.; "
                     "ABO dataset; CC BY 4.0"),
        "source_sequences": len(selected),
        "unique_real_jpeg_frames": len(sample_hashes),
        "reference_pose_indices": list(ABO_REFS),
        "query_pose_indices": list(ABO_QUERIES),
        "selected_spin_id_digest_not_source_identity": hashlib.sha256(
            "|".join(s for s, _ in selected).encode()).hexdigest(),
        "selected_media_sha256_combined": hashlib.sha256(
            "".join(sample_hashes).encode()).hexdigest(),
        "distinct_physical_objects_verified_separately": False,
        "independent_capture_sessions": False,
        "same_turntable_sequence_frames": True,
        "trained_on_study_media": False,
        "image_model_onnx": model is not None,
        "host_image_onnx_inference": _latency(times) if times else None,
        "host_cpu_user_s": round(after.ru_utime-before.ru_utime, 3),
        "host_cpu_system_s": round(after.ru_stime-before.ru_stime, 3),
        "host_peak_rss_kib_whole_process": after.ru_maxrss,
        "host_wall_s_includes_network": round(time.perf_counter()-started, 3),
        "raw_media_saved_or_committed": False,
        "sqlite_written": False,
        "motor_commands": 0, "pc_requests": 0,
        "hardware_validated": False,
        "candidates": results,
    }


def run_coil20(
    archive: Path, *, expected_sha256: str, model_file: Path | None = None,
    approved_noncommercial_research: bool = False,
):
    if approved_noncommercial_research is not True:
        raise R2BEvidenceError(
            "COIL20 requires reviewed noncommercial research authorization")
    timings = []
    model = None
    if model_file is not None:
        check_model_file(model_file)
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        model = ort.InferenceSession(str(model_file),
                                     sess_options=options,
                                     providers=["CPUExecutionProvider"])
    before = resource.getrusage(resource.RUSAGE_SELF)
    started = time.perf_counter()
    samples, timings = _image_samples(
        archive, expected_sha256=expected_sha256, model=model)
    result = evaluate_captures(
        samples, kinds=("legacy", "learned") if model else ("legacy",))
    after = resource.getrusage(resource.RUSAGE_SELF)
    result.update({
        "archive_sha256_operator_supplied": expected_sha256,
        "unique_independent_png_captures": len(samples),
        "image_model_onnx": model is not None,
        "host_image_onnx_inference": _latency(timings) if timings else None,
        "host_cpu_user_s_for_sample_loop": round(after.ru_utime-before.ru_utime, 3),
        "host_cpu_system_s_for_sample_loop": round(after.ru_stime-before.ru_stime, 3),
        "host_peak_rss_kib_whole_process": after.ru_maxrss,
        "host_total_wall_s_excludes_archive_download": round(
            time.perf_counter()-started, 3),
    })
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-abo-ccby", action="store_true")
    parser.add_argument("--coil20-zip", type=Path)
    parser.add_argument("--coil20-reviewed-sha256")
    parser.add_argument("--noncommercial-coil20-permission-reviewed",
                        action="store_true")
    parser.add_argument("--image-model", type=Path)
    parser.add_argument("--image-manifest", type=Path)
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--audio-manifest", type=Path)
    parser.add_argument("--audio-root", type=Path)
    parser.add_argument("--audio-model", type=Path)
    parser.add_argument("--locally-approved-research", action="store_true")
    args = parser.parse_args(argv)
    if not args.locally_approved_research:
        parser.error("explicit research/rights approval required")
    if (args.coil20_zip is None and args.audio_manifest is None
            and args.image_manifest is None and not args.public_abo_ccby
            or (args.audio_manifest is None) != (args.audio_root is None)
            or (args.image_manifest is None) != (args.image_root is None)
            or args.coil20_zip is not None and args.image_manifest is not None
            or args.public_abo_ccby and (
                args.image_manifest is not None or args.coil20_zip is not None)
            or (args.coil20_zip is None) != (
                args.coil20_reviewed_sha256 is None)
            or (args.coil20_zip is None and
                args.noncommercial_coil20_permission_reviewed)
            or args.image_model and (
                args.coil20_zip is None and args.image_manifest is None
                and not args.public_abo_ccby)
            or args.audio_model and args.audio_manifest is None):
        parser.error("choose zip and/or audio manifest+root; models optional")
    report = {}
    if args.public_abo_ccby:
        report["images_abo_public"] = run_public_abo(
            model_file=args.image_model)
    if args.coil20_zip is not None:
        report["images"] = run_coil20(
            args.coil20_zip,
            expected_sha256=args.coil20_reviewed_sha256,
            approved_noncommercial_research=(
                args.noncommercial_coil20_permission_reviewed),
            model_file=args.image_model)
    if args.image_manifest is not None:
        report["images_local"] = run_image_manifest(
            args.image_manifest, args.image_root,
            model_file=args.image_model)
    if args.audio_manifest is not None:
        session = None
        if args.audio_model is not None:
            check_audio_model(args.audio_model)
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(str(args.audio_model),
                 sess_options=options, providers=["CPUExecutionProvider"])
        report["audio"] = run_audio_manifest(
            args.audio_manifest, args.audio_root, audio_model=session)
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
