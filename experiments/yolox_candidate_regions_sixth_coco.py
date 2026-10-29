"""Host-only YOLOX candidate-region study on sixth disjoint COCO-val cohort.

No second model, additional detector, segmentation, camera, Qwen, SQLite or
motor access. A YOLOX COCO proposal is not a verified generic object.
"""
from __future__ import annotations

from collections import defaultdict
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import statistics
import time

from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, COCO_IDS, CATEGORIES, MAX_COCO_JSON_BYTES,
    _official_jpeg, select_coco_cases,
)
from microduck_companion.cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, _grid, prepare_image, validate_model_file,
)

STUDY = "sixth_disjoint_coco_val_yolox_candidates_20261029"
MAX_PRE_NMS = 160
NMS_IOU = 0.50
PROPOSAL_CAPS = (1, 3, 5)
MATCH_IOU = .50
MIN_K3_GAIN = 2
MIN_K3_BALLS = 1
MAX_K3_UNMATCHED_FRACTION = .70  # COCO annotation incomplete; diagnostic gate only
MAX_P95_SELECTION_MS_HOST = 15.0


def _remove_previous_ids(data, ids):
    return json.dumps({
        **data,
        "images": [x for x in data["images"] if x["id"] not in ids],
        "annotations": [a for a in data["annotations"]
                        if a["image_id"] not in ids],
    }, separators=(",", ":")).encode("utf-8")


def sixth_disjoint(blob):
    if (len(blob) > MAX_COCO_JSON_BYTES or
            hashlib.sha256(blob).hexdigest() != ANNOTATIONS_SHA256):
        raise ValueError("unapproved COCO annotations")
    data = json.loads(blob)
    excluded = set()
    sizes = []
    sixth = ()
    for per_class, negatives in ((4, 4), (4, 4), (3, 3),
                                 (2, 2), (2, 2), (2, 2)):
        subset = select_coco_cases(
            _remove_previous_ids(data, excluded) if excluded else blob,
            per_class=per_class, negatives=negatives,
        )
        ids = {c.image_id for c in subset}
        if ids & excluded or len(subset) != 5*per_class+negatives:
            raise ValueError("COCO cohort overlap")
        excluded.update(ids)
        sizes.append(len(subset))
        sixth = subset
    if sizes != [24, 24, 18, 12, 12, 12]:
        raise ValueError("unexpected sixth cohort")
    return sixth, data, sizes[:-1]


def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    overlap = max(0, min(ax2,bx2)-max(ax1,bx1))*max(
        0, min(ay2,by2)-max(ay1,by1))
    union = (ax2-ax1)*(ay2-ay1)+(bx2-bx1)*(by2-by1)-overlap
    return overlap/union if union > 0 else 0.


def decode_candidates(raw, *, width, height, max_results=5):
    """Fixed .25 YOLOX joint score and existing 0.50 class-agnostic NMS.

    These candidates are hypotheses amongst the 80 pretrained COCO classes,
    NOT a learned open-set or category-free object detector.
    """
    import numpy as np
    if (type(width) is not int or type(height) is not int
            or not 32 <= width <= 4096 or not 32 <= height <= 4096
            or type(max_results) is not int or max_results not in PROPOSAL_CAPS):
        raise ValueError("invalid geometry or cap")
    arr = np.asarray(raw)
    if (arr.shape != (1,3549,85)
            or not np.issubdtype(arr.dtype, np.floating)
            or not np.isfinite(arr).all()
            or np.any(arr[...,4:] < 0) or np.any(arr[...,4:] > 1)):
        raise ValueError("invalid YOLOX output")
    a = arr[0]
    confidence_joint = a[:,4,None]*a[:,5:]
    best_classes = np.argmax(confidence_joint,axis=1)
    scores = confidence_joint[np.arange(a.shape[0]),best_classes]
    cand = np.flatnonzero(scores >= MIN_SCORE)
    order = sorted(cand.tolist(), key=lambda k:(-float(scores[k]),k))[:MAX_PRE_NMS]
    grid, stride = _grid()
    ratio = min(SIZE/width,SIZE/height)
    rw, rh = max(1,round(width*ratio)),max(1,round(height*ratio))
    xscale, yscale = width/rw,height/rh
    accepted = []
    for k in order:
        with np.errstate(over="ignore",invalid="ignore"):
            centre = (a[k,:2]+grid[k])*stride[k]
            span = np.exp(a[k,2:4])*stride[k]
        if not np.isfinite(centre).all() or not np.isfinite(span).all():
            continue
        box = (
            float(np.clip((centre[0]-span[0]/2)*xscale,0,width)),
            float(np.clip((centre[1]-span[1]/2)*yscale,0,height)),
            float(np.clip((centre[0]+span[0]/2)*xscale,0,width)),
            float(np.clip((centre[1]+span[1]/2)*yscale,0,height)),
        )
        if min(box[2]-box[0],box[3]-box[1]) < 9:
            continue
        if any(_iou(box,old["xyxy"]) > NMS_IOU for old in accepted):
            continue
        accepted.append({
            "xyxy": box,
            "score": round(float(scores[k]),6),
            "untrusted_coco_class_index": int(best_classes[k]),
        })
        if len(accepted) >= max_results:
            break
    return accepted


