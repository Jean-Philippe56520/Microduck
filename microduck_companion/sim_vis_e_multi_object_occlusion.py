"""SIM-VIS-E: preregistered multi-object OEM MuJoCo region diagnostics.

Tests old YOLOX attention candidate geometry on previously untested pinned
OEM objects and a REAL geometrically blocked ball. A static optical test,
NOT a detector shipped to mediad or a permission to move the physical robot.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys
import time

from .cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, prepare_image, validate_model_file,
)
from .perception import DETECTION_CONFIDENCE
from .sim_ball_segmentation_gt import (
    BallGTError, FRAME_H, FRAME_W, MIN_VISIBLE_PIXELS, visible_geom_bbox,
)
from .sim_vis_d_new_scenes_f2_fixture import mock_f2_from_regions
from .yolox_attention_candidates import _iou, decode_candidates

# Freeze geometry BEFORE any new ONNX inference. Names/meshes belong to pinned
# microduck_rl, NOT Companion. Same 640x360 OEM head camera with 90 deg rotation.
CASES = (
    ("box_corridor", "scene_apartment.xml", "obj_0_geom"),
    ("chair_living", "scene_apartment.xml", "liv_chair_seat"),
    ("pillar_yellow", "scene_vslam.xml", "vs_pil_y"),
    ("ball_beside_chair", "scene_apartment.xml", "ball_0_geom"),
    ("ball_behind_chair", "scene_apartment.xml", "ball_0_geom"),
)
NON_BALL = ("box_corridor", "chair_living", "pillar_yellow")
POSITIVES = NON_BALL + ("ball_beside_chair",)
OCCLUDED = "ball_behind_chair"
LIVING_ROBOT_XY = (-2.90, 0.05)
VSLAM_ROBOT_XY = (1.90, -4.10)
SIDE_BALL_XY = (-1.70, 0.45)
HIDDEN_BALL_XY = (-1.70, 0.05)
CUBE_FORWARD_M = 0.52
BLOCKER_GEOM = "liv_chair_seat"


def ray_blocker(model, data, *, camera_xyz, target_xyz, blocker_id: int) -> dict:
    """Independent MuJoCo ray witness: chair must hit before the ball.

    The ray is solely a fixture oracle, NEVER a ToF reading or safety fact.
    """
    import mujoco
    import numpy as np

    origin = np.asarray(camera_xyz, dtype=np.float64)
    target = np.asarray(target_xyz, dtype=np.float64)
    if (origin.shape != (3,) or target.shape != (3,)
            or not np.isfinite(origin).all() or not np.isfinite(target).all()
            or type(blocker_id) is not int or blocker_id < 0):
        raise BallGTError("invalid occlusion witness input")
    displacement = target - origin
    distance = float(np.linalg.norm(displacement))
    if not math.isfinite(distance) or distance < .1:
        raise BallGTError("invalid target distance for ray witness")
    out_geom = np.full(1, -1, dtype=np.int32)
    hit_distance = float(mujoco.mj_ray(
        model, data, origin,
        np.ascontiguousarray(displacement / distance),
        None, 1, -1, out_geom,
    ))
    hit = int(out_geom[0])
    return {
        "first_hit_geom_id": hit,
        "expected_blocker_geom_id": blocker_id,
        "first_hit_m": round(hit_distance, 6),
        "target_center_m": round(distance, 6),
        "chair_physically_intercepts_ray": (
            hit == blocker_id and 0 < hit_distance < distance
        ),
    }


def _place_free_body(model, data, *, body_name: str, xyz) -> None:
    import mujoco
    import numpy as np

    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if bid < 0 or int(model.body_jntnum[bid]) != 1:
        raise BallGTError("preregistered OEM free body absent")
    joint = int(model.body_jntadr[bid])
    if int(model.jnt_type[joint]) != int(mujoco.mjtJoint.mjJNT_FREE):
        raise BallGTError("preregistered OEM body not free joint")
    vector = np.asarray(xyz, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise BallGTError("invalid preregistered object position")
    adr = int(model.jnt_qposadr[joint])
    data.qpos[adr:adr+3] = vector
    data.qpos[adr+3:adr+7] = [1., 0., 0., 0.]


def _static_scene(scene_dir: Path, case: str):
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import Body, HOME_TRUNK_Z, World
    from mjlab_microduck.sim.camera import Camera

    spec = next((item for item in CASES if item[0] == case), None)
    if spec is None:
        raise BallGTError("unregistered test case")
    if (not isinstance(scene_dir, Path) or scene_dir.is_symlink()
            or not scene_dir.is_dir()):
        raise BallGTError("approved OEM scene directory missing")
    scene_path = scene_dir / spec[1]
    if scene_path.is_symlink() or not scene_path.is_file():
        raise BallGTError("required pinned OEM scene missing")
    world = World(scene_path, 1)
    body = Body(world, 0)
    body.place(None, HOME_TRUNK_Z, 0.)
    yaw = 0.
    if case == "box_corridor":
        yaw = math.pi / 2
    elif case == "pillar_yellow":
        yaw = math.pi / 2
        world.data.qpos[body.trunk:body.trunk+2] = VSLAM_ROBOT_XY
    else:
        world.data.qpos[body.trunk:body.trunk+2] = LIVING_ROBOT_XY
    world.data.qpos[body.trunk+3:body.trunk+7] = [
        math.cos(yaw/2), 0., 0., math.sin(yaw/2),
    ]
    mujoco.mj_forward(world.model, world.data)
    camera = Camera(world.model, "head_camera")
    try:
        mujoco.mj_forward(world.model, world.data)
        gid = mujoco.mj_name2id(
            world.model, mujoco.mjtObj.mjOBJ_GEOM, spec[2])
        if gid < 0:
            raise BallGTError("declared OEM target geometry absent")
        if case == "box_corridor":
            mat = world.data.cam_xmat[camera.camera].reshape(3, 3)
            axis = -mat[:, 2].astype(float)
            horizontal = axis[:2]
            norm = float(np.linalg.norm(horizontal))
            if not math.isfinite(norm) or norm < .55:
                raise BallGTError("OEM head camera forward axis invalid")
            xy = world.data.cam_xpos[camera.camera, :2]
            position = xy + horizontal / norm * CUBE_FORWARD_M
            _place_free_body(
                world.model, world.data, body_name="obj_0",
                xyz=[float(position[0]), float(position[1]), 0.],
            )
        elif case in ("ball_beside_chair", OCCLUDED):
            xy = HIDDEN_BALL_XY if case == OCCLUDED else SIDE_BALL_XY
            _place_free_body(
                world.model, world.data, body_name="ball_0",
                xyz=[xy[0], xy[1], 0.],
            )
        mujoco.mj_forward(world.model, world.data)
        return world, camera, gid
    except Exception:
        camera.renderer.close()
        raise


def one_case(scene_dir: Path, case: str, session) -> dict:
    import mujoco
    import numpy as np
    from PIL import Image

    world, camera, gid = _static_scene(scene_dir, case)
    try:
        model, data = world.model, world.data
        old_time = float(data.time)
        old_qpos = hashlib.sha256(data.qpos.tobytes()).hexdigest()
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
                or not np.issubdtype(seg.dtype, np.integer)
                or data.time != old_time
                or hashlib.sha256(data.qpos.tobytes()).hexdigest() != old_qpos):
            raise BallGTError("OEM RGB/GT were not acquired at same static state")

        rotated_rgb = np.rot90(rgb, k=3)
        rotated_seg = np.rot90(seg, k=3)
        target_box, target_pixels = visible_geom_bbox(
            rotated_seg, geom_id=int(gid),
            geom_type=int(mujoco.mjtObj.mjOBJ_GEOM),
        )
        witness = None
        if case == OCCLUDED:
            chair = mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_GEOM, BLOCKER_GEOM)
            if chair < 0:
                raise BallGTError("OEM occluder missing")
            chair_box, chair_pixels = visible_geom_bbox(
                rotated_seg, geom_id=int(chair),
                geom_type=int(mujoco.mjtObj.mjOBJ_GEOM),
            )
            witness = ray_blocker(
                model, data,
                camera_xyz=data.cam_xpos[camera.camera],
                target_xyz=data.geom_xpos[gid],
                blocker_id=int(chair),
            )
            witness.update({
                "occluder_visible_pixels": chair_pixels,
                "occluder_bbox_xyxy": chair_box,
                "ball_mask_empty": target_pixels == 0,
            })
            if (target_pixels != 0 or chair_pixels < MIN_VISIBLE_PIXELS
                    or not witness["chair_physically_intercepts_ray"]):
                raise BallGTError(
                    "occlusion GT/ray witness invalid; do NOT reinterpret")
        elif target_pixels < MIN_VISIBLE_PIXELS or target_box is None:
            raise BallGTError("preregistered target not visibly measurable")

        buf = BytesIO()
        Image.fromarray(rotated_rgb).save(buf, format="JPEG", quality=95)
        tensor = prepare_image(buf.getvalue(), mode="original")
        t0 = time.perf_counter()
        output = session.run(None, {"images": tensor})[0]
        infer_ms = round((time.perf_counter() - t0) * 1000, 3)
        caps = {}
        top3: list[dict] = []
        for cap in (1, 3, 5):
            start = time.perf_counter()
            proposals = decode_candidates(
                output, width=FRAME_H, height=FRAME_W, max_results=cap)
            elapsed = round((time.perf_counter() - start)*1000, 3)
            overlap = (
                max((_iou(tuple(target_box), z["xyxy"])
                     for z in proposals), default=0.)
                if target_box is not None else None)
            caps[str(cap)] = {
                "region_count": len(proposals),
                "best_target_iou": round(float(overlap), 6)
                    if overlap is not None else None,
                "target_located_iou50": (
                    overlap is not None and overlap >= .5),
                "decode_ms_host": elapsed,
            }
            if cap == 3:
                top3 = proposals
        f2 = mock_f2_from_regions(top3)
        return {
            "case": case,
            "oem_scene": next(y[1] for y in CASES if y[0] == case),
            "target_gt_visible_pixels": target_pixels,
            "target_gt_bbox": target_box,
            "geom_ray_occlusion_oracle": witness,
            "regions_top1_top3_top5": caps,
            "top3_untrusted_scores": [z["score"] for z in top3],
            "f2_fixture": f2,
            "inference_host_ms": infer_ms,
            "raw_rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
            "gt_seg_sha256": hashlib.sha256(seg.tobytes()).hexdigest(),
            "static_world_time_s": old_time,
            "known_category_verified": False,
            "robot_sensor_authenticated": False,
            "motor_commands_issued": 0,
        }
    finally:
        camera.renderer.close()


def evaluate(scene_dir: Path, model_path: Path) -> dict:
    import onnxruntime as ort
    from mjlab_microduck.sim.camera import WIDTH, HEIGHT

    if (WIDTH, HEIGHT) != (FRAME_W, FRAME_H):
        raise BallGTError("OEM camera dimensions drifted")
    validate_model_file(model_path)
    opt = ort.SessionOptions()
    opt.intra_op_num_threads = 1
    opt.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=opt,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise BallGTError("YOLOX ONNX interface changed")

    cases = [one_case(scene_dir, case, session) for case, _, _ in CASES]
    scored = {c["case"]: c for c in cases}
    nonball_hits = sum(
        scored[case]["regions_top1_top3_top5"]["3"]["target_located_iou50"]
        for case in NON_BALL
    )
    positive_hits = sum(
        scored[case]["regions_top1_top3_top5"]["3"]["target_located_iou50"]
        for case in POSITIVES
    )
    negative = scored[OCCLUDED]["geom_ray_occlusion_oracle"]
    return {
        "lot": "SIM-VIS-E_OEM_multi_object_physical_occlusion_prereg",
        "model_sha256": MODEL_SHA256,
        "min_score_frozen": MIN_SCORE,
        "f2_mock_threshold_frozen": DETECTION_CONFIDENCE,
        "nonball_hits_top3_iou50": nonball_hits,
        "all_positive_hits_top3_iou50": positive_hits,
        "nonball_gate_met": nonball_hits >= 1,
        "positive_gate_met": positive_hits >= 2,
        "physical_occlusion_witness_valid": (
            negative["chair_physically_intercepts_ray"]
            and negative["ball_mask_empty"]
            and negative["occluder_visible_pixels"] >= MIN_VISIBLE_PIXELS
        ),
        "preregistered_gate_met": (
            nonball_hits >= 1 and positive_hits >= 2
            and negative["chair_physically_intercepts_ray"]
            and negative["ball_mask_empty"]
            and negative["occluder_visible_pixels"] >= MIN_VISIBLE_PIXELS
        ),
        "cases": cases,
        "sensor_semantics_or_RKNN_validated": False,
        "new_f2_policy_added": False,
        "actual_robot_or_motor_tested": False,
        "motor_commands_issued": 0,
        "true_mediad_frames": 0,
        "qwen_calls": 0,
        "persistent_sqlite_writes": 0,
        "raw_media_published": False,
        "result_scope": "static_pinned_OEM_renderer_and_mock_F2_only",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene-dir", required=True, type=Path)
    ap.add_argument("--model-path", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--authorize-readonly-oem-views", action="store_true")
    args = ap.parse_args(argv)
    if not args.authorize_readonly_oem_views:
        ap.error("explicit frozen-scene experiment opt-in required")
    try:
        result = evaluate(args.scene_dir, args.model_path)
        if args.output.exists() or args.output.is_symlink():
            raise BallGTError("do not replace an existing report")
        args.output.write_text(
            json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        # A valid experiment can FAIL its frozen detector transfer gate.
        return 0
    except (BallGTError, ValueError, RuntimeError, TypeError, OSError) as e:
        print(f"SIM-VIS-E stopped: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
