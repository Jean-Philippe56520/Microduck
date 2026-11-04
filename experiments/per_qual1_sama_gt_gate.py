"""PER-QUAL-1A: pre-inference Sama-COCO vs COCO label-source gate.

Only public annotation metadata is read. NO JPEGs, inference, model access,
robot control, model tuning, SQLite or independent-annotator claims.
Sama reannotators were seeded with COCO annotations; the labels are correlated.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import io
import json
import math
from pathlib import Path, PurePosixPath
import zipfile

SEED = "kwipi-per-qual1a-samacoco-paired-20261104-v1"
TARGETS = ("sports_ball", "book", "bottle", "chair", "dog", "cat", "person")
SAMPLES_PER_CLASS = 6
MAX_SAMA_ZIP = 20_000_000
MAX_SAMA_UNCOMPRESSED = 80_000_000
MIN_SIDE = 32
MAX_SIDE = 4096
# Captured from successful REAL label-only GitHub Actions #41879626743,
# before downloading any of these 42 JPEGs or running any YOLOX inference.
SAMA_ANNOTATION_ZIP_SHA256 = "c55454f6657ce63891783136cc5dfe5f1e9c5e1748c0d8ca08b456a804eab15f"
FROZEN_COHORT_SHA256 = "709718feba6185ddd79e2aa492c7eaf74bb2d904dfa6c30e81a25c31dbdb53d5"


class SourceGateError(ValueError):
    """An invalid or unqualified external ground-truth source."""


def _frozen_sha256(payload: bytes, expected: str, description: str) -> str:
    """Refuse source/roster drift; no model or image access."""
    actual = sha256(payload).hexdigest()
    if actual != expected:
        raise SourceGateError(description + " frozen SHA256 mismatch")
    return actual


def unpack_sama_archive(blob: bytes) -> dict:
    """Read only small COCO JSON shards, never extract paths to disk."""
    if type(blob) is not bytes or not 100 <= len(blob) <= MAX_SAMA_ZIP:
        raise SourceGateError("invalid bounded Sama annotation archive")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
        members = archive.infolist()
        if not 1 <= len(members) <= 64:
            raise SourceGateError("unsupported Sama archive entry count")
        total = 0
        shards = []
        seen_paths = set()
        for info in members:
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in info.filename
                    or info.filename in seen_paths or info.flag_bits & 1):
                raise SourceGateError("unsafe or duplicate archive entry")
            seen_paths.add(info.filename)
            if info.is_dir():
                continue
            if not info.filename.endswith(".json"):
                raise SourceGateError("unexpected non-JSON Sama archive entry")
            total += info.file_size
            if info.file_size > MAX_SAMA_UNCOMPRESSED or total > MAX_SAMA_UNCOMPRESSED:
                raise SourceGateError("Sama archive decompression budget exceeded")
            with archive.open(info) as fp:
                shard = json.loads(fp.read(MAX_SAMA_UNCOMPRESSED + 1))
            if (type(shard) is not dict or any(type(shard.get(k)) is not list
                    for k in ("images", "annotations", "categories"))):
                raise SourceGateError("Sama shard is not a COCO annotation object")
            shards.append(shard)
        if not shards:
            raise SourceGateError("no Sama annotations")
        # Use only the canonical taxonomies. The public archive may define
        # additional unused category IDs; reject any inconsistent definition.
        categories = shards[0]["categories"]
        canon = {c["id"]: c["name"] for c in categories
                 if type(c) is dict and type(c.get("id")) is int
                 and type(c.get("name")) is str}
        if len(canon) != len(categories):
            raise SourceGateError("duplicate/invalid Sama category mapping")
        images, annotations = [], []
        for shard in shards:
            cats = shard["categories"]
            if (len(cats) != len(categories) or
                    {c["id"]: c["name"] for c in cats} != canon):
                raise SourceGateError("conflicting Sama shard taxonomy")
            images.extend(shard["images"])
            annotations.extend(shard["annotations"])
        return {"categories": categories, "images": images,
                "annotations": annotations}
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError,
            EOFError, OSError) as exc:
        raise SourceGateError("corrupt Sama archive") from exc


def _images(data: dict) -> dict[int, tuple[int, int, str, int | None]]:
    if type(data) is not dict or type(data.get("images")) is not list:
        raise SourceGateError("missing image metadata")
    result = {}
    for row in data["images"]:
        if type(row) is not dict:
            raise SourceGateError("invalid image metadata")
        ident, w, h, filename = (row.get("id"), row.get("width"),
                                 row.get("height"), row.get("file_name"))
        if (type(ident) is not int or ident < 0 or ident in result
                or type(w) is not int or type(h) is not int
                or not MIN_SIDE <= w <= MAX_SIDE
                or not MIN_SIDE <= h <= MAX_SIDE
                or filename != f"{ident:012d}.jpg"):
            raise SourceGateError("invalid/duplicate image identity or geometry")
        result[ident] = (w, h, filename, row.get("license"))
    return result


def _category_ids(original: dict, sama: dict) -> dict[str, int]:
    expected = original.get("categories")
    actual = sama.get("categories")
    if type(expected) is not list or type(actual) is not list:
        raise SourceGateError("category metadata missing")
    orig = {c["id"]: c["name"] for c in expected}
    other = {c["id"]: c["name"] for c in actual}
    if (len(orig) != len(expected) or len(other) != len(actual)
            or any(other.get(ident) != name for ident, name in orig.items())):
        raise SourceGateError("Sama class IDs do not preserve official COCO names")
    used = {a.get("category_id") for a in sama.get("annotations", [])
            if type(a) is dict}
    if not used <= set(orig):
        raise SourceGateError("Sama annotation uses a non-COCO category")
    by_name = {name.replace(" ", "_"): ident for ident, name in orig.items()}
    if len(by_name) != len(orig) or any(name not in by_name for name in TARGETS):
        raise SourceGateError("missing or ambiguous target category")
    return {name: by_name[name] for name in TARGETS}


def _index_boxes(data: dict, images: dict, eligible: set[int]) -> tuple[dict, set[int]]:
    """Reject images with crowd or corrupt geometry; no synthetic negatives."""
    boxes: dict[tuple[int, int], list[tuple]] = defaultdict(list)
    forbidden = set()
    annotations = data.get("annotations")
    if type(annotations) is not list:
        raise SourceGateError("missing annotation records")
    seen_ids = set()
    for row in annotations:
        if type(row) is not dict or type(row.get("image_id")) is not int:
            raise SourceGateError("invalid annotation record")
        ident = row["image_id"]
        ann_id = row.get("id")
        if type(ann_id) is not int or ann_id in seen_ids:
            raise SourceGateError("missing/duplicate annotation ID")
        seen_ids.add(ann_id)
        if ident not in eligible:
            continue
        if row.get("iscrowd") not in (0, 1):
            forbidden.add(ident)
            continue
        if row["iscrowd"] == 1:
            forbidden.add(ident)
            continue
        box = row.get("bbox")
        if (type(box) is not list or len(box) != 4
                or any(type(x) not in (int, float) or not math.isfinite(x)
                       for x in box)):
            forbidden.add(ident)
            continue
        x, y, w, h = box
        W, H = images[ident][:2]
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > W + 1 or y + h > H + 1:
            forbidden.add(ident)
            continue
        boxes[(ident, row["category_id"])].append((float(x), float(y),
                                                    float(x+w), float(y+h)))
    return boxes, forbidden


def choose_paired_cohort(original: dict, sama: dict, *,
                         old_ids: frozenset[int], allowed_license_ids: frozenset[int],
                         per_class: int = SAMPLES_PER_CLASS):
    """Prospective 42-image cohort; selection sees only ground-truth metadata."""
    if (type(per_class) is not int or per_class != SAMPLES_PER_CLASS
            or type(old_ids) is not frozenset or type(allowed_license_ids) is not frozenset
            or any(type(i) is not int or i < 0 for i in old_ids | allowed_license_ids)):
        raise SourceGateError("invalid frozen prospective selection parameters")
    targets = _category_ids(original, sama)
    orig = _images(original)
    sam = _images(sama)
    if len(sam) != len(orig) or set(sam) != set(orig):
        raise SourceGateError("Sama images differ from official COCO validation IDs")
    eligible = set()
    for ident, (w, h, filename, license_id) in orig.items():
        sw, sh, sf, _ = sam[ident]
        if (w, h, filename) != (sw, sh, sf):
            raise SourceGateError("Sama image geometry/identity disagrees with COCO")
        if ident not in old_ids and license_id in allowed_license_ids:
            eligible.add(ident)
    orig_boxes, orig_bad = _index_boxes(original, orig, eligible)
    sama_boxes, sama_bad = _index_boxes(sama, sam, eligible)
    eligible -= orig_bad | sama_bad
    pools = {}
    for name, category_id in targets.items():
        pools[name] = sorted((ident for ident in eligible
                 if orig_boxes.get((ident, category_id)) and
                    sama_boxes.get((ident, category_id))),
            key=lambda ident: (sha256(f"{SEED}/{name}/{ident}".encode()).digest(), ident))
    taken = set(old_ids)
    cases = []
    # Rare classes first avoids allocating a shared scene to a common class.
    for name in sorted(TARGETS, key=lambda label: (len(pools[label]), TARGETS.index(label))):
        free = [ident for ident in pools[name] if ident not in taken]
        if len(free) < per_class:
            raise SourceGateError(f"STOP_SOURCE class={name} available={len(free)} "
                                  f"required={per_class}")
        for ident in free[:per_class]:
            cases.append((ident, name))
            taken.add(ident)
    if (len(cases) != len(TARGETS) * per_class or
            len({ident for ident, _ in cases}) != len(cases) or
            old_ids & {ident for ident, _ in cases}):
        raise SourceGateError("non-disjoint prospective cohort")
    return tuple(cases), targets, orig_boxes, sama_boxes, {
        "source_eligible_images": len(eligible),
        "source_excluded_bad_or_crowd": len(orig_bad | sama_bad),
        "per_class_available_before_assignment": {name: len(v) for name, v in pools.items()},
    }


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0., x1-x0)*max(0., y1-y0)
    area_a = (a[2]-a[0])*(a[3]-a[1])
    area_b = (b[2]-b[0])*(b[3]-b[1])
    union = area_a+area_b-intersection
    return intersection / union if union > 0 else 0.


def _paired_iou50(a, b):
    """Maximum one-to-one IoU50 matches, independent of annotation order.

    Greedy pairing is not sufficient: overlapping objects can give fewer
    matches when the first GT consumes the only match of the second GT.
    """
    edges = []
    for box in a:
        candidates = [(i, _iou(box, other)) for i, other in enumerate(b)]
        edges.append(tuple(i for i, score in sorted(
            (entry for entry in candidates if entry[1] >= .5),
            key=lambda entry: (-entry[1], entry[0]),
        )))

    owners = {}  # index into b -> index into a

    def augment(index, visited):
        for target in edges[index]:
            if target in visited:
                continue
            visited.add(target)
            if target not in owners or augment(owners[target], visited):
                owners[target] = index
                return True
        return False

    return sum(augment(index, set()) for index in range(len(a)))


def summarize_ground_truth(cases, targets, orig_boxes, sama_boxes):
    result = {name: dict(allocated_photos=0, original_gt_boxes=0,
                         sama_gt_boxes=0, paired_gt_boxes_iou50=0)
              for name in TARGETS}
    for ident, name in cases:
        idx = targets[name]
        orig = orig_boxes.get((ident, idx), ())
        new = sama_boxes.get((ident, idx), ())
        row = result[name]
        row["allocated_photos"] += 1
        row["original_gt_boxes"] += len(orig)
        row["sama_gt_boxes"] += len(new)
        row["paired_gt_boxes_iou50"] += _paired_iou50(orig, new)
    return result


def run_source_gate(annotations: Path, sama_zip: Path):
    from experiments.per80_yolox_coco_public import (
        P4_IDS, _cohort_from_pinned_source, _valid_license_ids,
    )
    from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint
    from microduck_companion.cata2_bbox_eval import MAX_COCO_JSON_BYTES

    for file, limit in ((annotations, MAX_COCO_JSON_BYTES), (sama_zip, MAX_SAMA_ZIP)):
        if (not isinstance(file, Path) or file.is_symlink() or not file.is_file()
                or not 100 <= file.stat().st_size <= limit):
            raise SourceGateError("invalid bounded or symlinked metadata source")
    original_blob = annotations.read_bytes()
    _, old_cases, _, _, _ = _cohort_from_pinned_source(original_blob)
    eighth, original, _, older = eighth_disjoint(original_blob)
    history = frozenset(older | {c.image_id for c in eighth} | P4_IDS |
                        {case.image_id for case, _ in old_cases})
    if len(history) != 1232:
        raise SourceGateError("historical COCO exclusion is not 432+800")
    archive_blob = sama_zip.read_bytes()
    sama_sha = _frozen_sha256(
        archive_blob, SAMA_ANNOTATION_ZIP_SHA256, "Sama source")
    sama = unpack_sama_archive(archive_blob)
    cases, targets, orig_gt, sama_gt, source = choose_paired_cohort(
        original, sama, old_ids=history,
        allowed_license_ids=_valid_license_ids(original))
    roster = "|".join(f"{ident}/{cat}" for ident, cat in cases)
    roster_sha = _frozen_sha256(
        roster.encode(), FROZEN_COHORT_SHA256, "prospective cohort")
    return {
        "experiment": "PER-QUAL-1A Sama-COCO secondary-human-GT source gate",
        "status": "SOURCE_GATE_PASS_NO_INFERENCE",
        "sama_zip_sha256": sama_sha,
        "original_coco_annotation_sha256": sha256(original_blob).hexdigest(),
        "cohort_selection_sha256": roster_sha,
        "excluded_previous_coco_val_images": len(history),
        "prospective_new_photos_selected": len(cases),
        "per_target_allocation": SAMPLES_PER_CLASS,
        "categories": list(TARGETS),
        "source": source,
        "paired_annotations": summarize_ground_truth(cases,targets,orig_gt,sama_gt),
        "gt_processes_independent_of_yolox_predictions": True,
        "gt_processes_statistically_independent": False,
        "images_fetched": 0,
        "inferences_executed": 0,
        "model_accessed": False,
        "viewpoint_height": "unknown",
        "safe_robot_perception_validated": False,
        "promotion": False,
        "motor_commands": 0, "sqlite_writes": 0, "qwen_calls": 0,
        "no_media_or_ids_published": True,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-metadata",action="store_true")
    p.add_argument("--annotations",required=True,type=Path)
    p.add_argument("--sama-zip",required=True,type=Path)
    a = p.parse_args(argv)
    if not a.approved_public_metadata:
        p.error("explicit public metadata approval required")
    print(json.dumps(run_source_gate(a.annotations,a.sama_zip),sort_keys=True,
                     allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
