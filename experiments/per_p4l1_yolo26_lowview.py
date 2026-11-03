"""PER-P4L1: OEM MuJoCo head-view GT vs existing YOLO26n/-seg, host ONLY.

Frozen before model inference in docs/per-p4l1-yolo26-lowview-prereg-2026-11-03.md.
No camera socket, actuator, SQLite, Qwen, raw media, weights or model changes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import sys
import time

from experiments.per_p5_yolo26_rknn_compat import MODELS, ULTRA_VERSION
from microduck_companion.sim_ball_segmentation_gt import (
    BallGTError, FRAME_H, FRAME_W, MIN_VISIBLE_PIXELS, visible_geom_bbox,
)
from microduck_companion.sim_vis_f_gt_preflight import _set_free_joint

IOU_THRESHOLD = .50
CONF_THRESHOLD = .25
NEGATIVE_STRONG_SCORE = .80
FIVE_CLASSES = frozenset((0, 15, 16, 32, 56))  # COCO person,cat,dog,ball,chair
SAMPLE_COUNT = 4


@dataclass(frozen=True)
class Case:
    name: str
    scene: str
    xy: tuple[float, float]
    yaw: float
    geom: str | None
    move_cube: bool = False


# Three source-only SIM-VIS-F positives; final negative has a new yaw.
CASES = (
    Case("cube_south_living", "scene_apartment.xml", (-2.80, -2.20),
         math.pi / 2, "obj_0_geom", True),
    Case("chair_near", "scene_apartment.xml", (-2.55, .05),
         0., "liv_chair_seat"),
    Case("pillar_cyan_near", "scene_vslam.xml", (3.40, -1.20),
         math.pi / 2, "vs_pil_c"),
    Case("empty_floor_yaw27", "scene.xml", (0., 0.),
         math.radians(27), None),
)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_weight(path: Path) -> None:
    if (path.is_symlink() or not path.is_file()
            or path.name not in MODELS
            or _sha_file(path) != MODELS[path.name]):
        raise BallGTError("untrusted official YOLO26 weight")


def box_iou(a, b) -> float:
    if (len(a) != 4 or len(b) != 4
            or any(not math.isfinite(float(x)) for x in (*a, *b))
            or a[2] <= a[0] or a[3] <= a[1]
            or b[2] <= b[0] or b[3] <= b[1]):
        raise BallGTError("invalid bounding-box geometry")
    ix = max(0., min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0., min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def mask_vs_rectangle(geom_mask, prediction_mask, box):
    """Compare the same matched proposal against independent geom-ID pixels."""
    import numpy as np

    truth = np.asarray(geom_mask)
    mask = np.asarray(prediction_mask)
    if (truth.shape != (FRAME_W, FRAME_H)
            or mask.shape != truth.shape
            or truth.dtype != np.bool_
            or not np.isfinite(mask).all()):
        raise BallGTError("unmatched or malformed segmentation mask")
    if (len(box) != 4 or any(not math.isfinite(float(v)) for v in box)):
        raise BallGTError("invalid predicted rectangle")
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        raise BallGTError("inverted predicted rectangle")
    x0, y0 = max(0, math.floor(x0)), max(0, math.floor(y0))
    x1, y1 = min(FRAME_H, math.ceil(x1)), min(FRAME_W, math.ceil(y1))
    rect = np.zeros_like(truth)
    rect[y0:y1, x0:x1] = True
    candidate = mask > .5

    def overlap(m):
        union = int(np.count_nonzero(np.logical_or(m, truth)))
        return (float(np.count_nonzero(np.logical_and(m, truth))) / union
                if union else 0.)
    return overlap(candidate), overlap(rect)


def render_case(scene_dir: Path, spec: Case):
    """Return RAM-only upright RGB + geom mask, with source independent of YOLO."""
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import Body, HOME_TRUNK_Z, World
    from mjlab_microduck.sim.camera import Camera, HEIGHT, WIDTH

    if (spec not in CASES or not scene_dir.is_dir() or scene_dir.is_symlink()
            or (WIDTH, HEIGHT) != (FRAME_W, FRAME_H)):
        raise BallGTError("unapproved OEM scene/camera")
    src = scene_dir / spec.scene
    if (spec.scene not in {c.scene for c in CASES}
            or not src.is_file() or src.is_symlink()):
        raise BallGTError("unapproved OEM scene file")
    world = World(src, 1)
    body = Body(world, 0)
    body.place(None, HOME_TRUNK_Z, 0.)
    model, data = world.model, world.data
    data.qpos[body.trunk:body.trunk + 2] = spec.xy
    data.qpos[body.trunk + 3:body.trunk + 7] = (
        math.cos(spec.yaw / 2), 0., 0., math.sin(spec.yaw / 2))
    mujoco.mj_forward(model, data)
    camera = Camera(model, "head_camera")
    try:
        mujoco.mj_forward(model, data)
        if spec.move_cube:
            rot = data.cam_xmat[camera.camera].reshape(3, 3)
            forward = -rot[:, 2].astype(float)
            norm = float(np.linalg.norm(forward[:2]))
            if not math.isfinite(norm) or norm < .55:
                raise BallGTError("invalid camera axis for preregistered cube")
            origin = data.cam_xpos[camera.camera, :2]
            xy = origin + forward[:2] / norm * .45
            _set_free_joint(model, data, "obj_0",
                            (float(xy[0]), float(xy[1]), 0.))
            mujoco.mj_forward(model, data)

        gid = -1
        if spec.geom:
            gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, spec.geom)
            if gid < 0:
                raise BallGTError("declared OEM geometry absent")
        else:
            floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
            extras = [j for j in range(model.ngeom)
                      if int(model.geom_bodyid[j]) == 0 and j != floor]
            if floor < 0 or extras:
                raise BallGTError("negative scene contains extra world geoms")
        at = float(data.time)
        pose_sha = hashlib.sha256(data.qpos.tobytes()).hexdigest()
        camera.renderer.update_scene(data, camera=camera.camera)
        rgb = camera.renderer.render().copy()
        camera.renderer.enable_segmentation_rendering()
        try:
            camera.renderer.update_scene(data, camera=camera.camera)
            seg = camera.renderer.render().copy()
        finally:
            camera.renderer.disable_segmentation_rendering()
        static = (float(data.time) == at
                  and hashlib.sha256(data.qpos.tobytes()).hexdigest() == pose_sha)
        if (not static or rgb.shape != (FRAME_H, FRAME_W, 3)
                or seg.shape != (FRAME_H, FRAME_W, 2)
                or not np.issubdtype(seg.dtype, np.integer)):
            raise BallGTError("incoherent OEM RGB/mask/time")
        upright = np.rot90(rgb, k=3)
        labels = np.rot90(seg, k=3)
        truth = ((labels[:, :, 0] == gid)
                 & (labels[:, :, 1] == int(mujoco.mjtObj.mjOBJ_GEOM)))
        bbox, pixels = (visible_geom_bbox(
            labels, geom_id=int(gid),
            geom_type=int(mujoco.mjtObj.mjOBJ_GEOM))
            if gid >= 0 else (None, 0))
        if (spec.geom and (bbox is None or pixels < MIN_VISIBLE_PIXELS)
                or not spec.geom and (pixels or bbox is not None)):
            raise BallGTError("GT visibility gate failed")
        record = {
            "case": spec.name, "scene": spec.scene,
            "target_geom": spec.geom, "visible_target_pixels": pixels,
            "gt_bbox": bbox, "static_qpos_time": static,
            "rgb_sha256": hashlib.sha256(upright.tobytes()).hexdigest(),
            "gt_mask_sha256": hashlib.sha256(truth.tobytes()).hexdigest(),
        }
        return upright, truth, record
    finally:
        camera.renderer.close()


def verify_preflight(rows):
    if (not isinstance(rows, list) or len(rows) != SAMPLE_COUNT
            or [r.get("case") for r in rows] != [s.name for s in CASES]):
        raise BallGTError("incomplete or reordered OEM test cases")
    for row, spec in zip(rows, CASES):
        box, pixels = row.get("gt_bbox"), row.get("visible_target_pixels")
        if row.get("static_qpos_time") is not True or row.get("target_geom") != spec.geom:
            raise BallGTError("unverified GT source or changing pose")
        if spec.geom:
            if (type(pixels) is not int or pixels < MIN_VISIBLE_PIXELS
                    or not isinstance(box, list) or len(box) != 4
                    or any(type(v) is not int for v in box)
                    or not (0 <= box[0] < box[2] <= FRAME_H
                            and 0 <= box[1] < box[3] <= FRAME_W)):
                raise BallGTError("positive GT invalid")
        elif box is not None or pixels != 0:
            raise BallGTError("negative geom invalid")
    return True


def _score_result(spec, record, truth, result, *, segment: bool):
    import numpy as np

    box_data = result.boxes
    boxes = [] if box_data is None else box_data.xyxy.cpu().numpy()
    labels = [] if box_data is None else box_data.cls.cpu().numpy()
    scores = [] if box_data is None else box_data.conf.cpu().numpy()
    if not (len(boxes) == len(labels) == len(scores) <= 100):
        raise BallGTError("malformed detection count")
    predictions = []
    for rect, label, score in zip(boxes, labels, scores):
        if (len(rect) != 4 or not np.isfinite(rect).all()
                or not math.isfinite(float(label))
                or not math.isfinite(float(score))
                or int(label) != label or not 0 <= int(label) < 80
                or not CONF_THRESHOLD <= score <= 1):
            raise BallGTError("nonfinite/invalid YOLO output")
        predictions.append({"xyxy": [float(v) for v in rect],
                            "coco_class_unverified": int(label),
                            "score_unverified": float(score)})
    if spec.geom is None:
        return {
            "case": spec.name, "region_iou50": None,
            "prediction_count": len(predictions),
            "five_class_claims": sum(
                p["coco_class_unverified"] in FIVE_CLASSES for p in predictions),
            "five_class_strong_claims": sum(
                p["coco_class_unverified"] in FIVE_CLASSES
                and p["score_unverified"] >= NEGATIVE_STRONG_SCORE
                for p in predictions),
            "mask_iou": None, "rectangle_mask_iou": None, "mask_better": None,
        }
    if record.get("gt_bbox") is None:
        raise BallGTError("missing independent positive region")
    matches = [
        (box_iou(record["gt_bbox"], p["xyxy"]), i)
        for i, p in enumerate(predictions)
    ]
    best_iou, index = max(matches, default=(0., -1))
    hit = best_iou >= IOU_THRESHOLD
    mask_iou = rect_iou = better = None
    if segment and hit:
        masks = (None if result.masks is None
                 else result.masks.data.cpu().numpy())
        if masks is None or len(masks) != len(predictions):
            raise BallGTError("missing source-aligned masks")
        mask_iou, rect_iou = mask_vs_rectangle(
            truth, masks[index], predictions[index]["xyxy"])
        better = mask_iou > rect_iou
    return {
        "case": spec.name, "region_iou50": bool(hit),
        "best_gt_bbox_iou": round(float(best_iou), 5),
        "matched_coco_class_unverified": (
            predictions[index]["coco_class_unverified"] if hit else None),
        "prediction_count": len(predictions),
        "mask_iou": round(mask_iou, 5) if mask_iou is not None else None,
        "rectangle_mask_iou": round(rect_iou, 5) if rect_iou is not None else None,
        "mask_better": better,
    }


def decision(a: list[dict], b: list[dict]):
    """A=YOLO26n, B=YOLO26n-seg; decision never creates a fact or permission."""
    names = [c.name for c in CASES]
    if (len(a) != SAMPLE_COUNT or len(b) != SAMPLE_COUNT
            or [x.get("case") for x in a] != names
            or [x.get("case") for x in b] != names):
        raise BallGTError("missing or reordered paired output")
    for x, y in zip(a, b):
        if not isinstance(x.get("prediction_count"), int) or not isinstance(y.get("prediction_count"), int):
            raise BallGTError("invalid output counts")
        if x["case"] != names[-1]:
            if type(x.get("region_iou50")) is not bool or type(y.get("region_iou50")) is not bool:
                raise BallGTError("invalid paired IoU verdict")
            if y["region_iou50"] and type(y.get("mask_better")) is not bool:
                raise BallGTError("missing segmentation quality verdict")
        elif any(type(z.get("five_class_strong_claims")) is not int
                 or z["five_class_strong_claims"] < 0 for z in (x, y)):
            raise BallGTError("invalid negative confidence diagnostic")
    hits_a = sum(x["region_iou50"] for x in a[:-1])
    hits_b = sum(x["region_iou50"] for x in b[:-1])
    wins = sum(x["mask_better"] is True for x in b[:-1])
    mask_fraction = wins / hits_b if hits_b else None
    strong = b[-1]["five_class_strong_claims"]
    eligible = (hits_b >= 2 and hits_b >= hits_a
                and mask_fraction is not None and mask_fraction >= .60
                and strong == 0)
    return {
        "detector_regions_at_iou50_of_3": hits_a,
        "segmenter_regions_at_iou50_of_3": hits_b,
        "segmenter_mask_wins_on_matched": wins,
        "segmenter_mask_win_fraction": mask_fraction,
        "strong_five_class_claims_on_empty_seg": strong,
        "lowview_candidate_gate_met": eligible,
        "status": ("PC_lowview_candidate_only_not_robot" if eligible
                   else "INSUFFICIENT_no_lowview_model_promotion"),
    }


def run(scene_dir: Path, weights_dir: Path | None, *, preflight_only: bool) -> dict:
    import numpy as np

    sources = [render_case(scene_dir, c) for c in CASES]
    records = [x[2] for x in sources]
    verify_preflight(records)
    report = {
        "study": "PER_P4L1_oem_lowview_model_pair", "geometry": records,
        "preflight_geometry_valid": True, "inference_cases": 0,
        "robot_or_npu_validated": False, "source_authenticated_for_robot": False,
        "camera_or_motor_commands": 0, "qwen_calls": 0, "memory_writes": 0,
        "pixels_or_weights_published": False,
        "model_rights": "AGPL-3.0/Enterprise, PC exploratory only",
    }
    if preflight_only:
        report["status"] = "GT_ONLY_NO_INFERENCE"
        return report
    if weights_dir is None:
        raise BallGTError("explicit verified model directory required")
    import ultralytics
    from ultralytics import YOLO
    from PIL import Image

    if ultralytics.__version__ != ULTRA_VERSION:
        raise BallGTError("unexpected Ultralytics runtime version")
    outputs = {}
    for model_name in MODELS:
        path = weights_dir / model_name
        verify_weight(path)
        yolo = YOLO(str(path))
        segment = model_name.endswith("-seg.pt")
        if yolo.task != ("segment" if segment else "detect"):
            raise BallGTError("unexpected pretrained YOLO model task")
        rows, durations = [], []
        for spec, (rgb, truth, record) in zip(CASES, sources):
            started = time.perf_counter()
            ans = yolo.predict(
                Image.fromarray(rgb), imgsz=640, conf=CONF_THRESHOLD,
                iou=IOU_THRESHOLD, max_det=100, device="cpu", verbose=False,
                retina_masks=segment)[0]
            durations.append((time.perf_counter() - started) * 1000.)
            rows.append(_score_result(spec, record, truth, ans, segment=segment))
            del ans
        outputs[model_name] = {
            "rows": rows, "host_ms_median": round(statistics.median(durations), 3),
            "host_ms_max": round(max(durations), 3),
            "host_peak_rss_kib_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "model_sha256": MODELS[model_name],
        }
        del yolo
    report["models"] = outputs
    report["inference_cases"] = len(CASES) * len(MODELS)
    report["decision"] = decision(
        outputs["yolo26n.pt"]["rows"], outputs["yolo26n-seg.pt"]["rows"])
    report["status"] = report["decision"]["status"]
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir", type=Path, required=True)
    parser.add_argument("--weights-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-static-oem-render", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_static_oem_render:
        parser.error("explicit host-only OEM render authorization required")
    try:
        if args.output.is_symlink() or args.output.exists():
            raise BallGTError("refuse to overwrite an evidence report")
        report = run(args.scene_dir, args.weights_dir,
                     preflight_only=args.preflight_only)
        args.output.write_text(json.dumps(report, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 0
    except (BallGTError, OSError, RuntimeError, ValueError) as exc:
        print(f"PER-P4L1 STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
