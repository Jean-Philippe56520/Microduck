"""Fourth disjoint COCO2017-val cohort: evaluate fixed GrabCut and YOLOX boxes.

GT polygons score masks, NEVER tune segmentation or model. No JPEG saved,
no Qwen/SQLite/OEM/robot. The two controls are target-free, not empty scenes.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import statistics
import time

from experiments.grabcut_region_probe import (
    describe_mask, grabcut_rectangle, mask_iou,
)
from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, CATEGORIES, MAX_COCO_JSON_BYTES,
    _official_jpeg, decode_boxes, iou, select_coco_cases, Box,
)
from microduck_companion.cata_yolox_categories import (
    MODEL_SHA256, MIN_SCORE, SIZE, _grid, prepare_image,
    validate_model_file,
)

COHORT_NAME = "fourth_disjoint_coco_polygon_20261029"
COHORT_TARGET_COUNTS = (2, 2)
EXPECTED_IMAGES = 12
MIN_USABLE_MASKS = 8
MIN_ORACLE_IOU = .55
MIN_MEAN_GAIN_OVER_RECT = .08
MIN_COLOUR_AGREEMENT = .60
MAX_MEDIAN_GRABCUT_MS_HOST = 250.0
MAX_CASES = 12


def _remove_ids(source, ids):
    # Keep all original annotations/labels except images explicitly excluded
    # from the candidate selection. This is not a reshuffle after results.
    stripped = {
        key: value for key, value in source.items()
    }
    stripped["images"] = [x for x in source["images"] if x["id"] not in ids]
    stripped["annotations"] = [
        x for x in source["annotations"] if x["image_id"] not in ids
    ]
    return json.dumps(stripped, separators=(",", ":")).encode("utf-8")


def select_fourth(blob):
    if hashlib.sha256(blob).hexdigest() != ANNOTATIONS_SHA256:
        raise ValueError("unapproved annotation SHA")
    data = json.loads(blob)
    first = select_coco_cases(blob)
    a = {x.image_id for x in first}
    second = select_coco_cases(blob, excluded_image_ids=frozenset(a))
    b = {x.image_id for x in second}
    third_blob = _remove_ids(data, a | b)
    third = select_coco_cases(third_blob, per_class=3, negatives=3)
    c = {x.image_id for x in third}
    last_blob = _remove_ids(data, a | b | c)
    fourth = select_coco_cases(last_blob, per_class=2, negatives=2)
    assert len(first) == 24 and len(second) == 24 and len(third) == 18
    if (len(fourth) != EXPECTED_IMAGES or
            {x.image_id for x in fourth}.intersection(a | b | c)):
        raise ValueError("fourth cohort not disjoint")
    return fourth, data, (len(a), len(b), len(c))


def _polymask(anns, target, w, h, *, source_w, source_h):
    import cv2
    import numpy as np
    valid = [
        a for a in anns if a.get("category_id") == target
        and a.get("iscrowd") == 0
        and isinstance(a.get("segmentation"), list)
        and isinstance(a.get("bbox"), list) and len(a["bbox"]) == 4
    ]
    if not valid:
        return None, None
    chosen = max(valid, key=lambda a: float(a["bbox"][2]*a["bbox"][3]))
    mask = np.zeros((h, w), np.uint8)
    xscale, yscale = w/source_w, h/source_h
    polys = []
    for poly in chosen["segmentation"]:
        if not isinstance(poly, list) or len(poly) < 6 or len(poly)%2:
            continue
        vertices = np.array(poly, dtype=np.float32).reshape(-1, 2)
        if not np.isfinite(vertices).all():
            continue
        vertices[:, 0] *= xscale
        vertices[:, 1] *= yscale
        polys.append(np.round(vertices).astype(np.int32))
    if not polys:
        return None, None
    cv2.fillPoly(mask, polys, 255)
    return mask, chosen


def _crop_to_box_mask(box, w, h):
    import numpy as np
    result = np.zeros((h, w), np.uint8)
    x1, y1, x2, y2 = box
    result[max(0, int(y1)):min(h, math.ceil(y2)),
           max(0, int(x1)):min(w, math.ceil(x2))] = 255
    return result


def _max_80_match(raw, imgw, imgh, gt_box):
    """One fixed 0.25-score pass, 80 pretrained COCO names, no tuned class."""
    import numpy as np
    a = np.asarray(raw)
    if a.shape != (1, 3549, 85) or not np.isfinite(a).all():
        raise ValueError("not the pinned YOLOX head")
    a = a[0]
    scores = a[:, 4, None] * a[:, 5:]
    classes = np.argmax(scores, axis=1)
    conf = scores[np.arange(len(scores)), classes]
    selected = np.flatnonzero(conf >= MIN_SCORE)
    selected = sorted(selected.tolist(), key=lambda k:(-float(conf[k]), k))[:160]
    grid, stride = _grid()
    ratio = min(SIZE / imgw, SIZE / imgh)
    rw, rh = max(1, round(imgw*ratio)), max(1, round(imgh*ratio))
    best = (0., None)
    for k in selected:
        with np.errstate(over="ignore", invalid="ignore"):
            centre = (a[k, :2]+grid[k]) * stride[k]
            sz = np.exp(a[k, 2:4]) * stride[k]
        if not np.isfinite(centre).all() or not np.isfinite(sz).all():
            continue
        x1 = float(np.clip(centre[0]-sz[0]/2,0,rw)*imgw/rw)
        y1 = float(np.clip(centre[1]-sz[1]/2,0,rh)*imgh/rh)
        x2 = float(np.clip(centre[0]+sz[0]/2,0,rw)*imgw/rw)
        y2 = float(np.clip(centre[1]+sz[1]/2,0,rh)*imgh/rh)
        if x2 <= x1 or y2 <= y1:
            continue
        proposal = Box("person",(x1,y1,x2,y2),float(conf[k]))
        gt = Box("person",tuple(float(v) for v in gt_box))
        overlap = iou(proposal,gt)
        if overlap > best[0]:
            best=(overlap,{"xyxy":[x1,y1,x2,y2],
                          "score":round(float(conf[k]),5),
                          "coco_class_index":int(classes[k]),
                          "iou_bbox":round(overlap,5)})
    return best[1] if best[1] and best[0] >= .5 else None


def run(annotation_path: Path, model_path: Path):
    import cv2
    import numpy as np
    from PIL import Image
    from io import BytesIO
    rawjson = annotation_path.read_bytes()
    if len(rawjson)>MAX_COCO_JSON_BYTES:
        raise ValueError("annotation too large")
    cases, data, exclusions = select_fourth(rawjson)
    validate_model_file(model_path)
    anns = defaultdict(list)
    for item in data["annotations"]:
        anns[item["image_id"]].append(item)
    import onnxruntime as ort
    opt=ort.SessionOptions()
    opt.intra_op_num_threads=1
    opt.inter_op_num_threads=1
    session=ort.InferenceSession(str(model_path),
                                sess_options=opt,
                                providers=["CPUExecutionProvider"])
    if (session.get_inputs()[0].shape != [1,3,SIZE,SIZE] or
        session.get_outputs()[0].shape != [1,3549,85] or
        session.get_inputs()[0].name!="images" or
        session.get_outputs()[0].name!="output"):
        raise ValueError("unexpected model interface")
    records=[]
    t0=time.perf_counter()
    resource_before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    categories=list(CATEGORIES)
    for index,case in enumerate(cases):
        name=categories[index//2] if index < 10 else "target_free"
        sample=_official_jpeg(case)
        with Image.open(BytesIO(sample)) as pil:
            rgb=np.asarray(pil.convert("RGB"),dtype=np.uint8)
        if rgb.shape[:2]!=(case.height,case.width):
            raise ValueError("source dimensions wrong")
        # Host-only experimental result; JPEG transient, never logged or archived.
        scale=min(1.,640/max(case.width,case.height))
        w=max(2,round(case.width*scale))
        h=max(2,round(case.height*scale))
        small=cv2.resize(rgb,(w,h),interpolation=cv2.INTER_AREA)
        frame_info={
            "coco_image_id":case.image_id,"filename":case.filename,
            "human_category_for_scoring_only":name,
            "image_size":[case.width,case.height],
            "ground_truth_available":index<10,
        }
        if index >= 10:
            tensor=prepare_image(sample,mode="original")
            raw=session.run(None,{"images":tensor})[0]
            fixed=decode_boxes(raw,width=case.width,height=case.height)
            frame_info.update({
                "reference_target_boxes":0,
                "yolox_supported_target_proposals":len(fixed),
                "other_coco_objects_may_exist":True,
            })
            records.append(frame_info)
            continue
        target_id={"person":1,"cat":17,"dog":18,"sports_ball":37,"chair":62}[name]
        ground,chosen=_polymask(anns[case.image_id],target_id,w,h,
                                 source_w=case.width,source_h=case.height)
        if ground is None or int((ground>0).sum())<35:
            frame_info["status"]="no_polygon_gt"
            records.append(frame_info)
            continue
        x,y,bw,bh=chosen["bbox"]
        gtbox=(float(x),float(y),float(x+bw),float(y+bh))
        if min(bw,bh)*scale<9:
            frame_info["status"]="gt_too_small_at_bounded_resolution"
            records.append(frame_info)
            continue
        gt_box_small=[coord*scale for coord in gtbox]
        # Scale adjustment reflects the PIL->cv2 rounded image dimensions.
        gt_box_small=[v*(w/(case.width*scale) if k%2==0
                         else h/(case.height*scale))
                      for k,v in enumerate(gt_box_small)]
        oracle, pred_oracle, frame=grabcut_rectangle(rgb,gtbox)
        gt_ref=describe_mask(small,ground)
        bbox_ref=_crop_to_box_mask(gt_box_small,w,h)
        baseline_iou=mask_iou(bbox_ref,ground)
        mask_score=(mask_iou(pred_oracle,ground)
                    if pred_oracle is not None else None)
        if frame.shape!=small.shape:
            raise ValueError("internal resize drift")
        tensor=prepare_image(sample,mode="original")
        raw=session.run(None,{"images":tensor})[0]
        supported=decode_boxes(raw,width=case.width,height=case.height)
        best_supported=max((iou(b,Box(b.category,gtbox)) for b in supported),
                           default=0.)
        any_match=_max_80_match(raw,case.width,case.height,gtbox)
        predicted_descriptor=None
        predicted_iou=None
        if any_match is not None:
            p,pm,_=grabcut_rectangle(rgb,any_match["xyxy"])
            predicted_descriptor=p.get("descriptor")
            predicted_iou=(mask_iou(pm,ground) if pm is not None else None)
        pred_desc=oracle.get("descriptor")
        colors_ground={z["name"] for z in gt_ref.get("colors",[])[:1]}
        colors_pred={z["name"] for z in pred_desc.get("colors",[])[:1]} if pred_desc else set()
        color_agrees=(bool(colors_ground.intersection(colors_pred))
                      if colors_ground and colors_pred else None)
        frame_info.update({
            "status":"evaluated",
            "ground_polygon_pixels":int((ground>0).sum()),
            "bbox_iou_reference":round(baseline_iou,4),
            "grabcut_iou_oracle_box":round(mask_score,4)
              if mask_score is not None else None,
            "grabcut_minus_box_iou":round(mask_score-baseline_iou,4)
              if mask_score is not None else None,
            "gt_shape_approx":gt_ref.get("shape"),
            "grabcut_shape_approx":pred_desc.get("shape")
              if pred_desc else "unknown",
            "gt_top_color":next(iter(colors_ground),"unknown"),
            "grabcut_top_color":next(iter(colors_pred),"unknown"),
            "top_color_matches_polygon_gt":color_agrees,
            "grabcut_ms_cpu":oracle.get("grabcut_ms"),
            "yolox_supported_class_bbox_iou_best":round(best_supported,4),
            "any_80_class_box_iou50_match":any_match,
            "end_to_end_grabcut_gt_iou_if_matched":
              round(predicted_iou,4) if predicted_iou is not None else None,
            "end_to_end_shape_if_matched":
              predicted_descriptor.get("shape") if predicted_descriptor else None,
        })
        records.append(frame_info)
    evaluated=[r for r in records if r.get("status")=="evaluated"]
    usable=[r for r in evaluated if r.get("grabcut_iou_oracle_box") is not None]
    gains=[r["grabcut_minus_box_iou"] for r in usable]
    ious=[r["grabcut_iou_oracle_box"] for r in usable]
    times=[r["grabcut_ms_cpu"] for r in usable if r["grabcut_ms_cpu"] is not None]
    with_color=[r for r in usable if r["top_color_matches_polygon_gt"] is not None]
    hits=sum(r["top_color_matches_polygon_gt"] for r in with_color)
    balls=[r for r in usable if r["human_category_for_scoring_only"]=="sports_ball"]
    positive= len(usable)>=MIN_USABLE_MASKS and (
        sum(s>=MIN_ORACLE_IOU for s in ious)>=7 and
        statistics.mean(gains)>=MIN_MEAN_GAIN_OVER_RECT and
        (hits / len(with_color)>=MIN_COLOUR_AGREEMENT if with_color else False)
        and len(balls)>=2 and
        sum(r["gt_shape_approx"]=="round_like" and
            r["grabcut_shape_approx"]=="round_like" for r in balls)>=1
        and (statistics.median(times)<=MAX_MEDIAN_GRABCUT_MS_HOST if times else False))
    return {
        "status":"host_grabcut_predeclared_gate_passed" if positive
                 else "host_grabcut_predeclared_gate_failed",
        "gate_passed":positive,"study":COHORT_NAME,
        "annotation_sha256":ANNOTATIONS_SHA256,
        "yolox_model_sha256":MODEL_SHA256,
        "yolox_threshold_unchanged":MIN_SCORE,
        "excluded_previous_cohort_sizes":list(exclusions),
        "image_count":len(cases),"distinct_image_ids":len({c.image_id for c in cases}),
        "oracle_bbox_uses_gt_not_robot_detector":True,
        "polygon_gt_is_independent_of_grabcut":True,
        "cohort_label_selection_before_inference":True,
        "GT_polygon_available_cases":len(evaluated),
        "GT_mask_scored_cases":len(usable),
        "oracle_iou_median":round(statistics.median(ious),4) if ious else None,
        "oracle_mask_iou_ge_055":sum(x>=.55 for x in ious),
        "rectangle_baseline_iou_median":
            round(statistics.median([r["bbox_iou_reference"] for r in usable]),4)
            if usable else None,
        "oracle_iou_mean_gain_over_rectangle":
            round(statistics.mean(gains),4) if gains else None,
        "groundtruth_color_cases":len(with_color),
        "foreground_top_color_matches":hits,
        "ball_round_matches":sum(r["gt_shape_approx"]=="round_like" and
                                   r["grabcut_shape_approx"]=="round_like" for r in balls),
        "yolox_any_80_class_bbox_matches":sum(bool(r.get("any_80_class_box_iou50_match"))
                                           for r in evaluated),
        "yolox_5_target_class_bbox_matches":
            sum((r.get("yolox_supported_class_bbox_iou_best") or 0)>=.5 for r in evaluated),
        "median_grabcut_host_cpu_ms":round(statistics.median(times),3) if times else None,
        "peak_runner_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "previous_runner_rss_kib":resource_before,
        "total_host_elapsed_s":round(time.perf_counter()-t0,3),
        "negative_cases_are_target_free_not_object_free":True,
        "unknown_objects_not_authorized_for_action":True,
        "robot_or_npu_tested":False,
        "memory_writes":0,"qwen_calls":0,"motor_commands":0,
        "new_trained_models":0,
        "criteria_fixed":{
          "min_evaluable_polygon_gt":MIN_USABLE_MASKS,
          "at_least_7_masks_IoU_055":True,
          "min_mean_IoU_gain_over_rectangle":MIN_MEAN_GAIN_OVER_RECT,
          "min_color_agreement":MIN_COLOUR_AGREEMENT,
          "min_two_ball_masks_and_one_round_match":True,
          "max_median_grabcut_ms_on_runner":MAX_MEDIAN_GRABCUT_MS_HOST,
        },
        "cases":records,
    }


if __name__=="__main__":
    annotation_path=Path(os.environ["COCO_VAL_ANNOTATIONS"])
    model_path=Path(os.environ["YOLOX_MODEL"])
    result=run(annotation_path,model_path)
    s=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    Path(os.environ["GRABCUT_RESULT"]).write_text(s,encoding="utf-8")
    print(json.dumps(result,separators=(",",":"),allow_nan=False))