def _all_gt_boxes(anns, width, height):
    """All 80 COCO categories; annotation gaps never imply no object."""
    gt=[]
    for ann in anns:
        if ann.get("iscrowd") or not isinstance(ann.get("bbox"),list):
            continue
        b=ann["bbox"]
        if len(b)!=4 or not all(type(x) in (int,float) and math.isfinite(x) for x in b):
            continue
        x,y,w,h=b
        if w<=0 or h<=0:
            continue
        box=(max(0.,float(x)),max(0.,float(y)),
             min(float(width),float(x+w)),min(float(height),float(y+h)))
        if box[2]>box[0] and box[3]>box[1]:
            gt.append({"category_id":ann.get("category_id"),"xyxy":box})
    return gt


def _metrics(rows, cap):
    target = [r for r in rows if r["expected_target_for_scoring"]!="target_free"]
    hits=sum(r[f"target_hit_at_{cap}"] for r in target)
    ball_hits=sum(r[f"target_hit_at_{cap}"] for r in target
                  if r["expected_target_for_scoring"]=="sports_ball")
    allproposals=[p for r in rows for p in r["proposals"][:cap]]
    annotated=sum(p["overlaps_any_COCO_annotation_IoU50"] for p in allproposals)
    return {
        "matched_target_images":hits,
        "matched_ball_images":ball_hits,
        "all_images_with_at_least_one_candidate":sum(bool(r["proposals"][:cap])
                                                      for r in rows),
        "proposals_total":len(allproposals),
        "proposals_matched_to_an_80_class_COCO_annotation":annotated,
        "proposals_not_matched_to_COCO_annotations_not_proved_false":
            len(allproposals)-annotated,
        "unmatched_annotation_fraction":round(
            (len(allproposals)-annotated)/len(allproposals),4
        ) if allproposals else None,
    }


