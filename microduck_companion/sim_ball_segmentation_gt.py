"""SIM-VIS-B: static OEM MuJoCo RGB + independent segmentation vs frozen YOLOX.

Two declared views of the same pinned apartment: three balls BEHIND the
head camera (negative), and one ground ball in front at 0.55 m (positive).
No robotd, motor command, physics step, new weights, memory or raw media log.
GT is a geom-ID mask from the SAME frozen MuJoCo snapshot as RGB, never from
YOLOX output. This is a controlled optical test, not real-world perception.
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
    MODEL_SHA256, MIN_SCORE, SIZE, prepare_image, validate_model_file,
)
from .cata2_bbox_eval import Box, MATCH_IOU, decode_boxes, iou

BALL_NAMES = ("ball_0", "ball_1", "ball_2")
POSITIVE_DISTANCE_M = 0.55
NEGATIVE_DISTANCE_M = 0.70
ROBOT_YAW_RAD = math.pi / 2
MIN_VISIBLE_PIXELS = 80
FRAME_W = 640
FRAME_H = 360


class BallGTError(RuntimeError):
    pass


def visible_geom_bbox(segmentation, *, geom_id: int, geom_type: int) -> tuple[list[int] | None, int]:
    """Object-id ground truth, excluding background and every non-geom ID.

    MuJoCo Renderer segmentation: [object_id, object_type] int32 at each
    pixel. Upper pixel limits are exclusive, exactly like Cat-A2a boxes.
    """
    import numpy as np
    seg = np.asarray(segmentation)
    if (seg.shape != (FRAME_W, FRAME_H, 2)
            or not np.issubdtype(seg.dtype, np.integer)
            or type(geom_id) is not int or geom_id < 0
            or type(geom_type) is not int):
        raise BallGTError("invalid upright segmentation geometry/type")
    mask = (seg[:, :, 0] == geom_id) & (seg[:, :, 1] == geom_type)
    ys, xs = np.where(mask)
    pixels = int(xs.size)
    if not pixels:
        return None, 0
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1,
            int(ys.max()) + 1], pixels


def compare_boxes(ground_truth: list[Box], proposals: tuple[Box, ...]) -> dict:
    """Greedy one-to-one matching at Cat-A2a's predeclared 0.50 IoU."""
    detected = [p for p in proposals if p.category == "sports_ball"]
    pairs = sorted(
        ((iou(g, p), gi, pi) for gi, g in enumerate(ground_truth)
         for pi, p in enumerate(detected)),
        reverse=True,
    )
    used_gt: set[int] = set()
    used_proposal: set[int] = set()
    matched = []
    for overlap, gi, pi in pairs:
        if overlap < MATCH_IOU or gi in used_gt or pi in used_proposal:
            continue
        used_gt.add(gi)
        used_proposal.add(pi)
        matched.append(round(float(overlap), 6))
    return {
        "ground_truth_count": len(ground_truth),
        "ball_proposal_count": len(detected),
        "matched_iou_at_least_0_50": len(matched),
        "matched_ious": sorted(matched, reverse=True),
        "false_negatives": len(ground_truth) - len(matched),
        "false_positives": len(detected) - len(matched),
    }


def _rig_scene(scene_path: Path, case: str):
    """Reuse OEM World, Body and head Camera; change ONLY static qpos in RAM."""
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import World, Body, HOME_TRUNK_Z
    from mjlab_microduck.sim.camera import Camera

    if case not in ("negative_behind", "positive_floor_ahead"):
        raise BallGTError("not a declared test case")
    if (not isinstance(scene_path, Path) or scene_path.is_symlink()
            or scene_path.name != "scene_apartment.xml"
            or not scene_path.is_file()):
        raise BallGTError("pinned OEM apartment entrypoint required")

    world = World(scene_path, 1)
    body = Body(world, 0)
    body.place(None, HOME_TRUNK_Z, 0.0)
    q = world.data.qpos
    q[body.trunk + 3:body.trunk + 7] = [
        math.cos(ROBOT_YAW_RAD / 2), 0.0, 0.0,
        math.sin(ROBOT_YAW_RAD / 2),
    ]
    mujoco.mj_forward(world.model, world.data)
    camera = Camera(world.model, "head_camera")
    mujoco.mj_forward(world.model, world.data)  # OEM camera correction
    optical = world.data.cam_xmat[camera.camera].reshape(3, 3)
    forward = -optical[:, 2].astype(float)
    horizontal = forward[:2] / float(np.linalg.norm(forward[:2]))
    if (not np.isfinite(horizontal).all() or not 0.55 <= np.linalg.norm(forward[:2]) <= 1.0):
        camera.renderer.close()
        raise BallGTError("camera not approximately forward-facing")
    sideways = np.array([-horizontal[1], horizontal[0]])
    origin = world.data.cam_xpos[camera.camera, :2].copy()

    geom_ids = {}
    for i, name in enumerate(BALL_NAMES):
        gid = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM, name + "_geom")
        bid = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_BODY, name)
        if gid < 0 or bid < 0 or int(world.model.body_jntnum[bid]) != 1:
            camera.renderer.close()
            raise BallGTError("missing OEM free ball")
        joint = int(world.model.body_jntadr[bid])
        if (int(world.model.jnt_type[joint]) != int(mujoco.mjtJoint.mjJNT_FREE)
                or int(world.model.geom_type[gid]) != int(mujoco.mjtGeom.mjGEOM_SPHERE)):
            camera.renderer.close()
            raise BallGTError("OEM ball geometry is no longer dynamic sphere")
        addr = int(world.model.jnt_qposadr[joint])
        if case == "positive_floor_ahead" and i == 0:
            xy = origin + horizontal * POSITIVE_DISTANCE_M
        else:
            xy = origin - horizontal * (NEGATIVE_DISTANCE_M + 0.1 * i)
            xy += sideways * (i - 1) * 0.12
        q[addr:addr+3] = [float(xy[0]), float(xy[1]), 0.0]
        q[addr+3:addr+7] = [1.0, 0.0, 0.0, 0.0]
        geom_ids[name] = int(gid)
    mujoco.mj_forward(world.model, world.data)
    return world, camera, geom_ids


