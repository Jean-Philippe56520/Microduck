"""VIS-APP-1: predeclared seventh disjoint COCO color/geometry host test.

Independent polygon masks are used *only* for evaluation. YOLOX box selection,
region colour and geometry are computed before the labels/masks are consulted.
No GrabCut, new model, memory writes, camera, OEM or motor interfaces.
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

from PIL import Image, ImageDraw

from experiments.region_appearance_probe import (
    _color_summary, describe_region,
)
from experiments.yolox_candidate_regions_sixth_coco import (
    _iou, _remove_previous_ids,
)
from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, CATEGORIES, COCO_IDS, MAX_COCO_JSON_BYTES,
    _official_jpeg, select_coco_cases,
)
from microduck_companion.cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, prepare_image, validate_model_file,
)
from microduck_companion.yolox_attention_candidates import decode_candidates

SEVENTH_SIZES = (24, 24, 18, 12, 12, 12, 12)
TARGET_COUNT = 10
MATCH_IOU = .50
MIN_GT_ELIGIBLE = 5
MIN_ORACLE_COVERAGE = .70
MIN_ORACLE_PRECISION = .75
MIN_ORACLE_GAIN_VS_FULL = 1
MIN_TOP3_LOCALIZED = 7
MIN_TOP3_BALLS = 1
MIN_TOP3_COLOUR_PRECISION = .60
MAX_POSTPROCESS_MEDIAN_MS = 10.0
MAX_POSTPROCESS_P95_MS = 25.0


def seventh_cohort(blob):
    if (not isinstance(blob, bytes) or len(blob) > MAX_COCO_JSON_BYTES
            or hashlib.sha256(blob).hexdigest() != ANNOTATIONS_SHA256):
        raise ValueError("COCO annotations hash or size changed")
    data = json.loads(blob)
    exclude = set()
    sizes = []
    last = ()
    for per, neg in ((4, 4), (4, 4), (3, 3),
                     (2, 2), (2, 2), (2, 2), (2, 2)):
        sub = select_coco_cases(
            _remove_previous_ids(data, exclude) if exclude else blob,
            per_class=per, negatives=neg,
        )
        ids = {c.image_id for c in sub}
        if ids & exclude or len(ids) != 5*per+neg:
            raise ValueError("overlapping seventh cohort")
        exclude.update(ids)
        sizes.append(len(ids))
        last = sub
    if tuple(sizes) != SEVENTH_SIZES or len(last) != 12:
        raise ValueError("incorrect cohort sizes")
    return last, data


def polygon_gt(items, category_id, image):
    """Largest noncrowd polygon of chosen COCO target, for scoring only."""
    candidates = [
        a for a in items if a.get("category_id") == category_id
        and a.get("iscrowd") == 0 and isinstance(a.get("segmentation"), list)
        and isinstance(a.get("bbox"), list) and len(a["bbox"]) == 4
    ]
    candidates.sort(key=lambda a: (-float(a.get("area",0)), a.get("id",0)))
    if not candidates:
        return None, None
    selected = candidates[0]
    x, y, bw, bh = selected["bbox"]
    box = (max(0.,float(x)),max(0.,float(y)),
           min(float(image.width),float(x+bw)),
           min(float(image.height),float(y+bh)))
    if min(box[2]-box[0], box[3]-box[1]) < 12:
        return None, None
    ratio = min(1.,640/max(image.size))
    small = image.copy()
    if ratio < 1.:
        small.thumbnail((640,640),Image.Resampling.BILINEAR)
    mask = Image.new("L", small.size, 0)
    draw = ImageDraw.Draw(mask)
    for poly in selected["segmentation"]:
        if not isinstance(poly,list) or len(poly)<6 or len(poly)%2:
            continue
        pts = []
        for i in range(0,len(poly),2):
            px,py=poly[i],poly[i+1]
            if (type(px) not in (int,float) or type(py) not in (int,float)
                or not math.isfinite(px) or not math.isfinite(py)):
                pts=[]
                break
            pts.append((px*small.width/image.width,
                        py*small.height/image.height))
        if pts:
            draw.polygon(pts,fill=255)
    if mask.getbbox() is None:
        return None, None
    raw = list(small.getdata())
    labels = list(mask.getdata())
    foreground = [pixel for pixel,bit in zip(raw,labels) if bit >= 128]
    if len(foreground) < 35:
        return None, None
    reference = _color_summary(foreground)
    return box, {
        "color": reference["color"], "color_dominance":reference["dominance"],
        "eligible_unambiguous":reference["measured"],
        "foreground_pixels_at_bounded_resolution":len(foreground),
        "polygon_mask_source": "COCO_GT_only_for_scoring",
    }


def run(annotation_path, model_path):
    import onnxruntime as ort
    raw = Path(annotation_path).read_bytes()
    cases, annotations = seventh_cohort(raw)
    by_id = defaultdict(list)
    for a in annotations["annotations"]:
        by_id[a["image_id"]].append(a)
    validate_model_file(Path(model_path))
    options=ort.SessionOptions()
    options.intra_op_num_threads=1
    options.inter_op_num_threads=1
    session=ort.InferenceSession(str(model_path),sess_options=options,
                                 providers=["CPUExecutionProvider"])
    if (len(session.get_inputs())!=1 or len(session.get_outputs())!=1
        or session.get_inputs()[0].name!="images"
        or session.get_outputs()[0].name!="output"
        or session.get_inputs()[0].shape != [1,3,SIZE,SIZE]
        or session.get_outputs()[0].shape != [1,3549,85]):
        raise ValueError("unexpected YOLOX model ABI")
    rows=[]
    region_costs=[]
    for ix,case in enumerate(cases):
        label = list(CATEGORIES)[ix//2] if ix < TARGET_COUNT else "target_free"
        jpeg=_official_jpeg(case)
        with Image.open(BytesIO(jpeg)) as source:
            if source.format!="JPEG" or source.size!=(case.width,case.height):
                raise ValueError("unexpected original image")
            image=source.convert("RGB")
        # No COCO label is fed to YOLOX or the region descriptors.
        head=session.run(None,{"images":prepare_image(jpeg,mode="original")})[0]
        regions=decode_candidates(head,width=case.width,height=case.height)
        candidates=[]
        for p in regions:
            tick=time.perf_counter()
            center=describe_region(image,p["xyxy"])
            full=describe_region(image,p["xyxy"],central_fraction=1.0)
            region_costs.append((time.perf_counter()-tick)*1000)
            candidates.append({
                "xyxy":p["xyxy"],
                "joint_score":p["score"],
                "untrusted_class_index":p["untrusted_coco_class_index"],
                "center":center,
                "whole_box_control":full,
            })
        row={
            "coco_image_id":case.image_id,
            "expected_category_for_scoring_only":label,
            "image_size":list(image.size),
            "candidate_regions":candidates,
            "candidate_selection_and_descriptors_before_GT":True,
            "target_GT_status":"target_free_not_empty" if ix>=TARGET_COUNT else "pending",
        }
        if ix<TARGET_COUNT:
            gtbox,gt_colour=polygon_gt(by_id[case.image_id], COCO_IDS[label],image)
            if gtbox is None:
                row["target_GT_status"]="unavailable"
            else:
                row["target_GT_status"]="available"
                # Oracle GT-box is a CONTROL, never a deployable detector.
                oracle_c=describe_region(image,gtbox)
                oracle_f=describe_region(image,gtbox,central_fraction=1.0)
                row["target_GT_color"]=gt_colour
                row["oracle_bbox_central_color"]=oracle_c["color"]
                row["oracle_bbox_full_color"]=oracle_f["color"]
                row["oracle_bbox_aspect_hint"]=oracle_c["geometry"]["bbox_geometry_only"]
                # Choose correspondence only for evaluation: all 3 candidate
                # descriptions already computed. This does not model robot attention.
                indexed=[
                    (i,_iou(p["xyxy"],gtbox),p)
                    for i,p in enumerate(candidates)
                ]
                match=max(indexed,key=lambda x:x[1]) if indexed else None
                row["best_target_matching_candidate_rank_for_scoring_only"]=(
                    match[0]+1 if match and match[1]>=MATCH_IOU else None)
                row["best_target_matching_candidate_bbox_IoU"]=round(
                    match[1],4) if match else 0.
                row["matching_candidate_color_for_scoring_only"]=(
                    match[2]["center"]["color"]
                    if match and match[1]>=MATCH_IOU else None)
                row["matching_candidate_geometry_only"]=(
                    match[2]["center"]["geometry"]["bbox_geometry_only"]
                    if match and match[1]>=MATCH_IOU else None)
        rows.append(row)

    valid=[r for r in rows if r["target_GT_status"]=="available"]
    eligible=[r for r in valid if r["target_GT_color"]["eligible_unambiguous"]]
    centered=[r for r in eligible if r["oracle_bbox_central_color"]!="unknown"]
    centered_correct=sum(r["oracle_bbox_central_color"]==r["target_GT_color"]["color"]
                         for r in eligible)
    full_correct=sum(r["oracle_bbox_full_color"]==r["target_GT_color"]["color"]
                     for r in eligible)
    linked=[r for r in eligible if r["best_target_matching_candidate_rank_for_scoring_only"]]
    linked_given=[r for r in linked if
                  r["matching_candidate_color_for_scoring_only"]!="unknown"]
    linked_correct=sum(r["matching_candidate_color_for_scoring_only"]==
                       r["target_GT_color"]["color"] for r in linked_given)
    target_hits=sum(bool(r["best_target_matching_candidate_rank_for_scoring_only"])
                    for r in valid)
    ball_hits=sum(bool(r["best_target_matching_candidate_rank_for_scoring_only"])
                  for r in valid if r["expected_category_for_scoring_only"]=="sports_ball")
    costs=sorted(region_costs)
    p95=costs[math.ceil(.95*len(costs))-1] if costs else None
    checks={
        "all_10_target_polygon_masks":len(valid)==TARGET_COUNT,
        "at_least_5_GT_objects_have_unambiguous_dominant_color":
            len(eligible)>=MIN_GT_ELIGIBLE,
        "oracle_center_coverage_at_least_70pct":(
            len(eligible)>0 and len(centered)/len(eligible)>=MIN_ORACLE_COVERAGE),
        "oracle_center_precision_at_least_75pct":(
            len(centered)>0 and centered_correct/len(centered)>=MIN_ORACLE_PRECISION),
        "center_better_than_whole_GT_box_by_one_correct":
            centered_correct-full_correct>=MIN_ORACLE_GAIN_VS_FULL,
        "at_least_7_target_boxes_in_YOLOX_top3":target_hits>=MIN_TOP3_LOCALIZED,
        "at_least_1_ball_in_YOLOX_top3":ball_hits>=MIN_TOP3_BALLS,
        "matched_top3_resolved_colors_60pct_correct_and_at_least_3":(
            len(linked_given)>=3 and
            linked_correct/len(linked_given)>=MIN_TOP3_COLOUR_PRECISION),
        "median_two_descriptions_under_10ms_PC":(
            len(costs)>0 and statistics.median(costs)<=MAX_POSTPROCESS_MEDIAN_MS),
        "p95_two_descriptions_under_25ms_PC":(
            p95 is not None and p95<=MAX_POSTPROCESS_P95_MS),
    }
    return {
        "study":"VIS-APP-1_seventh_disjoint_COCO_polygon_color",
        "status":"passed" if all(checks.values()) else "failed",
        "predeclared_gate_passed":all(checks.values()),
        "checks":checks,
        "images":len(cases),
        "earlier_cohort_sizes":[24,24,18,12,12,12],
        "coco_image_ids":[c.image_id for c in cases],
        "unchanged_YOLOX_SHA256":MODEL_SHA256,
        "unchanged_YOLOX_threshold":MIN_SCORE,
        "COCO_annotations_SHA256":ANNOTATIONS_SHA256,
        "GT_target_polygons":len(valid),
        "GT_eligible_unambiguous_color":len(eligible),
        "oracle_center_resolved":len(centered),
        "oracle_center_color_correct":centered_correct,
        "oracle_whole_box_color_correct":full_correct,
        "top3_target_IoU50_hits":target_hits,
        "top3_ball_IoU50_hits":ball_hits,
        "matched_top3_GT_eligible":len(linked),
        "matched_top3_color_resolved":len(linked_given),
        "matched_top3_color_correct":linked_correct,
        "region_descriptor_two_methods_host_ms":{
            "median":round(statistics.median(costs),3) if costs else None,
            "p95_nearest_rank":round(p95,3) if p95 is not None else None,
            "max":round(max(costs),3) if costs else None,
        },
        "n_regions_timed":len(costs),
        "host_peak_RSS_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "GT_used_to_select_detector_proposals":False,
        "GT_used_to_choose_matched_proposal_for_scoring_only":True,
        "colors_may_be_background":True,
        "shape_descriptions_delivered":False,
        "bbox_aspect_is_not_object_shape":True,
        "real_object_vs_screen_unproven":True,
        "not_generic_unknown_object_detection":True,
        "not_RK3566_or_NPU_measured":True,
        "motor_commands":0,"sqlite_writes":0,"qwen_calls":0,
        "rows":rows
    }


if __name__=="__main__":
    result=run(os.environ["COCO_VAL_ANNOTATIONS"],os.environ["YOLOX_MODEL"])
    text=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
    Path(os.environ["APP_RESULTS"]).write_text(text,encoding="utf-8")
    print(json.dumps(result,separators=(",",":"),allow_nan=False))