def run(annotation_path,model_path):
    import onnxruntime as ort
    from PIL import Image

    blob=Path(annotation_path).read_bytes()
    cases,annotations,prior_sizes=sixth_disjoint(blob)
    by_id=defaultdict(list)
    for a in annotations["annotations"]:
        by_id[a["image_id"]].append(a)
    validate_model_file(Path(model_path))
    opts=ort.SessionOptions()
    opts.intra_op_num_threads=1
    opts.inter_op_num_threads=1
    session=ort.InferenceSession(str(model_path),sess_options=opts,
                                 providers=["CPUExecutionProvider"])
    if (len(session.get_inputs())!=1 or len(session.get_outputs())!=1
            or session.get_inputs()[0].shape!=[1,3,SIZE,SIZE]
            or session.get_inputs()[0].name!="images"
            or session.get_outputs()[0].shape!=[1,3549,85]
            or session.get_outputs()[0].name!="output"):
        raise ValueError("unapproved YOLOX ONNX interface")
    rows=[]
    cpu_times=[]
    infer_times=[]
    for i,c in enumerate(cases):
        name=list(CATEGORIES)[i//2] if i<10 else "target_free"
        raw_jpeg=_official_jpeg(c)
        with Image.open(BytesIO(raw_jpeg)) as image:
            if image.size!=(c.width,c.height):
                raise ValueError("image dimensions changed")
        inputs=prepare_image(raw_jpeg,mode="original")
        t0=time.perf_counter()
        raw=session.run(None,{"images":inputs})[0]
        infer_times.append((time.perf_counter()-t0)*1000)
        t0=time.perf_counter()
        boxes=decode_candidates(raw,width=c.width,height=c.height,max_results=5)
        cpu_times.append((time.perf_counter()-t0)*1000)
        gts=_all_gt_boxes(by_id[c.image_id],c.width,c.height)
        targets=[g["xyxy"] for g in gts if
                 g["category_id"]==COCO_IDS.get(name)] if name!="target_free" else []
        if name!="target_free" and not targets:
            raise ValueError("target annotation absent on class-selected image")
        candidate_rows=[]
        for p in boxes:
            overlap_all=max((_iou(p["xyxy"],g["xyxy"]) for g in gts),default=0.)
            candidate_rows.append({
                **p,
                "max_IoU_to_any_COCO_annotation_for_scoring":round(overlap_all,4),
                "overlaps_any_COCO_annotation_IoU50":overlap_all>=MATCH_IOU,
                "max_IoU_to_expected_category_for_scoring":round(
                    max((_iou(p["xyxy"],gt) for gt in targets),default=0.),4),
            })
        row={
            "COCO_image_id":c.image_id,
            "expected_target_for_scoring":name,
            "original_dimensions":[c.width,c.height],
            "all_80_class_GT_boxes_count":len(gts),
            "expected_target_GT_boxes_count":len(targets),
            "source_is_camera_agnostic":True,
            "proposals":candidate_rows,
            "GT_not_used_for_proposal_selection":True,
        }
        for cap in PROPOSAL_CAPS:
            row[f"target_hit_at_{cap}"]=bool(targets) and any(
                p["max_IoU_to_expected_category_for_scoring"]>=MATCH_IOU
                for p in candidate_rows[:cap])
        rows.append(row)
    metrics={f"k_{k}":_metrics(rows,k) for k in PROPOSAL_CAPS}
    gains=metrics["k_3"]["matched_target_images"]-metrics["k_1"]["matched_target_images"]
    p95=sorted(cpu_times)[math.ceil(.95*len(cpu_times))-1]
    criteria={
        "top3_at_least_two_more_target_images_than_top1":gains>=MIN_K3_GAIN,
        "top3_at_least_one_of_two_balls":metrics["k_3"]["matched_ball_images"]>=MIN_K3_BALLS,
        "top3_unmatched_COCO_annotation_fraction_at_most_0_70":
            metrics["k_3"]["unmatched_annotation_fraction"] is not None and
            metrics["k_3"]["unmatched_annotation_fraction"]<=MAX_K3_UNMATCHED_FRACTION,
        "postprocess_p95_host_at_most_15ms":p95<=MAX_P95_SELECTION_MS_HOST,
    }
    return {
        "study":STUDY,
        "status":"candidate_proposals_gate_passed" if all(criteria.values())
                 else "candidate_proposals_gate_failed",
        "gate_passed":all(criteria.values()),
        "criteria":criteria,
        "previous_disjoint_cohort_sizes":prior_sizes,
        "sixth_cohort_images":len(cases),
        "sixth_COCO_image_IDs":[c.image_id for c in cases],
        "image_selection_independent_of_predictions":True,
        "target_labels_only_for_scoring":True,
        "threshold_unchanged":MIN_SCORE,
        "model_sha256":MODEL_SHA256,
        "annotations_sha256":ANNOTATIONS_SHA256,
        "caps":list(PROPOSAL_CAPS),
        "IoU_threshold":MATCH_IOU,
        "metrics":metrics,
        "extra_target_hits_k3_vs_k1":gains,
        "inference_host_cpu_ms_median":round(statistics.median(infer_times),3),
        "postprocessing_host_cpu_ms_median":round(statistics.median(cpu_times),3),
        "postprocessing_host_cpu_ms_p95":round(p95,3),
        "host_peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "background_is_not_segmentation":True,
        "COCO_label_gaps_limit_false_positive_claims":True,
        "COCO_target_free_images_not_object_free":True,
        "not_a_category_free_or_unknown_object_detector":True,
        "no_color_or_shape_extraction_delivered":True,
        "no_online_learning_or_qwen":True,
        "no_oem_or_motor_or_robot_action":True,
        "robot_NPU_not_tested":True,
        "rows":rows,
    }


if __name__=="__main__":
    report=run(os.environ["COCO_VAL_ANNOTATIONS"],os.environ["YOLOX_MODEL"])
    text=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
    Path(os.environ["CANDIDATE_REPORT"]).write_text(text,encoding="utf-8")
    print(json.dumps(report,separators=(",",":"),allow_nan=False))
