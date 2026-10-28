"""C3-A: strictly synthetic, paired *measurement preflight* for memory ablations.

Reuses F3-A's proven manifest/split and prediction evaluator. This module
does NOT run C1, F2, Qwen, mediad, robotd or any model. The caller's labels
"without_memory"/"with_memory"/"with_pc" are MOCK lane names, not proof that
any memory or PC consultation occurred. A measured fixture score difference
cannot establish learning, generalization, causal effect or safe motor action.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from .visual_dataset import (
    DETECTION_CONFIDENCE, VisualDataset, VisualEvaluation,
    evaluate_mock_predictions, parse_visual_manifest,
)


@dataclass(frozen=True)
class C3MockLane:
    """A fixture-prediction score; no real sensor or model was executed."""

    score: VisualEvaluation
    declared_group_balanced_accuracy: float
    unknown_false_accepts: int


@dataclass(frozen=True)
class C3MockComparison:
    """Paired fixture scores with explicitly unverified ablation attribution."""

    without_memory: C3MockLane
    with_memory: C3MockLane
    with_pc: C3MockLane | None
    declared_test_groups: int
    sample_accuracy_delta_mock: float
    group_balanced_accuracy_delta_mock: float
    evaluated_synthetic_fixtures: bool = True
    ablation_execution_verified: bool = False
    independent_scenes_verified: int = 0
    real_sensors_verified: bool = False
    memory_benefit_verified: bool = False
    qwen_called: bool = False
    causal_effects_verified: int = 0
    physical_actions_authorized: bool = False
    memory_writes: int = 0
    motor_commands_issued: int = 0


def _mock_lane(dataset: VisualDataset, raw: str | bytes) -> C3MockLane:
    """Score through the existing F3-A validator before grouping predictions.

    Each declared group has equal weight, preventing repeated views of one
    group from automatically dominating the sample-weighted number. The IDs
    are caller-declared, never proof that different real scenes were captured.
    """
    score = evaluate_mock_predictions(dataset, raw)
    data = json.loads(raw)
    test = {s.sample_id: s for s in dataset.partition("test")}
    counts: dict[str, list[int]] = {}
    for record in data["predictions"]:
        sample = test[record["sample_id"]]
        predicted = record["category"]
        if predicted != "unknown" and record["confidence"] < DETECTION_CONFIDENCE:
            predicted = "unknown"
        group = counts.setdefault(sample.group_id, [0, 0])
        group[0] += int(predicted == sample.category)
        group[1] += 1
    if not counts:
        raise ValueError("test groups absent")
    balanced = sum(correct / total for correct, total in counts.values()) / len(counts)
    false_accepts = sum(
        n for truth, predicted, n in score.confusion
        if truth == "unknown" and predicted != "unknown"
    )
    return C3MockLane(score, balanced, false_accepts)


def compare_mock_category_ablations(
    manifest_json: str | bytes, without_memory_json: str | bytes,
    with_memory_json: str | bytes, *, with_pc_json: str | bytes | None = None,
) -> C3MockComparison:
    """Compare three *declared* mock prediction lanes on one protected TEST.

    Reuses the F3-A train/validation/test split guard (group and SHA
    anti-leakage, controlled labels, unknown cases, rights declarations).
    Each lane must independently cover exactly the same TEST samples once,
    with mock_prediction provenance. External/private datasets are REFUSED:
    real C3 needs an independently attested Cat-A2b pipeline, not this scorer.
    No training, inference, C1 connection, disk I/O or state mutation occurs.
    """
    dataset = parse_visual_manifest(manifest_json, allow_external=False)
    without = _mock_lane(dataset, without_memory_json)
    with_recall = _mock_lane(dataset, with_memory_json)
    optional_pc = (
        _mock_lane(dataset, with_pc_json)
        if with_pc_json is not None else None
    )
    groups = {s.group_id for s in dataset.partition("test")}
    return C3MockComparison(
        without_memory=without,
        with_memory=with_recall,
        with_pc=optional_pc,
        declared_test_groups=len(groups),
        sample_accuracy_delta_mock=(
            with_recall.score.accuracy - without.score.accuracy
        ),
        group_balanced_accuracy_delta_mock=(
            with_recall.declared_group_balanced_accuracy
            - without.declared_group_balanced_accuracy
        ),
    )