def _one_case(scene_path: Path, case: str, session) -> dict:
    import mujoco
    import numpy as np
    from PIL import Image

    world, camera, ids = _rig_scene(scene_path, case)
    try:
        model, data = world.model, world.data
        before_qpos = hashlib.sha256(data.qpos.tobytes()).hexdigest()
        before_time = float(data.time)
        camera.renderer.update_scene(data, camera=camera.camera)
        rgb = camera.renderer.render().copy()
        camera.renderer.enable_segmentation_rendering()
        try:
            camera.renderer.update_scene(data, camera=camera.camera)
            segmentation = camera.renderer.render().copy()
        finally:
            camera.renderer.disable_segmentation_rendering()
        if (rgb.shape != (FRAME_H, FRAME_W, 3)
                or segmentation.shape != (FRAME_H, FRAME_W, 2)
                or not np.issubdtype(segmentation.dtype, np.integer)):
            raise BallGTError("RGB/segmentation outputs are not aligned")
        if (float(data.time) != before_time
                or hashlib.sha256(data.qpos.tobytes()).hexdigest() != before_qpos):
            raise BallGTError("world advanced or pose mutated between renders")

        # Camera mount is 90 degrees clockwise, precisely as the OEM path.
        rgb_upright = np.rot90(rgb, k=3)
        seg_upright = np.rot90(segmentation, k=3)
        boxes = []
        gt = []
        geom_type = int(mujoco.mjtObj.mjOBJ_GEOM)
        for name, gid in ids.items():
            bounds, pixels = visible_geom_bbox(
                seg_upright, geom_id=gid, geom_type=geom_type
            )
            boxes.append({"name": name, "pixels": pixels, "bbox_xyxy": bounds})
            if bounds is not None:
                gt.append(Box("sports_ball", tuple(bounds)))
        visible_target = next(x for x in boxes if x["name"] == "ball_0")
        if case == "positive_floor_ahead":
            if (visible_target["pixels"] < MIN_VISIBLE_PIXELS
                    or visible_target["bbox_xyxy"] is None):
                raise BallGTError("predeclared ground ball is not measurably visible")
        elif any(x["pixels"] for x in boxes):
            raise BallGTError("negative witness contains visible ball pixels")

        frame = BytesIO()
        Image.fromarray(rgb_upright).save(frame, format="JPEG", quality=95)
        sample = prepare_image(frame.getvalue(), mode="original")
        start = time.perf_counter()
        output = session.run(None, {"images": sample})[0]
        infer_ms = (time.perf_counter() - start) * 1000
        proposals = decode_boxes(output, width=FRAME_H, height=FRAME_W)
        outcome = compare_boxes(gt, proposals)
        outcome.update({
            "case": case,
            "ball_segmentation": boxes,
            "all_target_proposals": len(proposals),
            "inference_ms_cpu": round(infer_ms, 3),
            "rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
            "segmentation_sha256": hashlib.sha256(segmentation.tobytes()).hexdigest(),
            "static_world_time_s": before_time,
            "camera_intrinsics_source": "pinned_OEM_MJCF",
        })
        return outcome
    finally:
        camera.renderer.close()


def evaluate(scene_path: Path, model_path: Path) -> dict:
    import onnxruntime as ort
    from mjlab_microduck.sim.camera import WIDTH, HEIGHT
    if (WIDTH, HEIGHT) != (FRAME_W, FRAME_H):
        raise BallGTError("OEM camera geometry drift")
    validate_model_file(model_path)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise BallGTError("unreviewed Cat-A ONNX interface")

    cases = [
        _one_case(scene_path, "negative_behind", session),
        _one_case(scene_path, "positive_floor_ahead", session),
    ]
    return {
        "lot": "SIM-VIS-B_static_OEM_scene_ball_gt",
        "source": "pinned_microduck_rl_camera_and_mujoco_renderer",
        "status": "independent_simulator_pixel_gt_two_predeclared_views",
        "model_sha256": MODEL_SHA256,
        "model_score_threshold": MIN_SCORE,
        "match_iou_threshold": MATCH_IOU,
        "predeclared_positive_distance_m": POSITIVE_DISTANCE_M,
        "predeclared_robot_yaw_deg": 90,
        "cases": cases,
        "ball_classification_gate_met": (
            cases[0]["false_positives"] == 0
            and cases[1]["matched_iou_at_least_0_50"] >= 1
            and cases[1]["false_negatives"] == 0
        ),
        "scope": "two_controlled_static_views_not_independent_generalization",
        "real_time_physics_or_robotd_validated": False,
        "mediad_path_validated": False,
        "physical_camera_or_NPU_validated": False,
        "motor_commands_issued": 0,
        "qwen_or_sqlite_calls": 0,
        "private_images_or_raw_renders_published": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-path", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--authorize-static-oem-render", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_static_oem_render:
        parser.error("explicit synthetic render opt-in required")
    try:
        result = evaluate(args.scene_path, args.model_path)
        if args.output.exists() or args.output.is_symlink():
            raise BallGTError("refusing to overwrite a prior experiment")
        args.output.write_text(json.dumps(result, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
    except (BallGTError, ValueError, RuntimeError, OSError) as exc:
        print(f"SIM-VIS-B insufficient: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
