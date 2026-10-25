"""F3-B real-photograph benchmark: download CC0 thumbs into RAM, never Git.

20 manually curated Wikimedia Commons file pages, distinct authors across
train/val/test. Only cat/dog model outputs + unknown abstention; no person,
identity, object bounding boxes, calibrated confidence or on-device claims.
Pillow is required for this *optional* real-data benchmark, not F1/F2/F3-A.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import time

from .visual_dataset import MANIFEST_VERSION, TASK, parse_visual_manifest
from .visual_photo_baseline import (
    PHOTO_CATALOG, TinyRGBKNN, choose_threshold, evaluate_holdout,
    fetch_thumbnail, sample_features, validate_catalog, validate_samples,
)


def _metadata_manifest(samples) -> str:
    """Pass REAL-photo fingerprints through F3-A's group-isolated contract.

    Public file descriptions/CC0 declarations were manually reviewed;
    individual downloaded pixels/visual class labels have not been double
    annotated independently. The manifest is held in memory, not persisted.
    """
    rows = []
    for photo, sample in zip(PHOTO_CATALOG, samples):
        if (photo.category,photo.split,photo.author) != (
                sample.category,sample.split,sample.group):
            raise ValueError("source ordering mismatch")
        sid = hashlib.sha256(photo.file_page.encode("utf-8")).hexdigest()[:16]
        gid = hashlib.sha256(photo.author.encode("utf-8")).hexdigest()[:16]
        rows.append({
            "sample_id": "s-" + sid,
            "group_id": "g-" + gid,
            "fingerprint_sha256": sample.content_sha256,
            "split": photo.split, "category": photo.category,
            "source_kind": "licensed_external",
            "rights_basis": "license_reviewed_locally",
            "annotation_basis": "human_reviewed",
        })
    return json.dumps({
        "schema_version": MANIFEST_VERSION, "task": TASK, "samples": rows,
    },allow_nan=False,sort_keys=True)


def run_benchmark(*, fetch=fetch_thumbnail, extract=sample_features) -> dict:
    """No network or image bytes in return/log; exception on partial download."""
    validate_catalog()
    started = time.perf_counter_ns()
    samples=[]
    for photo in PHOTO_CATALOG:
        payload=fetch(photo)  # by default, HTTP to Wikimedia only
        samples.append(extract(photo,payload))
    samples=tuple(samples)
    acquisition_ms=(time.perf_counter_ns()-started)/1e6
    validate_samples(samples)
    manifest=parse_visual_manifest(_metadata_manifest(samples),allow_external=True)
    if manifest.synthetic_only or len(manifest.samples)!=len(samples):
        raise RuntimeError("F3-A external photo manifest failed")
    train=tuple(s for s in samples if s.split=="train")
    validation=tuple(s for s in samples if s.split=="validation")
    holdout=tuple(s for s in samples if s.split=="test")
    start_cpu=time.process_time_ns()
    start_wall=time.perf_counter_ns()
    model=TinyRGBKNN(train)
    thresholds=choose_threshold(model,validation)
    val_metrics=evaluate_holdout(  # validation-only tuning diagnostics
        model, tuple(s.__class__(
            s.category,"test",s.group,s.content_sha256,s.values)
            for s in validation),thresholds
    )
    metrics=evaluate_holdout(model,holdout,thresholds)
    inference_wall_ms=(time.perf_counter_ns()-start_wall)/1e6
    inference_cpu_ms=(time.process_time_ns()-start_cpu)/1e6
    return {
        "scenario":"f3b_real_cc0_photos_host_cpu_only",
        "model":"handcrafted_rgb_features_knn3_not_neural",
        "source":"Wikimedia Commons CC0 (public uploader declarations)",
        "licensing_note":"self-declared_CC0_manual_page_review_not_rights_warranty",
        "image_bytes_persisted":0,
        "image_count_processed":len(samples),
        "author_groups":len({p.author for p in PHOTO_CATALOG}),
        "partitions":dict(sorted(Counter(p.split for p in PHOTO_CATALOG).items())),
        "thresholds_selected_on_validation":asdict(thresholds),
        "validation_diagnostic":asdict(val_metrics),
        "test_heldout_metrics":asdict(metrics),
        "download_wall_ms_host":round(acquisition_ms,3),
        "train_and_evaluation_wall_ms_host":round(inference_wall_ms,3),
        "train_and_evaluation_cpu_ms_host":round(inference_cpu_ms,3),
        "camera_validated":False,
        "robot_hardware_benchmarked":False,
        "individual_recognition":False,
        "motor_commands_issued":0,
    }


def main() -> int:
    print(json.dumps(run_benchmark(),sort_keys=True,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
