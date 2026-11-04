"""PER-YOLOX-SM-0: public COCO/Sama GT gate and Rockchip three-head model preflight.

Host-only research, not a detector installed in mediad or on RK3566.
Never reuse the 1316 consumed COCO val IDs, publish pixels, claim causal effect,
or infer physical robot performance from a PC smoke test.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import resource
import statistics
import time

from experiments.per80_yolox_coco_public import (
    COCO80_ID_ORDER, P4_IDS, Proposal, _cohort_from_pinned_source,
    _valid_license_ids,
)
from experiments.per_qual1_sama_gt_gate import (
    FROZEN_COHORT_SHA256, SEED_C1, SAMPLES_PER_CLASS, TARGETS,
    SourceGateError, _frozen_sha256, _images, _paired_iou50,
    choose_paired_cohort, unpack_sama_archive, validate_dual_class_map,
)
from experiments.per_qual1c1_new42_source import (
    FROZEN_NEW_COHORT_SHA256, source_gate,
)
from experiments.vis_att2_eighth_coco_category_vs_region import eighth_disjoint

ROCKCHIP_PIN = "837db8e992815ff8647eadb709f07067f4bc3a71"
MODEL_URLS = {
    "s": "https://ftrg.zbox.filez.com/v2/delivery/data/95f00b0fc900458ba134f8b180b3f7a1/examples/yolox/yolox_s.onnx",
    "m": "https://ftrg.zbox.filez.com/v2/delivery/data/95f00b0fc900458ba134f8b180b3f7a1/examples/yolox/yolox_m.onnx",
}
# Filled only AFTER the vendor downloads and numerical ABI smoke pass;
# until then benchmark mode refuses before fetching any public JPEG.
FROZEN_VENDOR_SHA256 = {"s": None, "m": None}
EXPECTED_HEADS = {(1, 85, 80, 80), (1, 85, 40, 40), (1, 85, 20, 20)}
N_IMAGES = 42
HISTORICAL = 1316
SIZE = 640
SCORE_THRESHOLD = 0.25
NMS_THRESHOLD = 0.45
MAX_DETECTIONS = 80
MAX_ABOVE_THRESHOLD = 1500
LICENSE_ID = 4  # COCO per-photo CC BY 2.0, not all six upstream licenses


def combine_exclusions(historical_1232: frozenset[int],
                       consumed_pr301: tuple,
                       consumed_pr304: tuple) -> frozenset[int]:
    """Fail closed on any overlap, incorrect count or repeated previous ID."""
    if (type(historical_1232) is not frozenset or len(historical_1232) != 1232
            or type(consumed_pr301) is not tuple or len(consumed_pr301) != 42
            or type(consumed_pr304) is not tuple or len(consumed_pr304) != 42):
        raise SourceGateError("STOP_SOURCE: historical cohort lengths invalid")
    try:
        a = [ident for ident, _ in consumed_pr301]
        b = [ident for ident, _ in consumed_pr304]
    except (TypeError, ValueError) as exc:
        raise SourceGateError("STOP_SOURCE: invalid old roster") from exc
    if (any(type(i) is not int or i < 0 for i in historical_1232)
            or any(type(i) is not int or i < 0 for i in a + b)):
        raise SourceGateError("STOP_SOURCE: bad historical ID")
    new = frozenset(historical_1232 | set(a) | set(b))
    if (len(new) != HISTORICAL or len(set(a)) != 42 or len(set(b)) != 42):
        raise SourceGateError("STOP_SOURCE: overlapping or missing consumed photos")
    return new


def source_and_truth(annotations: Path, sama_zip: Path):
    """Reconstruct all 1316 USED IDs before selecting another 42 using GT only."""
    old = source_gate(annotations, sama_zip)  # verifies COCO/Sama and old 1274
    if (old["status"] != "NEW_SOURCE_COHORT_SELECTED_NO_INFERENCE"
            or old["total_coco_ids_excluded"] != 1274
            or old["new_cohort_sha256"] != FROZEN_NEW_COHORT_SHA256):
        raise SourceGateError("STOP_SOURCE: old source gate drift")
    blob = annotations.read_bytes()
    names, previous_800, _, _, _ = _cohort_from_pinned_source(blob)
    eighth, coco, _, first = eighth_disjoint(blob)
    historical_1232 = frozenset(
        first | {c.image_id for c in eighth} | P4_IDS |
        {case.image_id for case, _ in previous_800}
    )
    if len(historical_1232) != 1232:
        raise SourceGateError("STOP_SOURCE: 1232 legacy exclusions drift")
    sama = unpack_sama_archive(sama_zip.read_bytes())
    previous_rights = _valid_license_ids(coco)
    earlier_42, _, _, _, _ = choose_paired_cohort(
        coco, sama, old_ids=historical_1232,
        allowed_license_ids=previous_rights,
    )
    _frozen_sha256(
        "|".join(f"{i}/{c}" for i, c in earlier_42).encode(),
        FROZEN_COHORT_SHA256, "previous 42 photos already consumed",
    )
    previous_1274 = frozenset(historical_1232 | {i for i, _ in earlier_42})
    newest_42, _, _, _, _ = choose_paired_cohort(
        coco, sama, old_ids=previous_1274,
        allowed_license_ids=previous_rights, selection_seed=SEED_C1,
    )
    _frozen_sha256(
        "|".join(f"{i}/{c}" for i, c in newest_42).encode(),
        FROZEN_NEW_COHORT_SHA256, "second 42 photos already consumed",
    )
    excluded = combine_exclusions(historical_1232, earlier_42, newest_42)
    # Restrict NEW images to CC BY 2.0. Do not retroactively alter the
    # historical rosters, which used six declared COCO licenses.
    allowed = _valid_license_ids(coco)
    if LICENSE_ID not in allowed:
        raise SourceGateError("STOP_RIGHTS: missing CC BY photo license")
    cases, official_ids, coco_gt, sama_gt, info = choose_paired_cohort(
        coco, sama, old_ids=excluded,
        allowed_license_ids=frozenset({LICENSE_ID}),
        selection_seed=SEED_C1,
    )
    maps = validate_dual_class_map(names, official_ids, COCO80_ID_ORDER)
    if (len(cases) != N_IMAGES
            or len({i for i, _ in cases}) != N_IMAGES
            or any(i in excluded for i, _ in cases)
            or {c for _, c in cases} != set(TARGETS)):
        raise SourceGateError("STOP_SOURCE: contaminated prospective cohort")
    for label in TARGETS:
        assigned = [i for i, c in cases if c == label]
        official_id = maps[label]["coco_category_id"]
        if (len(assigned) != SAMPLES_PER_CLASS
                or any(not coco_gt.get((i, official_id))
                       or not sama_gt.get((i, official_id)) for i in assigned)):
            raise SourceGateError("STOP_SCHEMA: missing paired positive GT")
    images = _images(coco)
    if any(images[i][3] != LICENSE_ID for i, _ in cases):
        raise SourceGateError("STOP_RIGHTS: unapproved image license")
    roster_hash = sha256(
        "|".join(f"{i}/{c}" for i, c in cases).encode()).hexdigest()
    return cases, maps, coco_gt, sama_gt, images, {
        "old_coco_val_ids_excluded": len(excluded),
        "new_public_photos": len(cases),
        "new_cohort_sha256": roster_hash,
        "coco_annotations_sha256": old["coco_source_sha256"],
        "sama_annotations_sha256": old["sama_source_sha256"],
        "photo_license_id": LICENSE_ID,
        "target_categories": list(TARGETS),
        "assigned_photos_per_category": SAMPLES_PER_CLASS,
        "source_inventory": {"eligible_without_bad_gt": info["source_eligible_images"]},
        "gt_independent_from_model_predictions": True,
        "gt_sources_statistically_independent": False,
        "viewpoint_height": "unknown",
        "physically_verified_negatives": 0,
        "media_bytes_published": 0,
        "identity_or_tracking_verified": False,
        "robot_rknn_validated": False,
        "model_promoted": False,
        "sqlite_writes": 0,
        "motor_commands": 0,
        "qwen_calls": 0,
    }


def validate_heads(heads) -> dict[int, object]:
    """Exactly three genuine Rockchip YOLOX heads, never Nano flat output."""
    import numpy as np
    if type(heads) not in (tuple, list) or len(heads) != 3:
        raise ValueError("STOP_MODEL: expected exactly 3 YOLOX heads")
    result = {}
    for head in heads:
        a = np.asarray(head)
        if (tuple(a.shape) not in EXPECTED_HEADS
                or not np.issubdtype(a.dtype, np.floating)
                or not np.isfinite(a).all()
                or np.any(a[:, 4:] < 0)
                or np.any(a[:, 4:] > 1)):
            raise ValueError("STOP_MODEL: invalid 3-head shape or scores")
        h = a.shape[-1]
        if h in result:
            raise ValueError("STOP_MODEL: repeated scale")
        result[h] = a
    if set(result) != {80, 40, 20}:
        raise ValueError("STOP_MODEL: missing output level")
    return result


def _iou(a, b) -> float:
    xx0, yy0 = max(a[0], b[0]), max(a[1], b[1])
    xx1, yy1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0., xx1 - xx0) * max(0., yy1 - yy0)
    area_a = max(0., a[2]-a[0]) * max(0., a[3]-a[1])
    area_b = max(0., b[2]-b[0]) * max(0., b[3]-b[1])
    d = area_a + area_b - intersection
    return intersection / d if d > 0 else 0.


def decode_vendor_heads(heads, *, width: int, height: int) -> tuple[Proposal, ...]:
    """Rockchip three-grid decoding + global NMS; oracle GT never enters."""
    import numpy as np
    if (type(width) is not int or type(height) is not int
            or not 32 <= width <= 4096 or not 32 <= height <= 4096):
        raise ValueError("STOP_GEOMETRY: invalid source image")
    scales = validate_heads(heads)
    ratio = min(SIZE / width, SIZE / height)
    new_w, new_h = round(width*ratio), round(height*ratio)
    pad_w, pad_h = (SIZE-new_w)/2, (SIZE-new_h)/2
    candidates = []
    for h in (80, 40, 20):
        a = scales[h][0].transpose(1, 2, 0)
        joint = a[:, :, 4, None] * a[:, :, 5:]
        class_idx = joint.argmax(axis=2)
        confidence = joint.max(axis=2)
        coords = np.argwhere(confidence >= SCORE_THRESHOLD)
        if len(coords) > MAX_ABOVE_THRESHOLD:
            raise ValueError("STOP_MODEL: too many raw candidates")
        stride = SIZE // h
        for y, x in coords:
            row = a[y, x]
            if not -20 <= float(row[2]) <= 20 or not -20 <= float(row[3]) <= 20:
                raise ValueError("STOP_MODEL: invalid exp box span")
            cx, cy = (float(row[0])+int(x))*stride, (float(row[1])+int(y))*stride
            bw, bh = math.exp(float(row[2]))*stride, math.exp(float(row[3]))*stride
            box = (cx-bw/2, cy-bh/2, cx+bw/2, cy+bh/2)
            if not all(math.isfinite(v) for v in box):
                raise ValueError("STOP_MODEL: nonfinite box")
            candidates.append((float(confidence[y,x]), int(class_idx[y,x]), box))
    if len(candidates) > MAX_ABOVE_THRESHOLD:
        raise ValueError("STOP_MODEL: too many proposals")
    # Vendor example uses class-agnostic NMS after argmax. No threshold tuning.
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    kept = []
    for confidence, class_idx, box in candidates:
        if any(_iou(box, item[2]) > NMS_THRESHOLD for item in kept):
            continue
        kept.append((confidence, class_idx, box))
        if len(kept) >= MAX_DETECTIONS:
            break
    predictions = []
    for confidence, class_idx, box in kept:
        x0, y0, x1, y1 = (
            max(0., min(float(width), (box[0]-pad_w)/ratio)),
            max(0., min(float(height), (box[1]-pad_h)/ratio)),
            max(0., min(float(width), (box[2]-pad_w)/ratio)),
            max(0., min(float(height), (box[3]-pad_h)/ratio)),
        )
        if x1 > x0 and y1 > y0:
            predictions.append(Proposal(class_idx, (x0,y0,x1,y1), confidence))
    return tuple(predictions)


def prepare_vendor(jpeg: bytes, *, width: int, height: int):
    """Host equivalent of Rockchip centered black cv2 letterbox and RGB CHW."""
    import cv2
    import numpy as np
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (height, width):
        raise SourceGateError("STOP_SOURCE: JPEG decode/geometry drift")
    ratio = min(SIZE/height, SIZE/width)
    new_w, new_h = round(width*ratio), round(height*ratio)
    resized = cv2.resize(image, (new_w,new_h), interpolation=cv2.INTER_LINEAR)
    dw, dh = (SIZE-new_w)/2, (SIZE-new_h)/2
    left, right = round(dw-0.1), round(dw+0.1)
    top, bottom = round(dh-0.1), round(dh+0.1)
    padded = cv2.copyMakeBorder(
        resized,top,bottom,left,right,cv2.BORDER_CONSTANT,value=(0,0,0))
    if padded.shape != (SIZE,SIZE,3):
        raise SourceGateError("STOP_SOURCE: letterbox shape changed")
    rgb = cv2.cvtColor(padded,cv2.COLOR_BGR2RGB)
    return np.ascontiguousarray(rgb.transpose(2,0,1)[None],dtype=np.float32)


def open_vendor_models(model_s: Path, model_m: Path, *, require_frozen: bool):
    import onnxruntime as ort
    handles, proofs = {}, {}
    for name, path in (("s",model_s),("m",model_m)):
        if (not isinstance(path,Path) or path.is_symlink()
                or not path.is_file()
                or not 20_000_000 <= path.stat().st_size <= 150_000_000):
            raise SourceGateError("STOP_MODEL: vendor ONNX unavailable/unsafe")
        digest=sha256(path.read_bytes()).hexdigest()
        if require_frozen and digest != FROZEN_VENDOR_SHA256[name]:
            raise SourceGateError("STOP_MODEL: vendor ONNX SHA not preapproved")
        opts=ort.SessionOptions()
        opts.intra_op_num_threads=opts.inter_op_num_threads=1
        session=ort.InferenceSession(
            str(path),sess_options=opts,providers=["CPUExecutionProvider"])
        inputs=session.get_inputs()
        outputs=session.get_outputs()
        if (len(inputs)!=1 or inputs[0].type!="tensor(float)"
                or inputs[0].shape != [1,3,SIZE,SIZE]
                or len(outputs)!=3 or
                {tuple(out.shape) for out in outputs} != EXPECTED_HEADS
                or any(out.type!="tensor(float)" for out in outputs)):
            raise SourceGateError("STOP_MODEL: ONNX ABI not Rockchip 3-head")
        handles[name]=(session,inputs[0].name)
        proofs[name]={"sha256":digest, "bytes":path.stat().st_size,
                      "inputs":[1,3,SIZE,SIZE],
                      "outputs":sorted([list(out.shape) for out in outputs])}
    return handles, proofs


def score_same_images(cases, class_maps, coco_gt, sama_gt,
                      predictions: dict) -> dict:
    """One-to-one IoU50 against official category IDs, never head indices."""
    if (type(cases) is not tuple or len(cases)!=N_IMAGES
            or type(predictions) is not dict
            or set(predictions)!={i for i,_ in cases}
            or set(class_maps)!=set(TARGETS)):
        raise SourceGateError("STOP_SCHEMA: incomplete paired scoring")
    result={}
    for name in TARGETS:
        official_id=class_maps[name]["coco_category_id"]
        head_idx=class_maps[name]["yolox_head_idx"]
        if COCO80_ID_ORDER[head_idx]!=official_id:
            raise SourceGateError("STOP_SCHEMA: official GT and YOLOX class indices swapped")
        row=dict(gt_coco_boxes=0,gt_sama_boxes=0,proposals=0,
                 matched_coco_iou50=0,matched_sama_iou50=0,
                 unmatched_coco_not_proven_false=0,
                 unmatched_sama_not_proven_false=0,assigned=0)
        for ident,allocated in cases:
            pred=predictions[ident]
            if (type(pred) is not tuple or len(pred)>MAX_DETECTIONS
                    or any(not isinstance(p,Proposal) for p in pred)):
                raise SourceGateError("STOP_MODEL: invalid result set")
            boxes=tuple(p.box for p in pred if p.class_idx==head_idx)
            ca=tuple(coco_gt.get((ident,official_id),()))
            sa=tuple(sama_gt.get((ident,official_id),()))
            if allocated==name and (not ca or not sa):
                raise SourceGateError("STOP_SCHEMA: allocated positives lack GT")
            ctp,stp=_paired_iou50(boxes,ca),_paired_iou50(boxes,sa)
            row["assigned"]+=int(allocated==name)
            row["gt_coco_boxes"]+=len(ca)
            row["gt_sama_boxes"]+=len(sa)
            row["proposals"]+=len(boxes)
            row["matched_coco_iou50"]+=ctp
            row["matched_sama_iou50"]+=stp
            row["unmatched_coco_not_proven_false"]+=len(boxes)-ctp
            row["unmatched_sama_not_proven_false"]+=len(boxes)-stp
        if row["assigned"]!=SAMPLES_PER_CLASS or row["gt_coco_boxes"]<SAMPLES_PER_CLASS or row["gt_sama_boxes"]<SAMPLES_PER_CLASS:
            raise SourceGateError("STOP_SCHEMA: missing positives")
        row["recall_coco_iou50"]=round(row["matched_coco_iou50"]/row["gt_coco_boxes"],6)
        row["recall_sama_iou50"]=round(row["matched_sama_iou50"]/row["gt_sama_boxes"],6)
        result[name]=row
    return result


def run(annotations: Path, sama_zip: Path, *,
        stage: str, model_s: Path | None = None,
        model_m: Path | None = None, model_nano: Path | None = None):
    if stage not in ("source","abi","benchmark"):
        raise ValueError("unapproved stage")
    cases, maps, original_gt, sama_gt, image_info, source = source_and_truth(
        annotations,sama_zip)
    base={
        "experiment":"PER-YOLOX-SM-0 Rockchip host evidence",
        "stage":stage,"source":source,
        "rockchip_reference_sha":ROCKCHIP_PIN,
        "score_threshold":SCORE_THRESHOLD,
        "nms_threshold_vendor":NMS_THRESHOLD,
        "max_detections":MAX_DETECTIONS,
        "model_promoted":False,"actual_rk3566_npu_inference":False,
        "mediad_modified":False,"robotd_modified":False,
        "sqlite_writes":0,"motor_commands":0,"qwen_calls":0,
        "input_photo_download_count":0,
        "inferences_executed":{"s":0,"m":0,"nano":0}
    }
    if stage=="source":
        base["status"]="SOURCE_PASS_NO_MODELS_NO_PIXELS"
        return base
    if model_s is None or model_m is None:
        raise SourceGateError("STOP_MODEL: both vendor variants required")
    sessions,model_proofs=open_vendor_models(
        model_s,model_m,require_frozen=(stage=="benchmark"))
    base["vendor_models"]=model_proofs
    if stage=="abi":
        # A real ONNX pass on a synthetic black input; still NOT a photo benchmark.
        import numpy as np
        synthetic=np.zeros((1,3,SIZE,SIZE),dtype=np.float32)
        for key,(session,name) in sessions.items():
            outputs=session.run(None,{name:synthetic})
            validate_heads(outputs)
            base["inferences_executed"][key]=1
        base["status"]="HOST_VENDOR_ABI_SMOKE_ONLY_NO_PUBLIC_PIXELS"
        return base
    if (not all(FROZEN_VENDOR_SHA256.values())
            or model_nano is None):
        raise SourceGateError("STOP_MODEL: weights not pinned before image access")
    from microduck_companion.cata2_bbox_eval import CocoCase, _official_jpeg
    from microduck_companion.cata_yolox_categories import (
        MODEL_SHA256, prepare_image,validate_model_file)
    from experiments.per80_yolox_coco_public import decode_all_classes
    import onnxruntime as ort
    validate_model_file(model_nano)
    opts=ort.SessionOptions()
    opts.intra_op_num_threads=opts.inter_op_num_threads=1
    nano=ort.InferenceSession(str(model_nano),sess_options=opts,providers=["CPUExecutionProvider"])
    if (len(nano.get_inputs())!=1 or
            nano.get_inputs()[0].shape != [1,3,416,416] or
            len(nano.get_outputs())!=1 or
            nano.get_outputs()[0].shape != [1,3549,85]):
        raise SourceGateError("STOP_MODEL: Nano baseline ABI changed")
    predictions={key:{} for key in ("s","m","nano")}
    durations={key:[] for key in ("s","m","nano")}
    photo_hashes=[]
    for ident,_category in cases:
        width,height,filename,_license=image_info[ident]
        jpeg=_official_jpeg(CocoCase(ident,filename,width,height,()))
        photo_hashes.append(sha256(jpeg).hexdigest())
        vendor_input=prepare_vendor(jpeg,width=width,height=height)
        nano_input=prepare_image(jpeg,mode="original")
        for key,(session,name) in sessions.items():
            t0=time.perf_counter()
            heads=session.run(None,{name:vendor_input})
            durations[key].append(1000*(time.perf_counter()-t0))
            predictions[key][ident]=decode_vendor_heads(heads,width=width,height=height)
        t0=time.perf_counter()
        raw=nano.run(None,{nano.get_inputs()[0].name:nano_input})[0]
        durations["nano"].append(1000*(time.perf_counter()-t0))
        predictions["nano"][ident]=decode_all_classes(raw,width=width,height=height)
    if (len(set(photo_hashes))!=N_IMAGES
            or any(len(predictions[k])!=N_IMAGES for k in predictions)):
        raise SourceGateError("STOP_SOURCE: repeated or incomplete images")
    base.update(
        status="HOST_REAL_PUBLIC_PAIRED_COMPARISON_COMPLETE_STOP_PROMOTION",
        input_photo_download_count=N_IMAGES,
        inferences_executed={k:N_IMAGES for k in predictions},
        jpeg_aggregate_sha256=sha256("|".join(photo_hashes).encode()).hexdigest(),
        nano_model_sha256=MODEL_SHA256,
        host_peak_rss_kib_process=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        results={k:{
            "per_class":score_same_images(cases,maps,original_gt,sama_gt,predictions[k]),
            "inference_p50_ms_host_only":round(statistics.median(durations[k]),3),
            "inference_p95_ms_host_only":round(sorted(durations[k])[math.ceil(.95*len(cases))-1],3)
        } for k in predictions},
    )
    return base


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-metadata",action="store_true")
    p.add_argument("--approved-public-media",action="store_true")
    p.add_argument("--stage",choices=("source","abi","benchmark"),required=True)
    p.add_argument("--annotations",required=True,type=Path)
    p.add_argument("--sama-zip",required=True,type=Path)
    p.add_argument("--model-s",type=Path)
    p.add_argument("--model-m",type=Path)
    p.add_argument("--model-nano",type=Path)
    args=p.parse_args(argv)
    if not args.approved_public_metadata:
        p.error("explicit public source preflight required")
    if args.stage=="benchmark" and not args.approved_public_media:
        p.error("explicit public media access required")
    print(json.dumps(run(
        args.annotations,args.sama_zip,stage=args.stage,
        model_s=args.model_s,model_m=args.model_m,model_nano=args.model_nano,
    ),sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
