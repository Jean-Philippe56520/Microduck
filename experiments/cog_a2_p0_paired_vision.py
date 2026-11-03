"""COG-A2-P0: two frozen OEM optical views; not physical rolling.

Experimental PC/MuJoCo-only harness, preregistered before model inference.
No robotd/mediad, mv command, training, second camera, motor, SQLite, F2,
Qwen, image output, private media, property learning or new OEM code.
Ground truth is used ONLY for evaluation, never region selection.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import statistics
import sys
import time

from microduck_companion.sim_ball_segmentation_gt import (
    BallGTError, FRAME_H, FRAME_W, MIN_VISIBLE_PIXELS, visible_geom_bbox,
)
from microduck_companion.sim_vis_f_gt_preflight import _set_free_joint
from microduck_companion.yolox_attention_candidates import _iou, decode_candidates

SHIFT_M = .10
FORWARD_M = .60
IOU_PASS = .50
MOVE_MIN_PX = 20.
STILL_MAX_PX = 5.
DELTA_ERROR_MAX_PX = 25.
BALL_COCO_INDEX = 32  # 'sports ball' COCO hypothesis, NEVER a fact.
FRAME_CENTRE_MAX = (FRAME_H, FRAME_W)


@dataclass(frozen=True)
class PairSpec:
    name: str
    scene: str
    robot_xy: tuple[float, float]
    yaw_rad: float
    body_name: str | None
    geom_name: str | None
    role: str


CASES = (
    PairSpec("flat_ball_shift", "scene_ball.xml", (0., 0.), 0.,
             "ball", "ball_geom", "positive"),
    PairSpec("office_ball_shift", "scene_apartment.xml", (2.15, -.55),
             math.pi / 2, "ball_1", "ball_1_geom", "positive"),
    PairSpec("flat_ball_still", "scene_ball.xml", (0., 0.), 0.,
             "ball", "ball_geom", "still_negative"),
    PairSpec("empty_floor", "scene.xml", (0., 0.), 0.,
             None, None, "empty_negative"),
    PairSpec("camera_yaw_confounded", "scene_ball.xml", (0., 0.), 0.,
             "ball", "ball_geom", "camera_negative"),
)
CASE_NAMES = tuple(s.name for s in CASES)
ALLOWED_SCENES = frozenset(s.scene for s in CASES)


def _center(box: list[int] | tuple[float, ...]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2., (box[1] + box[3]) / 2.)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _box_ok(box: object) -> bool:
    return (type(box) is list and len(box) == 4
            and all(type(v) is int for v in box)
            and 0 <= box[0] < box[2] <= FRAME_H
            and 0 <= box[1] < box[3] <= FRAME_W)


def _fixed_camera(a: dict, b: dict) -> tuple[bool, float]:
    import numpy as np

    xyz_a, xyz_b = np.asarray(a["camera_xyz"]), np.asarray(b["camera_xyz"])
    mat_a, mat_b = np.asarray(a["camera_rot"]), np.asarray(b["camera_rot"])
    if (xyz_a.shape != (3,) or xyz_b.shape != (3,)
            or mat_a.shape != (3, 3) or mat_b.shape != (3, 3)
            or not np.isfinite(xyz_a).all() or not np.isfinite(xyz_b).all()
            or not np.isfinite(mat_a).all() or not np.isfinite(mat_b).all()):
        raise BallGTError("invalid OEM camera pose")
    relative = mat_a.T @ mat_b
    angle = math.acos(float(np.clip((np.trace(relative) - 1.) / 2., -1., 1.)))
    fixed = (float(np.linalg.norm(xyz_a - xyz_b)) <= .002 and angle <= .01)
    return fixed, round(angle, 6)


def _render_current(camera, data, *, geom_id: int | None) -> tuple[object, dict]:
    import mujoco
    import numpy as np

    t = float(data.time)
    qhash = hashlib.sha256(data.qpos.tobytes()).hexdigest()
    camera.renderer.update_scene(data, camera=camera.camera)
    rgb = camera.renderer.render().copy()
    camera.renderer.enable_segmentation_rendering()
    try:
        camera.renderer.update_scene(data, camera=camera.camera)
        seg = camera.renderer.render().copy()
    finally:
        camera.renderer.disable_segmentation_rendering()
    if (rgb.shape != (FRAME_H, FRAME_W, 3)
            or seg.shape != (FRAME_H, FRAME_W, 2)
            or not np.issubdtype(seg.dtype, np.integer)):
        raise BallGTError("OEM RGB/segmentation geometry changed")
    # OEM frame rotation, not a second camera or sensor.
    upright = np.rot90(rgb, k=3)
    mask = np.rot90(seg, k=3)
    bbox, pixels = ((None, 0) if geom_id is None else visible_geom_bbox(
        mask, geom_id=geom_id, geom_type=int(mujoco.mjtObj.mjOBJ_GEOM)))
    return upright, {
        "bbox": bbox, "geom_pixels": pixels,
        "state_frozen": t == float(data.time)
                        and qhash == hashlib.sha256(data.qpos.tobytes()).hexdigest(),
        "camera_xyz": [float(x) for x in data.cam_xpos[camera.camera]],
        "camera_rot": data.cam_xmat[camera.camera].reshape(3, 3).tolist(),
        "rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
        "mask_sha256": hashlib.sha256(seg.tobytes()).hexdigest(),
    }


def render_case(scene_dir: Path, spec: PairSpec) -> tuple[tuple[object, object], dict]:
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import Body, HOME_TRUNK_Z, World
    from mjlab_microduck.sim.camera import Camera, HEIGHT, WIDTH

    if (spec not in CASES or (WIDTH, HEIGHT) != (FRAME_W, FRAME_H)
            or not isinstance(scene_dir, Path) or scene_dir.is_symlink()
            or not scene_dir.is_dir() or spec.scene not in ALLOWED_SCENES):
        raise BallGTError("unapproved OEM low-camera scene")
    src = scene_dir / spec.scene
    if src.is_symlink() or not src.is_file():
        raise BallGTError("pinned OEM scene unavailable")
    world = World(src, 1)
    body = Body(world, 0)
    body.place(None, HOME_TRUNK_Z, 0.)
    model, data = world.model, world.data
    data.qpos[body.trunk:body.trunk + 2] = spec.robot_xy
    data.qpos[body.trunk + 3:body.trunk + 7] = (
        math.cos(spec.yaw_rad / 2.), 0., 0., math.sin(spec.yaw_rad / 2.))
    mujoco.mj_forward(model, data)
    camera = Camera(model, "head_camera")
    try:
        mujoco.mj_forward(model, data)
        gid = None
        forward_xy = side_xy = origin_xy = None
        if spec.geom_name is not None:
            gid = mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_GEOM, spec.geom_name)
            if gid < 0:
                raise BallGTError("OEM pinned ball geom missing")
            rot = data.cam_xmat[camera.camera].reshape(3, 3)
            forward = -rot[:, 2]
            length = float(np.linalg.norm(forward[:2]))
            if not math.isfinite(length) or length < .55:
                raise BallGTError("invalid low camera horizontal optical axis")
            forward_xy = forward[:2] / length
            side_xy = np.asarray([-forward_xy[1], forward_xy[0]])
            origin_xy = data.cam_xpos[camera.camera, :2].copy()

            def place_ball(lateral):
                xy = origin_xy + forward_xy * FORWARD_M + side_xy * lateral
                _set_free_joint(model, data, spec.body_name,
                                (float(xy[0]), float(xy[1]), .035))
                mujoco.mj_forward(model, data)
            place_ball(-SHIFT_M)

        first_rgb, first = _render_current(camera, data, geom_id=gid)
        if spec.role == "positive":
            place_ball(SHIFT_M)
        elif spec.role == "camera_negative":
            yaw = spec.yaw_rad + math.radians(20.)
            data.qpos[body.trunk + 3:body.trunk + 7] = (
                math.cos(yaw / 2.), 0., 0., math.sin(yaw / 2.))
            mujoco.mj_forward(model, data)
        second_rgb, second = _render_current(camera, data, geom_id=gid)
        camera_fixed, angle = _fixed_camera(first, second)
        box_a, box_b = first["bbox"], second["bbox"]
        gt_delta = (_distance(_center(box_a), _center(box_b))
                    if box_a is not None and box_b is not None else None)
        return (first_rgb, second_rgb), {
            "case": spec.name, "role": spec.role, "scene": spec.scene,
            "views": [first, second], "camera_fixed": camera_fixed,
            "camera_rotation_rad": angle, "gt_delta_px": gt_delta,
            "f2_or_motor_executed": False, "physical_rolling_observed": False,
        }
    finally:
        camera.renderer.close()


def validate_preflight(rows: list[dict]) -> bool:
    """Check paired independent MuJoCo GT BEFORE any model is loaded."""
    if (type(rows) is not list or len(rows) != len(CASES)
            or tuple(row.get("case") for row in rows) != CASE_NAMES):
        raise BallGTError("incomplete or reordered preregistered cases")
    for spec, row in zip(CASES, rows):
        if (row.get("role") != spec.role or row.get("scene") != spec.scene
                or type(row.get("views")) is not list
                or len(row["views"]) != 2
                or row.get("f2_or_motor_executed") is not False
                or row.get("physical_rolling_observed") is not False):
            raise BallGTError("invalid evidence source or view count")
        a, b = row["views"]
        for v in (a, b):
            if (type(v.get("state_frozen")) is not bool
                    or v["state_frozen"] is not True
                    or type(v.get("geom_pixels")) is not int
                    or v["geom_pixels"] < 0):
                raise BallGTError("unverified frozen OEM geometry")
        fixed, angle = _fixed_camera(a, b)
        if (row.get("camera_fixed") is not fixed
                or type(row.get("camera_rotation_rad")) not in (int, float)
                or not math.isclose(row["camera_rotation_rad"], angle, abs_tol=1e-5)):
            raise BallGTError("camera pose claims disagree with geometry")
        boxes = [v["bbox"] for v in (a, b)]
        if spec.role == "empty_negative":
            if any(v["geom_pixels"] != 0 or v["bbox"] is not None
                   for v in (a, b)):
                raise BallGTError("empty target falsely detected by GT")
        elif (not all(_box_ok(v["bbox"]) and
                       v["geom_pixels"] >= MIN_VISIBLE_PIXELS for v in (a, b))):
            return False
        if spec.role == "camera_negative":
            if fixed or angle < .15:
                raise BallGTError("camera-confound negative lacks camera rotation")
        elif not fixed:
            return False
        delta = (_distance(_center(boxes[0]), _center(boxes[1]))
                 if boxes[0] is not None and boxes[1] is not None else None)
        if row.get("gt_delta_px") != delta:
            raise BallGTError("falsified GT displacement field")
        if spec.role == "positive" and (delta is None or delta < MOVE_MIN_PX):
            return False
        if spec.role == "still_negative" and (delta is None or delta >= STILL_MAX_PX):
            return False
    return True


def _safe_proposal(raw) -> dict | None:
    # No GT information is passed to the unmodified existing decoder.
    proposals = decode_candidates(raw, width=FRAME_H, height=FRAME_W,
                                  max_results=1)
    return proposals[0] if proposals else None


def score_pair(spec: PairSpec, oracle: dict, proposals: tuple[dict | None, dict | None]) -> dict:
    """Scoring ONLY; the candidate decoder has no access to oracle GT."""
    if (spec not in CASES or oracle.get("case") != spec.name
            or type(proposals) is not tuple or len(proposals) != 2):
        raise BallGTError("wrong paired optical score inputs")
    for item in proposals:
        if item is None:
            continue
        if (type(item) is not dict or set(item) != {
            "xyxy", "score", "untrusted_coco_class_index"
        } or type(item["xyxy"]) not in (tuple, list)
                or len(item["xyxy"]) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in item["xyxy"])
                or not (0 <= item["xyxy"][0] < item["xyxy"][2] <= FRAME_H
                        and 0 <= item["xyxy"][1] < item["xyxy"][3] <= FRAME_W)
                or type(item["score"]) not in (int, float)
                or not math.isfinite(item["score"]) or not 0 <= item["score"] <= 1
                or type(item["untrusted_coco_class_index"]) is not int
                or not 0 <= item["untrusted_coco_class_index"] < 80):
            raise BallGTError("invalid untrusted candidate")
    box_a, box_b = (v["bbox"] for v in oracle["views"])
    ious = [
        float(_iou(item["xyxy"], box)) if item is not None and box is not None
        else 0. for item, box in zip(proposals, (box_a, box_b))
    ]
    model_delta = (
        _distance(_center(proposals[0]["xyxy"]), _center(proposals[1]["xyxy"]))
        if all(item is not None for item in proposals) else None
    )
    gt_delta = oracle["gt_delta_px"]
    # Compare the 2D *vector*, not just its magnitude: opposite directions
    # are not evidence of tracking a displaced target.
    delta_err = None
    if (all(item is not None for item in proposals)
            and box_a is not None and box_b is not None):
        ax, ay = _center(proposals[0]["xyxy"])
        bx, by = _center(proposals[1]["xyxy"])
        gx0, gy0 = _center(box_a)
        gx1, gy1 = _center(box_b)
        delta_err = math.hypot((bx - ax) - (gx1 - gx0),
                               (by - ay) - (gy1 - gy0))
    both_localized = all(v >= IOU_PASS for v in ious)
    candidate_move = bool(
        model_delta is not None and model_delta >= MOVE_MIN_PX)
    good_positive = bool(
        spec.role == "positive" and oracle["camera_fixed"]
        and both_localized and candidate_move and delta_err is not None
        and delta_err <= DELTA_ERROR_MAX_PX
    )
    return {
        "case": spec.name, "role": spec.role,
        "model_proposal_count": sum(item is not None for item in proposals),
        "untrusted_sports_ball_coco_count": sum(
            item is not None and item["untrusted_coco_class_index"] == BALL_COCO_INDEX
            for item in proposals),
        "best_iou_per_view": [round(v, 6) for v in ious],
        "candidate_centre_delta_px": round(model_delta, 4)
            if model_delta is not None else None,
        "gt_centre_delta_px": round(gt_delta, 4)
            if gt_delta is not None else None,
        "delta_abs_error_px": round(delta_err, 4)
            if delta_err is not None else None,
        "candidate_move_ge_20_px": candidate_move,
        "both_views_iou50": both_localized,
        "positive_optical_gate": good_positive,
        "physical_motion_or_identity_verified": False,
        "category_or_effect_promoted": False,
    }


def gate(scored: list[dict], geometry: list[dict]) -> dict:
    """PC optical value threshold, no property nor robot qualification."""
    if (type(scored) is not list or len(scored) != 4
            or [x.get("case") for x in scored] != list(CASE_NAMES[:4])
            or validate_preflight(geometry) is not True):
        raise BallGTError("incomplete or invalid source-bound optical result")
    if any(x.get("physical_motion_or_identity_verified") is not False
           or x.get("category_or_effect_promoted") is not False
           for x in scored):
        raise BallGTError("forbidden physical promotion")
    passes = sum(x.get("positive_optical_gate") is True for x in scored[:2])
    still_good = scored[2].get("candidate_move_ge_20_px") is False
    empty_good = scored[3].get("untrusted_sports_ball_coco_count") == 0
    value = passes >= 1 and still_good and empty_good
    return {
        "paired_optical_positive_count": passes,
        "paired_optical_positive_total": 2,
        "still_false_move": not still_good,
        "empty_untrusted_ball_hypotheses": scored[3]["untrusted_sports_ball_coco_count"],
        "camera_confounded_refused": True,  # No inference called for N3.
        "optic_value_gate_met": value,
        "status": "PC_optical_delta_gate_met_not_A2_or_rolling"
                  if value else "STOP_no_paired_optical_property_claim",
        "a2_four_positives_eight_negatives_verified": False,
        "rolling_property_verified": False,
        "motor_commands_issued": 0,
        "memory_writes": 0,
    }


def evaluate(scene_dir: Path, model: Path | None, *, preflight_only: bool) -> dict:
    frames = []
    geometry = []
    try:
        for spec in CASES:
            images, record = render_case(scene_dir, spec)
            frames.append(images)
            geometry.append(record)
        valid = validate_preflight(geometry)
        report = {
            "study": "COG_A2_P0_static_OEM_paired_optical_delta",
            "baseline_main_sha": "0ddc9862cc5476d88b2a3b27cdfce19231b1110e",
            "preflight_geometry_valid": valid,
            "geometry": geometry,
            "images_saved": False,
            "model_inferences": 0,
            "motor_commands": 0, "memory_writes": 0,
            "qwen_calls": 0, "f2_calls": 0,
            "robot_or_npu_validated": False,
            "physical_rolling_or_identity_verified": False,
        }
        if not valid:
            report["status"] = "STOP_invalid_geometry"
            return report
        if preflight_only:
            report["status"] = "geometry_only_no_model"
            return report
        if model is None:
            raise BallGTError("pinned model required after geometry preflight")
        import numpy as np
        from PIL import Image
        import onnxruntime as ort
        from microduck_companion.cata_yolox_categories import (
            prepare_image, validate_model_file,
        )

        validate_model_file(model)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(model), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        if len(session.get_inputs()) != 1 or session.get_inputs()[0].name != "images":
            raise BallGTError("wrong frozen YOLOX input")
        scores, timings = [], []
        for spec, pair, row in zip(CASES, frames, geometry):
            if spec.role == "camera_negative":
                continue  # Explicitly refuse confounded pose, zero inference.
            proposals = []
            for frame in pair:
                jpeg = BytesIO()
                Image.fromarray(frame).save(jpeg, format="JPEG", quality=95)
                tensor = prepare_image(jpeg.getvalue(), mode="original")
                t0 = time.perf_counter()
                output = session.run(None, {"images": tensor})
                timings.append((time.perf_counter() - t0) * 1000.)
                if len(output) != 1:
                    raise BallGTError("wrong YOLOX output count")
                proposals.append(_safe_proposal(output[0]))
            scores.append(score_pair(spec, row, tuple(proposals)))
        report["model_inferences"] = len(timings)
        report["scores"] = scores
        report["decision"] = gate(scores, geometry)
        report["status"] = report["decision"]["status"]
        report["host_model_inference_ms_median"] = round(statistics.median(timings), 3)
        return report
    finally:
        frames.clear()  # No file-backed raw RGB/mask assets.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-static-oem-render", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_static_oem_render:
        parser.error("explicit read-only static OEM render authorization required")
    try:
        if args.output.exists() or args.output.is_symlink():
            raise BallGTError("do not overwrite previous evidence")
        report = evaluate(args.scene_dir, args.model, preflight_only=args.preflight_only)
        args.output.write_text(json.dumps(report, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 0  # A successful procedure does NOT mean the quality gate passed.
    except (BallGTError, ValueError, RuntimeError, OSError) as exc:
        print("COG-A2-P0 STOP: " + repr(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
