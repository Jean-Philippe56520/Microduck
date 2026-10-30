"""PER-S1A: optical fore/background property diagnostic on pinned static OEM views.

Only predict_from_region(rgb, xyxy) may create candidate features: it has NO
access to MuJoCo segmentation/geom/class, memory, Qwen or a robot. The
independent mask is used by score_proposal *after* prediction, never to pick
a detector region. This is not a production perception module.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import statistics
import sys
import time

from experiments.per_s0_lowview_oem_region import Case, render_case, validate_preflight
from microduck_companion.sim_ball_segmentation_gt import BallGTError, FRAME_H, FRAME_W
from microduck_companion.yolox_attention_candidates import _iou, decode_candidates


CASES = (
    Case("red_cube_near", "scene_apartment.xml", (2.00, -.50),
         math.pi / 2, ("obj_0_geom",), "outside_five",
         free_body="obj_0", forward_m=.42, left_m=.05),
    Case("orange_ball_mid", "scene_apartment.xml", (1.85, -.55),
         math.pi / 2, ("ball_0_geom",), "known_ball",
         free_body="ball_0", forward_m=.55, left_m=-.10),
    Case("pink_ball_far", "scene_apartment.xml", (1.85, -.50),
         math.pi / 2, ("ball_2_geom",), "known_ball",
         free_body="ball_2", forward_m=.75, left_m=.12),
    Case("green_pillar_side", "scene_vslam.xml", (-3.30, 2.60),
         0., ("vs_pil_g",), "outside_five"),
    Case("blue_pillar_side", "scene_vslam.xml", (-4.05, -1.60),
         0., ("vs_pil_b",), "outside_five"),
    Case("armchair_side", "scene_apartment.xml", (-2.85, .15),
         0., ("liv_chair_seat", "liv_chair_back"), "outside_five"),
    Case("floor_empty_control", "scene.xml", (0., 0.),
         0., (), "empty_negative"),
)
POSITIVE_COUNT = 6
ROI_SEED_FRACTION = .40
RGB_DISTANCE_MAX = 50.
MIN_COMPONENT_PIXELS = 64
MIN_COMPONENT_FRACTION = .08
MAX_COMPONENT_FRACTION = .95
COLOUR_ERROR_MAX = 35.
MIN_REGION_IOU = .50
MIN_MASK_IOU = .55
MAX_SHAPE_ERROR = .20
MAX_FEATURE_P95_MS = 25.
MIN_BOXES = 4
MIN_COMPLETE = 3
MIN_IMPROVEMENTS = 2


def _validate_rgb(rgb):
    import numpy as np
    if (not isinstance(rgb, np.ndarray)
            or rgb.shape != (FRAME_W, FRAME_H, 3)
            or rgb.dtype != np.uint8):
        raise BallGTError("expected a single upright OEM RGB uint8 frame")


def _validated_pixel_box(box):
    if (type(box) is not tuple or len(box) != 4 or
            any(type(v) not in (float, int) or not math.isfinite(v)
                for v in box)):
        raise BallGTError("invalid candidate bbox")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= FRAME_H and 0 <= y0 < y1 <= FRAME_W):
        raise BallGTError("unbounded candidate bbox")
    from math import floor, ceil
    a, b, c, d = floor(x0), floor(y0), ceil(x1), ceil(y1)
    if c-a < 9 or d-b < 9:
        return None
    return a, b, c, d


def _shape_compactness(mask):
    """Unitless mask compactness, never a semantic shape label."""
    import cv2
    import numpy as np
    if (not isinstance(mask, np.ndarray) or mask.ndim != 2
            or mask.dtype != np.bool_ or not mask.any()):
        return None
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    perimeter = float(sum(cv2.arcLength(c, True) for c in contours))
    if perimeter <= 0 or not math.isfinite(perimeter):
        return None
    result = 4. * math.pi * int(mask.sum()) / (perimeter * perimeter)
    if not math.isfinite(result) or result < 0:
        return None
    return min(1., float(result))


def predict_from_region(rgb, box: tuple[float, float, float, float]):
    """Fixed cheap colour-seed foreground proposal; NO MuJoCo oracle argument.

    Returns (small numeric descriptor, ephemeral bool mask) or (None,None).
    A nonempty result is NEVER proof of correct segmentation or an object.
    """
    import cv2
    import numpy as np
    _validate_rgb(rgb)
    coords = _validated_pixel_box(box)
    if coords is None:
        return None, None
    x0,y0,x1,y1 = coords
    roi = rgb[y0:y1, x0:x1]
    h, w = roi.shape[:2]
    # Frozen centre 40 percent: no sample selected using truth/ground colour.
    xs = max(0, int(w * (1. - ROI_SEED_FRACTION)/2.))
    xe = min(w, max(xs+1, int(w * (1. + ROI_SEED_FRACTION)/2.)))
    ys = max(0, int(h * (1. - ROI_SEED_FRACTION)/2.))
    ye = min(h, max(ys+1, int(h * (1. + ROI_SEED_FRACTION)/2.)))
    seed = np.median(roi[ys:ye, xs:xe], axis=(0,1))
    deviation = roi.astype(np.float32) - seed.astype(np.float32)
    coarse = (np.sum(deviation*deviation, axis=2)
              <= RGB_DISTANCE_MAX * RGB_DISTANCE_MAX).astype(np.uint8)
    kernel = np.ones((3,3), dtype=np.uint8)
    smooth = cv2.morphologyEx(coarse, cv2.MORPH_OPEN, kernel)
    smooth = cv2.morphologyEx(smooth, cv2.MORPH_CLOSE, kernel)
    n, components, stats, _ = cv2.connectedComponentsWithStats(smooth, connectivity=8)
    chosen = int(components[h//2, w//2])
    if not 1 <= chosen < n:
        return None, None
    count = int(stats[chosen, cv2.CC_STAT_AREA])
    fraction = count / (h*w)
    if (count < MIN_COMPONENT_PIXELS or
            not MIN_COMPONENT_FRACTION <= fraction <= MAX_COMPONENT_FRACTION):
        return None, None
    local = components == chosen
    mask = np.zeros((FRAME_W,FRAME_H), dtype=np.bool_)
    mask[y0:y1, x0:x1] = local
    compactness = _shape_compactness(mask)
    if compactness is None:
        return None, None
    colour = tuple(float(x) for x in np.median(roi[local], axis=0))
    if not all(math.isfinite(v) for v in colour):
        return None, None
    descriptor = {
        "color_rgb_median_unverified": [round(x,3) for x in colour],
        "shape_compactness_2d_unverified": round(compactness,6),
        "area_pixels_in_region_unverified": count,
        "candidate_fraction_inside_box": round(float(fraction),6),
        "confidence_of_color_and_shape_known": False,
    }
    return descriptor, mask


def _median_colour(rgb, mask):
    import numpy as np
    if not mask.any():
        return None
    return np.median(rgb[mask], axis=0)


def _colour_distance(a, b):
    import numpy as np
    if a is None or b is None:
        return None
    return float(np.linalg.norm(
        np.asarray(a,dtype=np.float32)-np.asarray(b,dtype=np.float32)))


def _mask_iou(a, b):
    import numpy as np
    if a.shape != b.shape or a.dtype != np.bool_ or b.dtype != np.bool_:
        raise BallGTError("invalid mask alignment")
    both = int(np.logical_and(a,b).sum())
    union = int(np.logical_or(a,b).sum())
    return both/union if union else 0.


def score_proposal(name: str, rgb, oracle_mask, candidates: list[dict]):
    """Comparison AFTER non-oracle prediction; only top1 can feed features."""
    import numpy as np
    _validate_rgb(rgb)
    if (not isinstance(oracle_mask, np.ndarray)
            or oracle_mask.shape != rgb.shape[:2]
            or oracle_mask.dtype != np.bool_
            or type(candidates) is not list or len(candidates) > 3):
        raise BallGTError("invalid scoring inputs")
    empty = name == "floor_empty_control"
    if empty != (not oracle_mask.any()):
        raise BallGTError("independent mask does not match declared case")
    if not candidates:
        return {
            "case":name,"had_region":False,
            "top1_iou": None if empty else 0.,
            "descriptor_produced":False,
            "mask_iou":None,"colour_error_rgb":None,
            "shape_compactness_error":None,
            "rectangle_mask_iou":None,"rectangle_colour_error_rgb":None,
            "feature_host_ms":0.,
            "top3_best_iou":None if empty else 0.,
            "candidate_class_unverified":None,
        }
    if any(type(c) is not dict or
           set(c) != {"xyxy","score","untrusted_coco_class_index"}
           for c in candidates):
        raise BallGTError("unexpected/untrusted YOLOX region layout")
    first = candidates[0]
    boxes = [_validated_pixel_box(c["xyxy"]) for c in candidates]
    if any(b is None for b in boxes):
        raise BallGTError("model offered degenerate bbox")
    # Oracle is now used ONLY for scoring. It never selects the top1 region.
    x0,y0,x1,y1 = boxes[0]
    rect_mask = np.zeros(oracle_mask.shape, dtype=np.bool_)
    rect_mask[y0:y1,x0:x1] = True
    before = time.perf_counter()
    descriptor, predicted_mask = predict_from_region(rgb, first["xyxy"])
    feature_ms = (time.perf_counter()-before)*1000.
    gt_colour = _median_colour(rgb,oracle_mask)
    rectangle_colour = _median_colour(rgb,rect_mask)
    rectangle_error = _colour_distance(rectangle_colour, gt_colour)
    predicted_error = (_colour_distance(
        descriptor["color_rgb_median_unverified"], gt_colour)
        if descriptor else None)
    oracle_compactness = _shape_compactness(oracle_mask)
    predicted_compactness_error = (
        abs(descriptor["shape_compactness_2d_unverified"]
            - oracle_compactness)
        if descriptor and oracle_compactness is not None else None
    )
    gt_ys,gt_xs = np.where(oracle_mask)
    gt_box = (float(gt_xs.min()),float(gt_ys.min()),
              float(gt_xs.max()+1),float(gt_ys.max()+1)) if not empty else None
    return {
        "case":name, "had_region":True,
        "top1_iou":round(float(_iou(gt_box,first["xyxy"])),6)
            if gt_box else None,
        "top3_best_iou":round(
            max((_iou(gt_box,c["xyxy"]) for c in candidates),default=0.),6)
            if gt_box else None,
        "candidate_class_unverified":first["untrusted_coco_class_index"],
        "candidate_confidence_unverified":first["score"],
        "descriptor_produced":descriptor is not None,
        "mask_iou":round(_mask_iou(predicted_mask,oracle_mask),6)
            if descriptor else None,
        "colour_error_rgb":round(predicted_error,4)
            if predicted_error is not None else None,
        "shape_compactness_error":round(predicted_compactness_error,6)
            if predicted_compactness_error is not None else None,
        "rectangle_mask_iou":round(_mask_iou(rect_mask,oracle_mask),6),
        "rectangle_colour_error_rgb":round(rectangle_error,4)
            if rectangle_error is not None else None,
        "feature_host_ms":round(feature_ms,3),
    }


def assess(rows: list[dict]):
    """Predeclared conjunction. A green test run is NOT a good feature model."""
    import numpy as np
    if (type(rows) is not list or
            tuple(x.get("case") for x in rows) != tuple(s.name for s in CASES)):
        raise BallGTError("not the full/reordered preregistered S1A cohort")
    seen = rows[:POSITIVE_COUNT]
    negative = rows[-1]
    if negative["had_region"] or negative["descriptor_produced"]:
        negative_bad = True
    else:
        negative_bad = False
    matched = 0
    complete = 0
    better_mask = 0
    better_colour = 0
    false_confident = 0
    durations = []
    for entry in seen:
        overlap = entry.get("top1_iou")
        if (type(overlap) not in (float,int) or not math.isfinite(overlap)
                or not 0 <= overlap <= 1
                or type(entry.get("descriptor_produced")) is not bool
                or type(entry.get("feature_host_ms")) not in (float,int)
                or not math.isfinite(entry["feature_host_ms"])
                or entry["feature_host_ms"] < 0):
            raise BallGTError("invalid area/time or output")
        durations.append(entry["feature_host_ms"])
        if overlap >= MIN_REGION_IOU:
            matched += 1
        elif entry["descriptor_produced"]:
            false_confident += 1
        if not entry["descriptor_produced"]:
            continue
        fields = ["mask_iou","colour_error_rgb",
                  "shape_compactness_error","rectangle_mask_iou",
                  "rectangle_colour_error_rgb"]
        if any(type(entry.get(k)) not in (float,int)
               or not math.isfinite(entry[k])
               or entry[k]<0 for k in fields):
            raise BallGTError("nonfinite/unverified feature score")
        if not 0 <= entry["mask_iou"] <= 1:
            raise BallGTError("mask IoU outside range")
        if overlap >= MIN_REGION_IOU:
            if (entry["mask_iou"] >= MIN_MASK_IOU
                    and entry["colour_error_rgb"] <= COLOUR_ERROR_MAX
                    and entry["shape_compactness_error"] <= MAX_SHAPE_ERROR):
                complete += 1
            if entry["mask_iou"] > entry["rectangle_mask_iou"]:
                better_mask += 1
            if entry["colour_error_rgb"] < entry["rectangle_colour_error_rgb"]:
                better_colour += 1
    p95 = float(np.percentile(durations,95))
    value = (matched>=MIN_BOXES and complete>=MIN_COMPLETE
             and better_mask>=MIN_IMPROVEMENTS
             and better_colour>=MIN_IMPROVEMENTS
             and false_confident==0 and not negative_bad
             and p95<=MAX_FEATURE_P95_MS)
    return {
        "positive_cases":len(seen),"top1_region_iou50":matched,
        "complete_mask_colour_compactness":complete,
        "mask_better_than_full_rectangle":better_mask,
        "colour_better_than_full_rectangle":better_colour,
        "false_confident_when_not_located":false_confident,
        "negative_has_any_proposal":bool(negative_bad),
        "feature_cpu_host_p95_ms":round(p95,3),
        "functional_value_gate_met":bool(value),
        "status":"PC_candidate_ONLY_not_real_robot" if value
        else "STOP_no_auto_colour_or_shape_to_memory",
    }


def run(scene_dir: Path, model: Path|None, *, preflight_only: bool):
    import numpy as np
    from PIL import Image

    images, masks, geometry = [], [], []
    for case in CASES:
        rgb, record, gt = render_case(
            scene_dir, case, authorized_cases=CASES, with_target_mask=True)
        images.append(rgb)
        masks.append(gt)
        geometry.append(record)
    ready = validate_preflight(geometry, authorized_cases=CASES)
    report = {
        "study":"PER-S1A_cautious_foreground_colour_geometry_host",
        "oem_camera_sim_only":True,
        "geometry":geometry,
        "preflight_gate_met":ready,
        "model_inference_count":0,
        "private_media_or_weights_published":False,
        "motor_robot_Qwen_SQLite_writes":0,
        "oem_code_or_gitlinks_mutated":False,
    }
    if not ready:
        report["status"]="STOP_geometry_not_valid"
        report["functional_value_gate_met"]=None
        return report
    if preflight_only:
        report["status"]="geometry_preflight_only_NO_ONNX"
        report["functional_value_gate_met"]=None
        return report
    if model is None:
        raise BallGTError("pinned YOLOX ONNX required")
    from microduck_companion.cata_yolox_categories import (
        prepare_image, validate_model_file)
    import onnxruntime as ort

    validate_model_file(model)
    options=ort.SessionOptions()
    options.intra_op_num_threads=2
    options.inter_op_num_threads=1
    session=ort.InferenceSession(str(model),sess_options=options,
                                 providers=["CPUExecutionProvider"])
    if len(session.get_inputs())!=1 or session.get_inputs()[0].name!="images":
        raise BallGTError("unexpected ONNX model input")
    result=[]
    inference=[]
    for scene,rgb,gt in zip(CASES,images,masks):
        frame=BytesIO()
        Image.fromarray(rgb).save(frame,format="JPEG",quality=95)
        inp=prepare_image(frame.getvalue(),mode="original")
        t0=time.perf_counter()
        output=session.run(None,{"images":inp})
        inference.append((time.perf_counter()-t0)*1000.)
        if len(output)!=1:
            raise BallGTError("expected one original YOLOX output")
        candidates=decode_candidates(output[0],width=FRAME_H,
                                     height=FRAME_W,max_results=3)
        result.append(score_proposal(scene.name,rgb,gt,candidates))
    report["model_inference_count"]=len(result)
    report["observations"]=result
    report["decision"]=assess(result)
    report["status"]=report["decision"]["status"]
    report["functional_value_gate_met"]=report["decision"]["functional_value_gate_met"]
    report["inference_host_p50_ms"]=round(float(np.median(inference)),3)
    report["inference_host_p95_ms"]=round(float(np.percentile(inference,95)),3)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir",type=Path,required=True)
    parser.add_argument("--model",type=Path)
    parser.add_argument("--preflight-only",action="store_true")
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--authorize-static-oem-render",action="store_true")
    args=parser.parse_args(argv)
    if not args.authorize_static_oem_render:
        parser.error("explicit static OEM source-only render permission required")
    try:
        if args.report.exists() or args.report.is_symlink():
            raise BallGTError("refuse to overwrite prior evidence")
        report=run(args.scene_dir,args.model,preflight_only=args.preflight_only)
        args.report.write_text(json.dumps(report,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps(report,sort_keys=True))
        return 0 # CI green != functional value gate met.
    except (BallGTError,ValueError,RuntimeError,OSError) as exc:
        print(f"PER-S1A STOP {type(exc).__name__}: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
