"""PER-80: host-only YOLOX Nano COCO-80 public bbox evaluation.

One frozen 80-head pretrained model, not an onboard multiclass adapter.
800 COCO validation JPEGs, disjoint by ID from the eight historical 5-class
cohorts and PER-P4's 300-image public benchmark. Ground truth is COCO bbox;
unmatched proposal != proven false physical presence, no private media/robot.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
import resource
import statistics
import time

from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint
from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, COCO_IDS, CocoCase, _official_jpeg,
    MAX_COCO_JSON_BYTES, MAX_DIMENSION,
    PHOTO_LICENSE_NAME, PHOTO_LICENSE_URL,
)
from microduck_companion.cata_yolox_categories import (
    CATEGORIES, MIN_SCORE, MODEL_SHA256, SIZE, _grid,
    prepare_image, validate_model_file,
)
from microduck_companion.yolox_attention_candidates import _iou

SEED = "kwipi-per80-20261104-v1"
MAX_PUBLIC_IMAGES = 800
TARGET_IMAGES_PER_CLASS = 8
COCO80_ID_ORDER = (
    1,2,3,4,5,6,7,8,9,10,11,13,14,15,16,17,18,19,20,21,22,23,
    24,25,27,28,31,32,33,34,35,36,37,38,39,40,41,42,43,44,46,
    47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,
    67,70,72,73,74,75,76,77,78,79,80,81,82,84,85,86,87,88,89,90,
)
# IDs from the public numeric artifact of completed PR #214,
# GitHub Actions run #41085096403, 300 COCO VAL JPEGs. No photos or PII.
P4_IDS = frozenset(map(int, """
632,1503,6614,10363,14226,14831,17115,17379,22192,22935,22969,
23666,30213,33759,35062,35326,37988,40083,40471,42296,44068,
44195,48396,50896,51008,51598,52565,53505,54593,55950,57238,
60090,60102,61171,61418,71451,76417,78032,78426,78915,80666,
82812,83172,84650,88951,90108,90155,91406,93353,93437,94751,
97585,99054,100624,106389,107087,109055,109118,111086,112626,
115245,121586,123585,125405,125952,126216,127494,127530,129054,
129322,130599,131131,132931,133645,134112,136355,136915,138492,
146358,149222,151629,153568,153797,154087,155291,157046,166563,
170278,171611,172856,173004,173008,174004,177489,178028,179285,
179898,180101,180792,181969,186296,187236,188296,188906,189806,
190236,193162,193674,194471,196141,197796,199771,199977,201025,
203488,205834,206218,206831,206994,209613,210099,221693,222235,
222991,223747,224337,229997,230819,232489,233825,236914,237517,
240023,243075,244411,245576,245915,249550,253386,255536,255664,
257624,261318,261706,263463,267300,273420,277197,279145,279278,
281409,281687,284106,286422,288391,289343,291861,292082,294162,
294783,295478,304817,305695,309484,311303,311928,323151,326541,
327701,329319,329447,332455,333069,338905,341681,344621,346968,
350148,356094,357459,357941,359219,360943,364636,365207,367195,
368294,368961,369081,369541,370813,370900,371042,372718,374551,
382030,384616,384670,385205,388215,392933,400367,402473,403122,
407298,407960,410510,412286,413395,416170,416256,416330,417085,
419601,419974,420069,420840,425390,427160,434996,438017,440184,
442822,445439,445658,447200,451693,455301,456394,457559,458255,
458410,459500,459757,460229,460494,462371,463174,464089,469067,
471789,474167,475779,476491,476787,479155,479732,480212,482319,
485027,488592,490125,491497,501023,501368,502229,504074,505169,
509403,509735,511398,512836,516038,516871,516916,519522,519688,
520301,526197,527427,529966,530061,530162,530975,534827,535156,
536343,536947,537802,543581,545826,546556,547502,548246,551815,
555005,556498,559547,560266,561889,564336,565469,568690,572303,
573094,579070,579321,581206,581615,581781
""".replace("\n", "").split(",")))
P4_IDS_SHA256 = "dbc87f64f56d8f988da4afe25883c1a1049f8221d481775b3c96c2aa1f4c931e"

# Identical six-license metadata gate to PER-P4's exploratory public study.
_GRANTS = {
    1: ("Attribution-NonCommercial-ShareAlike License",
        "http://creativecommons.org/licenses/by-nc-sa/2.0/"),
    2: ("Attribution-NonCommercial License",
        "http://creativecommons.org/licenses/by-nc/2.0/"),
    3: ("Attribution-NonCommercial-NoDerivs License",
        "http://creativecommons.org/licenses/by-nc-nd/2.0/"),
    4: (PHOTO_LICENSE_NAME, PHOTO_LICENSE_URL),
    5: ("Attribution-ShareAlike License",
        "http://creativecommons.org/licenses/by-sa/2.0/"),
    6: ("Attribution-NoDerivs License",
        "http://creativecommons.org/licenses/by-nd/2.0/"),
}
MAX_PRE_NMS = 160
MAX_PER_IMAGE = 80
NMS_IOU = 0.50
MATCH_IOU = 0.50


@dataclass(frozen=True)
class Truth:
    class_idx: int
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class Proposal:
    class_idx: int
    box: tuple[float, float, float, float]
    confidence: float


def check_class_order(data: dict) -> tuple[str, ...]:
    """COCO ID order must be the exact YOLOX head index order."""
    if type(data) is not dict or type(data.get("categories")) is not list:
        raise ValueError("missing COCO class taxonomy")
    entries = data["categories"]
    if (len(entries) != 80
            or any(type(c) is not dict or type(c.get("id")) is not int
                   or type(c.get("name")) is not str
                   for c in entries)):
        raise ValueError("not 80 official COCO categories")
    ordered = sorted(entries, key=lambda item: item["id"])
    if tuple(c["id"] for c in ordered) != COCO80_ID_ORDER:
        raise ValueError("COCO taxonomy is not the 80 ordered head indices")
    names = tuple(c["name"].replace(" ", "_") for c in ordered)
    if len(set(names)) != 80 or any(not x or not x.isascii() for x in names):
        raise ValueError("invalid or ambiguous category names")
    for name, idx in CATEGORIES.items():
        if names[idx] != name or ordered[idx]["id"] != COCO_IDS[name]:
            raise ValueError("five trusted COCO class anchors mismatch")
    return names


def _valid_license_ids(data: dict) -> frozenset[int]:
    grants = frozenset(
        item["id"] for item in data.get("licenses", [])
        if type(item) is dict and type(item.get("id")) is int
        and item["id"] in _GRANTS
        and item.get("name") == _GRANTS[item["id"]][0]
        and item.get("url") in (
            _GRANTS[item["id"]][1],
            _GRANTS[item["id"]][1].replace("http:", "https:"),
        )
    )
    if len(grants) != len(_GRANTS):
        raise ValueError("license metadata no longer matches reviewed six CC grants")
    return grants


def _box_from_annotation(ann: dict, width: int, height: int):
    rect = ann.get("bbox")
    if (type(rect) is not list or len(rect) != 4
            or any(type(x) not in (int, float) or not math.isfinite(x)
                   for x in rect)):
        return None
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    box = (
        max(0., float(x)), max(0., float(y)),
        min(float(width), float(x + w)), min(float(height), float(y + h)),
    )
    return box if box[2] > box[0] and box[3] > box[1] else None


def select_cases(data: dict, excluded_ids: frozenset[int], *,
                 image_count: int = MAX_PUBLIC_IMAGES,
                 per_class: int = TARGET_IMAGES_PER_CLASS):
    """Stratify using GT only, rare categories first; zero score lookups."""
    names = check_class_order(data)
    if (type(excluded_ids) is not frozenset
            or any(type(i) is not int or i < 0 for i in excluded_ids)
            or type(image_count) is not int or image_count < 80
            or image_count > MAX_PUBLIC_IMAGES
            or type(per_class) is not int or not 1 <= per_class <= 8):
        raise ValueError("invalid prospective cohort budget or class quota")
    licenses = _valid_license_ids(data)
    images = {}
    for image in data.get("images", []):
        if type(image) is not dict:
            raise ValueError("invalid COCO image metadata")
        ident, width, height = (
            image.get("id"), image.get("width"), image.get("height")
        )
        if (type(ident) is not int or type(width) is not int
                or type(height) is not int):
            raise ValueError("invalid image geometry metadata")
        if ident in excluded_ids or image.get("license") not in licenses:
            continue
        if (not 32 <= width <= MAX_DIMENSION
                or not 32 <= height <= MAX_DIMENSION
                or image.get("file_name") != f"{ident:012d}.jpg"
                or ident in images):
            raise ValueError("invalid/duplicate eligible image")
        images[ident] = (width, height)

    index = {cid: i for i, cid in enumerate(COCO80_ID_ORDER)}
    truth = defaultdict(list)
    forbidden = set()
    for ann in data.get("annotations", []):
        if type(ann) is not dict:
            raise ValueError("invalid annotation entry")
        ident = ann.get("image_id")
        if ident not in images:
            continue
        if ann.get("category_id") not in index:
            forbidden.add(ident)
            continue
        if ann.get("iscrowd") != 0:  # crowd regions not individually scorable
            forbidden.add(ident)
            continue
        width, height = images[ident]
        box = _box_from_annotation(ann, width, height)
        if box is None:
            forbidden.add(ident)
        else:
            truth[ident].append(Truth(index[ann["category_id"]], box))

    available = frozenset(images) - forbidden
    if len(available) < image_count:
        raise ValueError("too few licensed noncrowd COCO validation photos")
    category_images = tuple(
        frozenset(ident for ident in available
                  if any(t.class_idx == c for t in truth[ident]))
        for c in range(80)
    )
    missing = [names[i] for i, ids in enumerate(category_images) if not ids]
    if missing:
        raise ValueError("no official GT after exclusions for categories: "
                         + ",".join(missing))
    def ordered(ids):
        return sorted(ids, key=lambda ident: (
            sha256(f"{SEED}:{ident}".encode("ascii")).digest(), ident,
        ))

    selected: list[int] = []
    used: set[int] = set()
    # Select rarer categories first. A shared selected image counts for all
    # annotated categories; no instance or image is counted twice.
    for category in sorted(range(80), key=lambda c: (
            len(category_images[c]), c)):
        present = len(used & category_images[category])
        if present >= per_class:
            continue
        eligible = ordered(category_images[category] - used)
        for ident in eligible[:per_class - present]:
            selected.append(ident)
            used.add(ident)
    if len(selected) > image_count:
        raise ValueError("prospective class allocation exceeded image budget")
    selected.extend(ordered(available - used)[:image_count - len(selected)])
    if (len(selected) != image_count or len(set(selected)) != image_count
            or excluded_ids.intersection(selected)):
        raise ValueError("invalid or contaminated public cohort")
    coverage = tuple(
        sum(ident in category_images[c] for ident in selected)
        for c in range(80)
    )
    cases = tuple((
        CocoCase(ident, f"{ident:012d}.jpg", *images[ident], ()),
        tuple(truth[ident])
    ) for ident in selected)
    return names, cases, coverage, {
        "available_licensed_without_crowd": len(available),
        "excluded_crowd_or_bad_gt": len(forbidden),
    }


def _cohort_from_pinned_source(blob: bytes):
    if (type(blob) is not bytes
            or not 128 <= len(blob) <= MAX_COCO_JSON_BYTES
            or sha256(blob).hexdigest() != ANNOTATIONS_SHA256):
        raise ValueError("unpinned COCO validation annotations")
    if (len(P4_IDS) != 300
            or sha256(",".join(map(str, sorted(P4_IDS))).encode()
                      ).hexdigest() != P4_IDS_SHA256):
        raise ValueError("historical PER-P4 numeric exclusion roster changed")
    eighth, data, _, old = eighth_disjoint(blob)
    history = frozenset(old | {case.image_id for case in eighth} | P4_IDS)
    if len(history) != 432:
        raise ValueError("historical COCO cohort collision or malformed IDs")
    names, cases, coverage, inventory = select_cases(data, history)
    digest = sha256(",".join(str(case.image_id) for case, _ in cases
                             ).encode()).hexdigest()
    return names, cases, coverage, inventory, digest


def decode_all_classes(raw, *, width: int, height: int) -> tuple[Proposal, ...]:
    """The existing YOLOX per-class 0.25 joint score / 0.50 NMS for all 80.

    Experimental display/benchmark only, intentionally not F1 or OEM output.
    """
    import numpy as np
    if (type(width) is not int or type(height) is not int
            or not 32 <= width <= MAX_DIMENSION
            or not 32 <= height <= MAX_DIMENSION):
        raise ValueError("invalid original image geometry")
    a = np.asarray(raw)
    if (a.shape != (1, 3549, 85)
            or not np.issubdtype(a.dtype, np.floating)
            or not np.isfinite(a).all()
            or np.any(a[..., 4:] < 0) or np.any(a[..., 4:] > 1)):
        raise ValueError("invalid raw 80-class YOLOX head")
    values = a[0].astype(np.float32, copy=False)
    grid, stride = _grid()
    with np.errstate(over="ignore", invalid="ignore"):
        center = (values[:, :2] + grid) * stride
        span = np.exp(values[:, 2:4]) * stride
    if not np.isfinite(center).all() or not np.isfinite(span).all():
        raise ValueError("nonfinite decoded YOLOX box")
    scale = min(SIZE / width, SIZE / height)
    rw, rh = max(1, round(width * scale)), max(1, round(height * scale))
    xs, ys = width / rw, height / rh
    coords = (
        np.clip((center[:, 0] - span[:, 0]/2) * xs, 0, width),
        np.clip((center[:, 1] - span[:, 1]/2) * ys, 0, height),
        np.clip((center[:, 0] + span[:, 0]/2) * xs, 0, width),
        np.clip((center[:, 1] + span[:, 1]/2) * ys, 0, height),
    )
    valid = (coords[2] > coords[0] + 1e-6) & (
        coords[3] > coords[1] + 1e-6)
    boxes: list[Proposal] = []
    for class_idx in range(80):
        confidence = values[:, 4] * values[:, 5 + class_idx]
        cand = np.flatnonzero(valid & (confidence >= MIN_SCORE))
        order = sorted(cand.tolist(), key=lambda i: (
            -float(confidence[i]), i))[:MAX_PRE_NMS]
        accepted: list[Proposal] = []
        for i in order:
            box = tuple(float(v[i]) for v in coords)
            if all(_iou(box, old.box) <= NMS_IOU for old in accepted):
                accepted.append(Proposal(
                    class_idx, box, float(confidence[i]),
                ))
            if len(accepted) >= MAX_PER_IMAGE:
                break
        boxes.extend(accepted)
    return tuple(sorted(boxes, key=lambda p: (
        -p.confidence, p.class_idx, p.box
    ))[:MAX_PER_IMAGE])


def _stats_for_class(
    gt: tuple[Truth, ...], pred: tuple[Proposal, ...], class_idx: int,
):
    truth = tuple(x.box for x in gt if x.class_idx == class_idx)
    proposed = tuple(x for x in pred if x.class_idx == class_idx)
    matched = set()
    tp = 0
    for p in proposed:
        options = [(_iou(p.box, box), i)
                   for i, box in enumerate(truth) if i not in matched]
        best, idx = max(options, default=(0., -1))
        if best >= MATCH_IOU:
            matched.add(idx)
            tp += 1
    return len(truth), len(proposed), tp


def evaluate_report(names, rows, *, coverage):
    """Aggregate all 80 categories; never invent true negatives or official mAP."""
    if (len(names) != 80 or len(coverage) != 80 or not rows
            or any(len(p) != 2 for p in rows)):
        raise ValueError("invalid 80-category benchmark rows")
    support = [0]*80
    proposals = [0]*80
    matched = [0]*80
    for truth, predicted in rows:
        if (type(truth) is not tuple or type(predicted) is not tuple):
            raise ValueError("not immutable scored rows")
        for category in range(80):
            n_gt, n_pred, tp = _stats_for_class(
                truth, predicted, category,
            )
            support[category] += n_gt
            proposals[category] += n_pred
            matched[category] += tp
    by_class = {}
    for i, label in enumerate(names):
        by_class[label] = {
            "gt_instances": support[i],
            "proposals": proposals[i],
            "matched_iou50": matched[i],
            "missed_gt": support[i] - matched[i],
            "unmatched_proposals_not_proven_false": proposals[i] - matched[i],
            "recall_iou50": (round(matched[i] / support[i], 6)
                             if support[i] else None),
            "selected_photos_with_this_gt": coverage[i],
            "class_coverage_status": (
                "unsupported" if support[i] == 0 else
                "low_support" if coverage[i] < TARGET_IMAGES_PER_CLASS else
                "measured_sample_only"
            ),
        }
    tp_total, gt_total = sum(matched), sum(support)
    supported = [matched[i]/support[i] for i in range(80) if support[i]]
    return {
        "class_count_model": 80,
        "gt_classes_represented": len(supported),
        "gt_classes_at_least_8_photos": sum(x >= 8 for x in coverage),
        "gt_instances": gt_total,
        "matched_boxes_iou50": tp_total,
        "unmatched_proposals_not_proven_false": (
            sum(proposals) - tp_total
        ),
        "micro_recall_iou50": round(tp_total / gt_total, 6) if gt_total else None,
        "macro_recall_iou50_present_classes": round(
            statistics.mean(supported), 6
        ) if supported else None,
        "categories": by_class,
        "official_coco_map_80": None,
        "physically_verified_absent_images": 0,
        "all_80_category_safe_use": False,
    }


def run(annotations: Path, *, model_path: Path | None, validate_only: bool):
    if (not isinstance(annotations, Path) or annotations.is_symlink()
            or not annotations.is_file()
            or not 128 <= annotations.stat().st_size <= MAX_COCO_JSON_BYTES):
        raise ValueError("valid frozen official COCO annotations required")
    blob = annotations.read_bytes()
    names, cases, coverage, inventory, selection_sha = (
        _cohort_from_pinned_source(blob)
    )
    base = {
        "status": ("SOURCE_GATE_PASS_NO_INFERENCE" if validate_only
                   else "HOST_PUBLIC_INFERENCE_COMPLETED"),
        "public_photos_selected": len(cases),
        "gt_class_names_count": len(names),
        "gt_class_names": list(names),
        "photos_with_target_gt_by_category": dict(zip(names, coverage)),
        "excluded_previous_public_cohorts": 432,
        "coco_source_sha256": ANNOTATIONS_SHA256,
        "prior_300_id_sha256": P4_IDS_SHA256,
        "roster_sha256": selection_sha,
        "model_sha256": MODEL_SHA256,
        "threshold_unchanged": MIN_SCORE,
        "iou_threshold": MATCH_IOU,
        "selection": inventory,
        "camera_height_verified": False,
        "independent_physical_scenes_verified": False,
        "individual_photo_rights_verified": False,
        "no_private_photos": True,
        "no_automated_motor_or_model_install": True,
        "robot_rknn_validated": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
        "qwen_calls": 0,
        "f1_category_vocabulary_changed": False,
    }
    if validate_only:
        return base
    if model_path is None:
        raise ValueError("provide approved YOLOX ONNX model for inference")
    validate_model_file(model_path)

    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=opts,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1
            or len(session.get_outputs()) != 1
            or (session.get_inputs()[0].name, session.get_inputs()[0].shape)
            != ("images", [1, 3, SIZE, SIZE])
            or (session.get_outputs()[0].name, session.get_outputs()[0].shape)
            != ("output", [1, 3549, 85])):
        raise ValueError("wrong YOLOX ONNX input or output contract")

    scored = []
    timings = []
    image_hashes = []
    for case, gt in cases:
        # _official_jpeg uses the original trusted fixed COCO S3 host,
        # checks 2.5MB cap, actual dimensions and EXIF without saving bytes.
        jpeg = _official_jpeg(case)
        image_hashes.append(sha256(jpeg).hexdigest())
        inp = prepare_image(jpeg, mode="original")
        t0 = time.perf_counter()
        output = session.run(None, {"images": inp})[0]
        timings.append(1000*(time.perf_counter()-t0))
        predicted = decode_all_classes(
            output, width=case.width, height=case.height,
        )
        scored.append((gt, predicted))
    if len(set(image_hashes)) != len(image_hashes):
        raise ValueError("duplicate JPEG bytes within selected public cohort")
    result = evaluate_report(names, scored, coverage=coverage)
    result.update(base)
    result.update({
        "inference_on_real_public_pixels": True,
        "actual_jpeg_sha256_aggregate": sha256(
            ",".join(image_hashes).encode()
        ).hexdigest(),
        "median_host_onnx_ms": round(statistics.median(timings), 3),
        "p95_host_onnx_ms": round(
            sorted(timings)[math.ceil(len(timings)*0.95)-1], 3
        ),
        "host_peak_rss_kib_process": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "model_tuned_or_retrained": False,
    })
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-media", action="store_true")
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--annotations", required=True, type=Path)
    p.add_argument("--model", type=Path)
    args = p.parse_args(argv)
    if not args.approved_public_media:
        p.error("operator must approve public noncommercial exploratory evaluation")
    if not args.validate_only and not args.model:
        p.error("the fixed YOLOX model is required outside preflight")
    print(json.dumps(run(
        args.annotations, model_path=args.model,
        validate_only=args.validate_only,
    ), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
