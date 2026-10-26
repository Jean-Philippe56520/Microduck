"""R2-B+2: source-separated comparison among ABO products of ONE product type.

Host/CI-only, opt-in, read-only. Reuses the R2-B ABO image fetcher, model,
fingerprints, frozen validation thresholds and abstention diagnostics. A
distinct item_id is a distinct CATALOGUE LISTING, not certified proof of
distinct manufactured objects or a new physical capture session.

Predeclared metadata class CHAIR is a same-category hard-negative PROXY.
No test-driven class/product/model selection. No media, identity, SQLite,
microphone, OEM service, motor or LLM access.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import resource
import statistics
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .r2b_independent_capture_eval import (
    ABO_HOST, ABO_CC_BY_SOURCE, ABO_POSES, ABO_REFS, ABO_QUERIES,
    ABO_MAX_JPEG_BYTES, R2BEvidenceError,
    _abo_spin_sample, _abo_https_bytes,
    _metrics, _negative_scores, _predict,
)
from .compact_multimodal_memory import image_fingerprint
from .m1b2_host_embeddings import (
    _image_baseline, _image_learned, _latency, conservative_threshold,
)
from .visual_photo_mobilenet_demo import check_model_file

# Defined before image access or any model score; changing this means a
# distinct future evaluation, not tuning on the held-out test.
CATEGORY = "CHAIR"
SHARDS = (0, 1)
VAL_KNOWN, VAL_UNKNOWN = 8, 4
TEST_KNOWN, TEST_UNKNOWN = 12, 6
SOURCE_COUNT = VAL_KNOWN + VAL_UNKNOWN + TEST_KNOWN + TEST_UNKNOWN
MAX_GZ_BYTES = 8_000_000
MAX_INFLATED_BYTES = 45_000_000
MAX_ITEMS_PER_SHARD = 12_000
MAX_CANDIDATES = 300
SPIN_RE = re.compile(r"[0-9a-f]{8}\Z", re.ASCII)
ITEM_RE = re.compile(r"[A-Z0-9]{10,14}\Z", re.ASCII)
LISTING_BASE = "https://" + ABO_HOST + "/listings/metadata/listings_{}.json.gz"


def _read_metadata(url: str, *, opener=None) -> bytes:
    if (url not in tuple(LISTING_BASE.format(i) for i in SHARDS)
            or type(url) is not str):
        raise R2BEvidenceError("official predefined ABO listing shard required")
    operation = opener or urlopen
    with operation(Request(url, headers={
        "User-Agent": "Microduck-R2B2-ABO-CCBY-research/1"
    }), timeout=30) as response:
        target = urlparse(response.geturl())
        if target.scheme != "https" or target.hostname != ABO_HOST:
            raise R2BEvidenceError("ABO listing redirected to untrusted host")
        raw = response.read(MAX_GZ_BYTES + 1)
    if not 1 <= len(raw) <= MAX_GZ_BYTES:
        raise R2BEvidenceError("ABO compressed metadata byte budget exceeded")
    return raw


def _parse_listings(chunks: tuple[bytes, ...]) -> dict[str, str]:
    """Map spin ID -> unique catalogue item ID, never collect titles/faces."""
    if type(chunks) is not tuple or len(chunks) != len(SHARDS):
        raise R2BEvidenceError("two fixed ABO metadata shards required")
    allowed: dict[str, str] = {}
    seen_items: set[str] = set()
    for packed in chunks:
        count = 0
        bytes_seen = 0
        try:
            with gzip.GzipFile(fileobj=BytesIO(packed)) as source:
                for line in source:
                    count += 1
                    bytes_seen += len(line)
                    if (count > MAX_ITEMS_PER_SHARD
                            or bytes_seen > MAX_INFLATED_BYTES
                            or len(line) > 120_000):
                        raise R2BEvidenceError("ABO listing decompression budget")
                    obj = json.loads(line)
                    if type(obj) is not dict:
                        raise R2BEvidenceError("invalid ABO catalogue entry")
                    product_type = obj.get("product_type")
                    labels = (
                        [x.get("value") for x in product_type
                         if type(x) is dict]
                        if type(product_type) is list else [])
                    if CATEGORY not in labels:
                        continue
                    spin, item = obj.get("spin_id"), obj.get("item_id")
                    if spin is None:
                        continue
                    if (type(spin) is not str or not SPIN_RE.fullmatch(spin)
                            or type(item) is not str or
                            not ITEM_RE.fullmatch(item)):
                        raise R2BEvidenceError("invalid CHAIR spin / item ID")
                    if item in seen_items:
                        continue
                    if spin in allowed:
                        if allowed[spin] != item:
                            raise R2BEvidenceError("same spin maps to two items")
                        continue
                    seen_items.add(item)
                    allowed[spin] = item
                    if len(allowed) > MAX_CANDIDATES:
                        raise R2BEvidenceError("too many eligible ABO listings")
        except (OSError, EOFError, ValueError, UnicodeDecodeError) as exc:
            if isinstance(exc, R2BEvidenceError):
                raise
            raise R2BEvidenceError("malformed ABO gzipped listing metadata") from exc
    if len(allowed) < SOURCE_COUNT:
        raise R2BEvidenceError("insufficient CHAIR listings with spin IDs")
    return allowed


def _splits(selected: tuple, spin_to_item: dict[str, str]) -> dict:
    """Verify 30 unique item IDs and assign fixed disjoint source cohorts."""
    if (type(selected) is not tuple or len(selected) != SOURCE_COUNT
            or type(spin_to_item) is not dict):
        raise R2BEvidenceError("exact R2-B+2 30-sequence roster required")
    spins = [s for s, _ in selected]
    if (len(set(spins)) != SOURCE_COUNT or
            any(s not in spin_to_item for s in spins) or
            len({spin_to_item[s] for s in spins}) != SOURCE_COUNT):
        raise R2BEvidenceError("reused product listing between cohorts")
    if any(set(p) != set(ABO_POSES) for _, p in selected):
        raise R2BEvidenceError("incomplete ABO multi-angle sequence")
    boundaries = (
        VAL_KNOWN, VAL_KNOWN + VAL_UNKNOWN,
        VAL_KNOWN + VAL_UNKNOWN + TEST_KNOWN, SOURCE_COUNT,
    )
    return {
        "validation_known": tuple(spins[:boundaries[0]]),
        "validation_unknown": tuple(spins[boundaries[0]:boundaries[1]]),
        "test_known": tuple(spins[boundaries[1]:boundaries[2]]),
        "test_unknown": tuple(spins[boundaries[2]:boundaries[3]]),
    }


def _cohort(vectors: dict, enrolled: tuple, unknown: tuple) -> tuple:
    refs = {s: tuple(vectors[(s, a)] for a in ABO_REFS)
            for s in enrolled}
    queries = tuple((s, a, vectors[(s, a)])
                    for s in (*enrolled, *unknown)
                    for a in ABO_QUERIES)
    return refs, queries


def _anonymized_confusions(refs, queries, *, kind: str,
                          threshold: float) -> dict:
    """Report actual wrong acceptances and cross-object hard-negative scores.

    IDs are ordinal indices from the predeclared roster, not spin/item IDs.
    Report means across correlated angle frames; NOT confidence intervals.
    """
    all_sources = sorted({s for s, _, _ in queries} | set(refs))
    index = {sid: i+1 for i, sid in enumerate(all_sources)}
    errors: Counter[tuple] = Counter()
    for sid, _, vector in queries:
        predicted, _ = _predict(
            refs, vector, kind=kind, threshold=threshold)
        if predicted is not None and predicted != sid:
            errors[(index[sid], index[predicted])] += 1
    return {
        "pair_errors_anonymous": [
            {"query_index": pair[0], "wrong_reference_index": pair[1],
             "count": n}
            for pair, n in sorted(errors.items(), key=lambda x:(-x[1], x[0]))
        ][:12],
        "wrong_pair_total": sum(errors.values()),
    }


def evaluate_vectors(vectors: dict, groups: dict, *,
                     kinds: tuple = ("legacy",)) -> dict:
    if kinds not in (("legacy",), ("legacy", "learned")):
        raise R2BEvidenceError("only existing R2-B descriptors allowed")
    if set(vectors) != {(sid, angle)
                        for cohort in groups.values()
                        for sid in cohort for angle in ABO_POSES}:
        raise R2BEvidenceError("missing or additional image descriptors")
    vr, vq = _cohort(vectors, groups["validation_known"],
                     groups["validation_unknown"])
    tr, tq = _cohort(vectors, groups["test_known"], groups["test_unknown"])
    result = {}
    for kind in kinds:
        if any(kind not in record for record in vectors.values()):
            raise R2BEvidenceError("incomplete image descriptor candidate")
        threshold = conservative_threshold(_negative_scores(
            vr, vq, kind=kind))
        result[kind] = {
            "threshold_frozen_on_validation_only": threshold,
            "validation": _metrics(vr, vq, kind=kind, cutoff=threshold),
            "test": _metrics(tr, tq, kind=kind, cutoff=threshold),
            "validation_confusions": _anonymized_confusions(
                vr, vq, kind=kind, threshold=threshold),
            "test_confusions": _anonymized_confusions(
                tr, tq, kind=kind, threshold=threshold),
        }
    return result


def run(*, model_file: Path | None = None, opener=None) -> dict:
    """One-shot host comparison on same-class product listings, no retries by score."""
    from PIL import Image
    model = None
    np = None
    if model_file is not None:
        check_model_file(model_file)
        import numpy as np
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        model = ort.InferenceSession(
            str(model_file), sess_options=opts,
            providers=["CPUExecutionProvider"])
    started = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    chunks = tuple(_read_metadata(LISTING_BASE.format(i), opener=opener)
                   for i in SHARDS)
    catalogue = _parse_listings(chunks)
    selected = _abo_spin_sample(
        allowed_spin_ids=frozenset(catalogue), source_count=SOURCE_COUNT)
    groups = _splits(selected, catalogue)
    images: dict = {}
    timings: list[float] = []
    hashes: set[str] = set()
    ordered_hashes = []
    for sid, paths in selected:
        for angle in ABO_POSES:
            jpg = _abo_https_bytes(
                "https://" + ABO_HOST + "/spins/original/" + paths[angle],
                limit=ABO_MAX_JPEG_BYTES)
            if not (jpg.startswith(b"\xff\xd8") and jpg.endswith(b"\xff\xd9")):
                raise R2BEvidenceError("ABO JPEG invalid markers")
            digest = hashlib.sha256(jpg).hexdigest()
            if digest in hashes:
                raise R2BEvidenceError("exact reused image frame")
            hashes.add(digest)
            ordered_hashes.append(digest)
            with Image.open(BytesIO(jpg)) as img:
                if (img.format != "JPEG" or img.width > 4096
                        or img.height > 4096 or min(img.size) < 32):
                    raise R2BEvidenceError("invalid original ABO image geometry")
                resized = img.convert("RGB").resize(
                    (224, 224), Image.Resampling.BILINEAR)
            record = {"legacy": image_fingerprint(
                _image_baseline(resized))}
            if model is not None:
                record["learned"] = _image_learned(
                    model, resized, np, timings)
            images[(sid, angle)] = record
    candidates = evaluate_vectors(
        images, groups,
        kinds=("legacy", "learned") if model is not None else ("legacy",))
    after = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "scenario": "ABO_CC_BY_4_same_product_type_CHAIR_multiple_item_ids",
        "citation": "Amazon.com; Guillaumin et al.; ABO dataset; CC BY 4.0",
        "license_source": ABO_CC_BY_SOURCE,
        "predeclared_category": CATEGORY,
        "category_metadata_is_not_visual_similarity_proof": True,
        "catalogue_listings_with_spin_in_first_two_shards": len(catalogue),
        "distinct_catalogue_item_ids": SOURCE_COUNT,
        "distinct_manufactured_physical_objects_verified": False,
        "independent_photography_sessions": False,
        "same_spin_turntable_frames": True,
        "angles_per_sequence": len(ABO_POSES),
        "unique_real_jpeg_frames": len(hashes),
        "validation_known_items": len(groups["validation_known"]),
        "validation_unknown_items": len(groups["validation_unknown"]),
        "test_known_items": len(groups["test_known"]),
        "test_unknown_items": len(groups["test_unknown"]),
        "reference_pose_indices": list(ABO_REFS),
        "query_pose_indices": list(ABO_QUERIES),
        "selection_digest_not_identity": hashlib.sha256(
            "|".join(s for s, _ in selected).encode()).hexdigest(),
        "media_sha256_combined": hashlib.sha256(
            "".join(ordered_hashes).encode()).hexdigest(),
        "weights_sha256_checked": model is not None,
        "host_onnx_inference_ms": _latency(timings) if timings else None,
        "host_cpu_user_s": round(after.ru_utime - before.ru_utime, 3),
        "host_cpu_system_s": round(after.ru_stime - before.ru_stime, 3),
        "host_peak_rss_kib_process": after.ru_maxrss,
        "host_wall_s_including_network": round(
            time.perf_counter() - started, 3),
        "raw_images_saved": False, "sqlite_written": False,
        "motor_commands": 0, "pc_requests": 0,
        "hardware_validated": False,
        "candidates": candidates,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locally-approved-ccby-research",
                        action="store_true")
    parser.add_argument("--image-model", type=Path)
    args = parser.parse_args(argv)
    if not args.locally_approved_ccby_research:
        parser.error("explicit CC BY 4.0 research approval required")
    result = run(model_file=args.image_model)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
