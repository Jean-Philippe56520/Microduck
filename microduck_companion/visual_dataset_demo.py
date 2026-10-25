"""F3-A deterministic metadata-only fixture; NOT a trained image classifier.

All samples, digests and predictions are invented; no image bytes are opened.
The numbers printed here assess the evaluator itself, not detection accuracy.
"""
from __future__ import annotations

from dataclasses import asdict
from collections import Counter
import hashlib
import json

from .visual_dataset import (
    MANIFEST_VERSION, PREDICTION_ORIGIN, TASK,
    evaluate_mock_predictions, parse_visual_manifest,
)

TRAIN_LABELS = (
    "ball", "toy", "dog", "cat", "person", "microduck", "other_object",
    "unknown",
)
VALIDATION_LABELS = (
    "dog", "cat", "person", "ball", "toy", "microduck", "other_object",
    "unknown",
)
TEST_LABELS = (
    "dog", "cat", "person", "ball", "toy", "microduck", "other_object",
    "unknown", "dog", "cat", "unknown", "ball",
)
# Deliberate mistakes, explicit unknown, and low-confidence rejections.
MOCK_TEST_PREDICTIONS = (
    ("dog", .96),
    ("dog", .90),
    ("person", .70),
    ("ball", .96),
    ("toy", .96),
    ("microduck", .93),
    ("other_object", .88),
    ("unknown", 0.),
    ("dog", .95),
    ("cat", .89),
    ("dog", .40),
    ("toy", .90),
)


def fixture_json() -> tuple[str, str]:
    """Produce only controlled category metadata, no assets or real labels."""
    entries = []
    index = 1
    for split, labels in (
        ("train", TRAIN_LABELS),
        ("validation", VALIDATION_LABELS),
        ("test", TEST_LABELS),
    ):
        for category in labels:
            entries.append({
                "sample_id": f"s-{index:016x}",
                "group_id": f"g-{index:016x}",
                # Digest of synthetic *token*, NOT a real media fingerprint.
                "fingerprint_sha256": hashlib.sha256(
                    f"fictional-only-token-v1:{index}".encode("ascii")
                ).hexdigest(),
                "split": split, "category": category,
                "source_kind": "synthetic_fixture",
                "rights_basis": "generated_fixture",
                "annotation_basis": "deterministic_fixture",
            })
            index += 1
    test_entries = [s for s in entries if s["split"] == "test"]
    manifest = {
        "schema_version": MANIFEST_VERSION, "task": TASK, "samples": entries,
    }
    predicted = {
        "schema_version": MANIFEST_VERSION,
        "source": PREDICTION_ORIGIN,
        "predictions": [
            {"sample_id": sample["sample_id"], "category": category,
             "confidence": confidence}
            for sample, (category, confidence) in
            zip(test_entries, MOCK_TEST_PREDICTIONS)
        ],
    }
    return (
        json.dumps(manifest, sort_keys=True, allow_nan=False),
        json.dumps(predicted, sort_keys=True, allow_nan=False),
    )


def run_demo() -> dict:
    manifest, predictions = fixture_json()
    dataset = parse_visual_manifest(manifest)
    report = evaluate_mock_predictions(dataset, predictions)
    split_counts = dict(sorted(Counter(s.split for s in dataset.samples).items()))
    if split_counts != {"test": 12, "train": 8, "validation": 8}:
        raise RuntimeError("fictional evaluation fixture changed")
    return {
        "scope": "synthetic_metadata_only",
        "evaluation_kind": "synthetic_prediction_fixture_not_model_accuracy",
        "samples": len(dataset.samples),
        "split_counts": split_counts,
        "unknown_test_samples": report.unknown_support,
        "metrics": asdict(report),
        "opened_images": 0,
        "executed_actions": 0,
        "motor_commands_issued": 0,
        "physical_camera_validated": False,
    }


def main() -> int:
    print(json.dumps(run_demo(), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
