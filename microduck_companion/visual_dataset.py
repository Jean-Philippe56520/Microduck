"""F3-A: image-free annotation/evaluation contract, never image recognition.

Only strict, *opaque* sample/group IDs, category labels and SHA-256 digests
are processed. No images, filenames, URLs, people/pet identities, boxes, media
capture, robotd, mediad, model loading or Qwen. Synthetic demo predictions
cannot be represented as classifier performance on real camera imagery.

An allowed origin/rights field is self-declared metadata, not a verified
license, consent record, identity or source authentication.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
import re

from .passive_observations import OBJECT_CATEGORIES
from .perception import DETECTION_CONFIDENCE

MANIFEST_VERSION = 1
TASK = "single_label_visual_category"
PREDICTION_ORIGIN = "mock_prediction"
MAX_JSON_BYTES = 512 * 1024
MAX_SAMPLES = 4096
CATEGORIES = tuple(sorted(OBJECT_CATEGORIES))
SPLITS = ("train", "validation", "test")
_ORIGIN_RIGHTS = {
    "synthetic_fixture": ("generated_fixture", "deterministic_fixture"),
    "licensed_external": ("license_reviewed_locally", "human_reviewed"),
    "consented_private": ("consent_recorded_locally", "human_reviewed"),
}
_SAMPLE_FIELDS = frozenset({
    "sample_id", "group_id", "fingerprint_sha256", "split", "category",
    "source_kind", "rights_basis", "annotation_basis",
})
_PREDICTION_FIELDS = frozenset({"sample_id", "category", "confidence"})
_SAMPLE_ID_RE = re.compile(r"s-[0-9a-f]{16}\Z", re.ASCII)
_GROUP_ID_RE = re.compile(r"g-[0-9a-f]{16}\Z", re.ASCII)
_SHA_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


class VisualProtocolError(ValueError):
    """An untrusted manifest/prediction violates the strict F3-A contract."""


@dataclass(frozen=True)
class VisualSample:
    sample_id: str
    group_id: str
    fingerprint_sha256: str
    split: str
    category: str
    source_kind: str
    rights_basis: str
    annotation_basis: str


@dataclass(frozen=True)
class VisualDataset:
    samples: tuple[VisualSample, ...]
    synthetic_only: bool

    def partition(self, split: str) -> tuple[VisualSample, ...]:
        if split not in SPLITS:
            raise ValueError("unknown partition")
        return tuple(s for s in self.samples if s.split == split)


@dataclass(frozen=True)
class CategoryScore:
    category: str
    support: int
    predicted: int
    true_positive: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class VisualEvaluation:
    """MOCK test-split classification metrics, NOT real detection metrics."""

    test_samples: int
    correct: int
    accuracy: float
    known_support: int
    unknown_support: int
    predicted_unknown: int
    low_confidence_abstentions: int
    coverage: float
    selective_accuracy: float | None
    unknown_recall: float
    macro_f1_known: float | None
    confusion: tuple[tuple[str, str, int], ...]
    per_category: tuple[CategoryScore, ...]
    prediction_source: str = PREDICTION_ORIGIN
    is_synthetic_only: bool = True
    executed_actions: int = 0
    motor_commands_issued: int = 0


def _unique_json_pairs(pairs: list[tuple[str, object]]) -> dict:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise VisualProtocolError("duplicate JSON key")
        out[key] = value
    return out


def _bad_constant(_: str) -> None:
    raise VisualProtocolError("NaN or infinite JSON numbers forbidden")


def _parse_json(raw: str | bytes) -> dict:
    """Batched metadata only; reject oversized or ambiguous input before use."""
    if type(raw) is bytes:
        if len(raw) > MAX_JSON_BYTES:
            raise VisualProtocolError("metadata byte budget exceeded")
        try:
            raw = raw.decode("utf-8")
        except UnicodeError as exc:
            raise VisualProtocolError("metadata must be UTF-8") from exc
    elif type(raw) is str:
        try:
            if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
                raise VisualProtocolError("metadata byte budget exceeded")
        except UnicodeError as exc:
            raise VisualProtocolError("metadata must be UTF-8") from exc
    else:
        raise TypeError("expected JSON string/bytes, not a file or image")
    try:
        result = json.loads(
            raw, object_pairs_hook=_unique_json_pairs,
            parse_constant=_bad_constant)
    except (ValueError, UnicodeError, RecursionError, TypeError) as exc:
        raise VisualProtocolError("invalid or ambiguous JSON metadata") from exc
    if type(result) is not dict:
        raise VisualProtocolError("root must be a JSON object")
    return result


def _field_str(value: object, *, choices: tuple[str, ...] | None = None) -> str:
    if type(value) is not str or (choices is not None and value not in choices):
        raise VisualProtocolError("unsupported controlled category/field")
    return value


def parse_visual_manifest(
    raw: str | bytes, *, allow_external: bool = False
) -> VisualDataset:
    """Validate metadata; never open files, license grants or camera streams.

    The repository/CI lane permits synthetic fixtures only. External licensed
    or private data need an explicit opt-in in a local-only workflow; declaring
    rights in JSON does NOT independently prove those rights exist.
    """
    if type(allow_external) is not bool:
        raise TypeError("allow_external must be explicit boolean")
    data = _parse_json(raw)
    if (set(data) != {"schema_version", "task", "samples"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != MANIFEST_VERSION
            or data["task"] != TASK):
        raise VisualProtocolError("unsupported manifest schema/task")
    records = data["samples"]
    if (type(records) is not list
            or not 1 <= len(records) <= MAX_SAMPLES):
        raise VisualProtocolError("invalid/oversized sample list")
    samples: list[VisualSample] = []
    sample_ids: set[str] = set()
    fingerprints: set[str] = set()
    groups: dict[str, str] = {}
    counts: Counter[str] = Counter()
    synthetic_only = True
    for row in records:
        if type(row) is not dict or set(row) != _SAMPLE_FIELDS:
            # Disallows media paths, names, faces, transcripts, boxes, URLs, etc.
            raise VisualProtocolError("sample contains missing or extra fields")
        sid = _field_str(row["sample_id"])
        group = _field_str(row["group_id"])
        digest = _field_str(row["fingerprint_sha256"])
        if (not _SAMPLE_ID_RE.fullmatch(sid)
                or not _GROUP_ID_RE.fullmatch(group)
                or not _SHA_RE.fullmatch(digest)):
            raise VisualProtocolError("opaque ID or SHA-256 digest malformed")
        if sid in sample_ids or digest in fingerprints:
            raise VisualProtocolError("duplicate sample or exact duplicate content")
        sample_ids.add(sid)
        fingerprints.add(digest)
        split = _field_str(row["split"], choices=SPLITS)
        if group in groups and groups[group] != split:
            raise VisualProtocolError("capture/subject group leaks across splits")
        groups[group] = split
        category = _field_str(row["category"], choices=CATEGORIES)
        origin = _field_str(
            row["source_kind"], choices=tuple(_ORIGIN_RIGHTS))
        rights = _field_str(row["rights_basis"])
        annotation = _field_str(row["annotation_basis"])
        if (rights, annotation) != _ORIGIN_RIGHTS[origin]:
            raise VisualProtocolError("origin/rights/annotation mismatch")
        if origin != "synthetic_fixture":
            synthetic_only = False
            if not allow_external:
                raise VisualProtocolError(
                    "non-synthetic data forbidden in public/CI fixture lane")
        counts[split] += 1
        samples.append(VisualSample(
            sid, group, digest, split, category, origin, rights, annotation))
    if any(counts[split] == 0 for split in SPLITS):
        raise VisualProtocolError("train/validation/test must be nonempty")
    holdout = tuple(s for s in samples if s.split == "test")
    if (not any(s.category == "unknown" for s in holdout)
            or not any(s.category != "unknown" for s in holdout)):
        raise VisualProtocolError(
            "test split must include known and unknown ground truth")
    return VisualDataset(tuple(samples), synthetic_only)


def evaluate_mock_predictions(
    dataset: VisualDataset, raw: str | bytes,
) -> VisualEvaluation:
    """Evaluate only TEST sample IDs with declared synthetic predictions.

    'unknown' is a legitimate abstention/output; insufficient confidence on
    a known class is mapped to unknown. Macro F1 excludes unknown and includes
    supported/predicted known classes only. This is NOT detection mAP, a
    probability calibration assessment or evidence of trained inference.
    """
    if not isinstance(dataset, VisualDataset):
        raise TypeError("requires validated VisualDataset")
    if not dataset.synthetic_only:
        raise VisualProtocolError(
            "mock prediction metrics cannot validate external/private images")
    data = _parse_json(raw)
    if (set(data) != {"schema_version", "source", "predictions"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != MANIFEST_VERSION
            or data["source"] != PREDICTION_ORIGIN):
        raise VisualProtocolError("predictions must declare mock provenance")
    records = data["predictions"]
    test = dataset.partition("test")
    if type(records) is not list or len(records) != len(test):
        raise VisualProtocolError("predictions must cover the test split once")
    allowed = {s.sample_id: s.category for s in test}
    if len(allowed) != len(test):
        raise VisualProtocolError("invalid duplicate test sample ID")
    responses: dict[str, str] = {}
    low_confidence = 0
    for row in records:
        if type(row) is not dict or set(row) != _PREDICTION_FIELDS:
            raise VisualProtocolError("unknown/extra prediction data")
        sample_id = _field_str(row["sample_id"])
        category = _field_str(row["category"], choices=CATEGORIES)
        confidence = row["confidence"]
        if (type(confidence) not in (int, float)
                or not math.isfinite(confidence)
                or not 0 <= confidence <= 1):
            raise VisualProtocolError("confidence must be finite in [0,1]")
        if sample_id not in allowed or sample_id in responses:
            raise VisualProtocolError("missing/extra/duplicate test prediction")
        if category != "unknown" and confidence < DETECTION_CONFIDENCE:
            category = "unknown"
            low_confidence += 1
        responses[sample_id] = category
    if set(responses) != set(allowed):
        raise VisualProtocolError("incomplete holdout predictions")

    pairs = [(s.category, responses[s.sample_id]) for s in test]
    matrix = Counter(pairs)
    correct = sum(1 for truth, pred in pairs if truth == pred)
    covered = sum(1 for _, pred in pairs if pred != "unknown")
    correct_covered = sum(
        1 for truth, pred in pairs if pred != "unknown" and truth == pred)
    unknown_support = sum(1 for truth, _ in pairs if truth == "unknown")
    unknown_correct = matrix[("unknown", "unknown")]
    scores = []
    for category in CATEGORIES:
        if category == "unknown":
            continue
        actual = sum(1 for truth, _ in pairs if truth == category)
        predicted = sum(1 for _, pred in pairs if pred == category)
        if not (actual or predicted):
            continue
        true_positive = matrix[(category, category)]
        precision = true_positive / predicted if predicted else 0.
        recall = true_positive / actual if actual else 0.
        f1 = (2 * precision * recall / (precision + recall)
              if precision + recall else 0.)
        scores.append(CategoryScore(
            category, actual, predicted, true_positive,
            precision, recall, f1))
    return VisualEvaluation(
        test_samples=len(test),
        correct=correct,
        accuracy=correct / len(test),
        known_support=len(test) - unknown_support,
        unknown_support=unknown_support,
        predicted_unknown=len(test) - covered,
        low_confidence_abstentions=low_confidence,
        coverage=covered / len(test),
        selective_accuracy=correct_covered / covered if covered else None,
        unknown_recall=unknown_correct / unknown_support,
        macro_f1_known=sum(x.f1 for x in scores) / len(scores) if scores else None,
        confusion=tuple(sorted((a, b, n) for (a, b), n in matrix.items())),
        per_category=tuple(scores),
    )
