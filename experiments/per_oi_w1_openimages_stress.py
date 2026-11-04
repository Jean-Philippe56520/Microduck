"""PER-OI-W1: prospective independent Open Images host-only stress cohort.

No model tuning, private media, robot control, database writes or promotion.
The fixed PER-80 COCO cohort is NEVER re-inferred by this script.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
from io import StringIO
import json
import math
from pathlib import Path
import resource
import statistics
import time

from experiments.cata2d_openimages_bbox_public import (
    _load_sources, _licensed_ids, _bool_votes, _boxes, _geometry,
    _source_bytes, PublicCase,
)
from experiments.per80_yolox_coco_public import decode_all_classes
from microduck_companion.yolox_attention_candidates import _iou
from microduck_companion.cata2c_openimages_human_labels import (
    _official_jpeg, IMAGE_ID_PATTERN, select_human_verified_cases,
)
from microduck_companion.cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, prepare_image, validate_model_file,
)
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError

SEED = "kwipi-per-oi-w1-prospective-20261104"
TARGETS = {"book": ("Book", 73), "bottle": ("Bottle", 39),
           "chair": ("Chair", 56)}
PER_LABEL = 8
NMS_IOU = 0.50
MATCH_IOU = 0.50


def target_mids(raw: bytes) -> dict[str, str]:
    """Exact official MID -> target, with no inferred semantic synonym."""
    if type(raw) is not bytes or not 16 <= len(raw) <= 150_000:
        raise PhotoBaselineError("invalid bounded class metadata")
    lookup: dict[str, set[str]] = {c: set() for c in TARGETS}
    seen_mids: set[str] = set()
    try:
        for row in csv.reader(StringIO(raw.decode("utf-8-sig")), strict=True):
            if row == ["LabelName", "DisplayName"]:
                continue
            if len(row) != 2 or not row[0].startswith("/m/"):
                raise PhotoBaselineError("malformed official class label")
            if row[0] in seen_mids:
                raise PhotoBaselineError("duplicate official MID")
            seen_mids.add(row[0])
            for cat, (name, _) in TARGETS.items():
                if row[1] == name:
                    lookup[cat].add(row[0])
    except (UnicodeError, csv.Error, ValueError) as exc:
        raise PhotoBaselineError("invalid official class metadata") from exc
    if any(len(ids) != 1 for ids in lookup.values()):
        raise PhotoBaselineError("missing or ambiguous target MID")
    result = {next(iter(ids)): cat for cat, ids in lookup.items()}
    if len(result) != len(TARGETS):
        raise PhotoBaselineError("reused official MID")
    return result


def choose_cases(classes: bytes, metadata: bytes, votes: bytes, boxes: bytes,
                 *, excluded_ids: frozenset[str], count: int = PER_LABEL):
    """Ground truth only, deterministic before reading model/image pixels."""
    if (type(count) is not int or count != PER_LABEL
            or type(excluded_ids) is not frozenset
            or any(type(i) is not str or not IMAGE_ID_PATTERN.fullmatch(i)
                   for i in excluded_ids)):
        raise PhotoBaselineError("invalid preregistered selection parameters")
    mids = target_mids(classes)
    licensed = _licensed_ids(metadata)
    truth = _bool_votes(votes, mids, licensed)
    boxes_by_key = _boxes(boxes, mids, licensed)
    pools = {}
    for cat in TARGETS:
        for presence in (True, False):
            candidates = []
            for (ident, category), values in truth.items():
                if (category != cat or ident in excluded_ids
                        or values != {presence}):
                    continue
                refs = boxes_by_key.get((ident, cat), ())
                if (presence and not refs) or (not presence and refs):
                    continue
                candidates.append(ident)
            pools[(cat, presence)] = sorted(
                candidates, key=lambda ident: (
                    sha256(f"{SEED}/{cat}/{int(presence)}/{ident}".encode()).digest(),
                    ident,
                ))
    selected = []
    taken = set(excluded_ids)
    for cat in TARGETS:
        for presence in (True, False):
            free = [i for i in pools[(cat, presence)] if i not in taken]
            if len(free) < count:
                raise PhotoBaselineError(
                    f"STOP_SOURCE class={cat} human_presence={int(presence)} "
                    f"available={len(free)} required={count}"
                )
            for ident in free[:count]:
                selected.append(PublicCase(
                    ident, cat, presence,
                    tuple(boxes_by_key.get((ident, cat), ())),
                ))
                taken.add(ident)
    if (len(selected) != 2*len(TARGETS)*count
            or len({x.image_id for x in selected}) != len(selected)
            or {x.image_id for x in selected} & excluded_ids):
        raise PhotoBaselineError("non-disjoint prospective cohort")
    return tuple(selected)


def _matched(case: PublicCase, predicted: tuple, width: int, height: int):
    """One-to-one correct-class localization; other classes remain separate."""
    _, idx = TARGETS[case.category]
    truth = tuple((
        b.xyxy_normalized[0]*width, b.xyxy_normalized[1]*height,
        b.xyxy_normalized[2]*width, b.xyxy_normalized[3]*height,
    ) for b in case.boxes)
    matched = set()
    proposals = [p for p in predicted if p.class_idx == idx]
    for p in sorted(proposals, key=lambda x: -x.confidence):
        remaining = [(_iou(p.box,b), i)
                     for i,b in enumerate(truth) if i not in matched]
        score, key = max(remaining, default=(0.0, -1))
        if score >= MATCH_IOU:
            matched.add(key)
    return len(proposals), len(matched)


def benchmark(*, classes: Path, metadata: Path, votes: Path, boxes: Path,
              model: Path | None, validate_only: bool):
    sources = (_source_bytes(classes, 150_000),
               _source_bytes(metadata, 45_000_000),
               _source_bytes(votes, 55_000_000),
               _source_bytes(boxes, 70_000_000))
    # Reuse the frozen Cat-A2c and Cat-A2d source hashes/selection;
    # this rejects altered sources instead of silently choosing replacements.
    old_cases, digests, _ = _load_sources(classes, metadata, votes, boxes)
    old_c = select_human_verified_cases(*sources[:3])
    excluded = frozenset([x.image_id for x in old_c] +
                         [x.image_id for x in old_cases])
    if len(excluded) != 240:
        raise PhotoBaselineError("historical Open Images exclusion mismatch")
    cohort = choose_cases(*sources, excluded_ids=excluded)
    roster_sha = sha256("|".join(
        f"{c.image_id}/{c.category}/{int(c.present)}" for c in cohort
    ).encode()).hexdigest()
    base = dict(
        experiment="PER-OI-W1 frozen three-class independent OI host-only",
        status="STOP_SOURCE" if not validate_only else "SOURCE_GATE_PASS_NO_INFERENCE",
        public_images_selected=len(cohort),
        previous_openimages_ids_excluded=240,
        selection_sha256=roster_sha, source_sha256=digests,
        positive_negative_per_class=PER_LABEL,
        targets=list(TARGETS),
        model_sha256=MODEL_SHA256,
        no_private_photos=True,
        camera_height_verified=False,
        real_world_presence_verified=False,
        robot_rknn_validated=False,
        motor_commands=0, sqlite_writes=0, qwen_calls=0,
        promotion=False, no_media_or_ids_published=True,
        threshold=MIN_SCORE, nms_iou=NMS_IOU, match_iou=MATCH_IOU,
    )
    if validate_only:
        return base
    if model is None:
        raise PhotoBaselineError("model required for real public inference")
    validate_model_file(model)
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model),sess_options=options,
                                   providers=["CPUExecutionProvider"])
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_inputs()[0].shape != [1,3,SIZE,SIZE]
            or session.get_outputs()[0].shape != [1,3549,85]):
        raise PhotoBaselineError("unexpected YOLOX runtime tensor contract")
    rows = {cat: dict(positive_images=0,negative_images=0,
                      proposed_on_positive=0,proposed_on_verified_negative=0,
                      gt_boxes=0,matched_iou50=0,
                      other_class_proposals=0,depicted_gt=0)
            for cat in TARGETS}
    times = []
    pixel_hashes = []
    distinct = set()
    for case in cohort:
        jpg = _official_jpeg(case.image_id)
        digest = sha256(jpg).hexdigest()
        if digest in distinct:
            raise PhotoBaselineError("duplicate public JPEG bytes")
        distinct.add(digest)
        pixel_hashes.append(digest)
        w,h = _geometry(jpg)
        image = prepare_image(jpg,mode="original")
        before = time.perf_counter()
        out = session.run(None,{"images":image})[0]
        times.append((time.perf_counter()-before)*1000)
        predicted = decode_all_classes(out,width=w,height=h)
        proposed,matched = _matched(case,predicted,w,h)
        row = rows[case.category]
        row["other_class_proposals"] += sum(
            p.class_idx != TARGETS[case.category][1] for p in predicted
        )
        if case.present:
            row["positive_images"] += 1
            row["proposed_on_positive"] += bool(proposed)
            row["gt_boxes"] += len(case.boxes)
            row["matched_iou50"] += matched
            row["depicted_gt"] += sum(x.depiction == "1" for x in case.boxes)
        else:
            row["negative_images"] += 1
            row["proposed_on_verified_negative"] += bool(proposed)
    safe = True
    for cat,row in rows.items():
        if row["positive_images"] != PER_LABEL or row["negative_images"] != PER_LABEL:
            raise PhotoBaselineError("invalid denominators after inference")
        row["image_sensitivity"] = round(row["proposed_on_positive"]/PER_LABEL,6)
        row["negative_proposal_rate"] = round(row["proposed_on_verified_negative"]/PER_LABEL,6)
        row["iou50_recall"] = round(row["matched_iou50"]/row["gt_boxes"],6)
        safe &= (row["image_sensitivity"] >= .70 and
                 row["negative_proposal_rate"] <= .10 and
                 row["iou50_recall"] >= .50)
    base.update(status="HOST_PUBLIC_INFERENCE_COMPLETED",
                classwise_results=rows,
                decision="HOST_METRIC_GATE_ONLY_NO_PROMOTION" if safe else "STOP_PROMOTION",
                image_sha256_aggregate=sha256("|".join(pixel_hashes).encode()).hexdigest(),
                p50_host_inference_ms=round(statistics.median(times),3),
                p95_host_inference_ms=round(sorted(times)[math.ceil(.95*len(times))-1],3),
                host_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                inference_on_real_public_pixels=True)
    return base


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-public-media",action="store_true")
    parser.add_argument("--validate-only",action="store_true")
    for key in ("classes","metadata","votes","boxes"):
        parser.add_argument("--"+key,required=True,type=Path)
    parser.add_argument("--model",type=Path)
    args=parser.parse_args(argv)
    if not args.approved_public_media:
        parser.error("public research confirmation required")
    if not args.validate_only and args.model is None:
        parser.error("--model required")
    print(json.dumps(benchmark(classes=args.classes,metadata=args.metadata,
              votes=args.votes,boxes=args.boxes,model=args.model,
              validate_only=args.validate_only),sort_keys=True,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
