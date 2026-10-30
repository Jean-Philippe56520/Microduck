"""SIM-VIS-F: independent geometry-only visibility preflight for pinned OEM views.

Never runs YOLOX, ONNX, F2, robotd, mediad, Qwen or SQLite. No RGB frames are
exported. A preflight success only certifies a usable *test image oracle*.
The four scenes are preregistered in docs/ before any renderer invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from .sim_ball_segmentation_gt import (
    BallGTError, FRAME_H, FRAME_W, MIN_VISIBLE_PIXELS, visible_geom_bbox,
)

# Scene, robot (x, y), yaw, independently named OEM geom. Frozen before render.
SCENES = (
    ("cube_south_living", "scene_apartment.xml", (-2.80, -2.20),
     math.pi / 2, "obj_0_geom"),
    ("chair_near", "scene_apartment.xml", (-2.55, 0.05),
     0., "liv_chair_seat"),
    ("pillar_cyan_near", "scene_vslam.xml", (3.40, -1.20),
     math.pi / 2, "vs_pil_c"),
    ("ball_hidden_by_chair", "scene_apartment.xml", (-2.55, 0.05),
     0., "ball_0_geom"),
)
OCCLUDED = "ball_hidden_by_chair"
CUBE_FORWARD_M = .45
HIDDEN_BALL_XY = (-1.55, .05)
BLOCKER = "liv_chair_seat"


def _set_free_joint(model, data, body_name: str, xyz: tuple[float, ...]) -> None:
    import mujoco

    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if bid < 0 or int(model.body_jntnum[bid]) != 1:
        raise BallGTError("declared OEM object missing/freejoint changed")
    j = int(model.body_jntadr[bid])
    if int(model.jnt_type[j]) != int(mujoco.mjtJoint.mjJNT_FREE):
        raise BallGTError("declared OEM object is no longer a free joint")
    adr = int(model.jnt_qposadr[j])
    data.qpos[adr:adr + 3] = xyz
    data.qpos[adr + 3:adr + 7] = (1., 0., 0., 0.)


def _occlusion_ray(model, data, *, camera_id: int, target_id: int,
                   blocker_id: int) -> dict:
    """Read-only MuJoCo ray to the ball centre; never a robot ToF result."""
    import mujoco
    import numpy as np

    origin = data.cam_xpos[camera_id].copy()
    target = data.geom_xpos[target_id].copy()
    v = target - origin
    d = float(np.linalg.norm(v))
    if not math.isfinite(d) or d <= .10:
        raise BallGTError("invalid camera-to-target physical ray")
    geom = np.full(1, -1, dtype=np.int32)
    hit_dist = float(mujoco.mj_ray(
        model, data, origin, np.ascontiguousarray(v/d),
        None, 1, -1, geom,
    ))
    hit_id = int(geom[0])
    return {
        "first_hit_geom_id": hit_id,
        "expected_blocker_geom_id": blocker_id,
        "hit_distance_m": round(hit_dist, 6),
        "ball_centre_distance_m": round(d, 6),
        "intercepted_by_chair": hit_id == blocker_id and 0 < hit_dist < d,
    }


def inspect_case(scene_dir: Path, spec: tuple) -> dict:
    """Inspect one static optical pose without importing or running a model."""
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import Body, HOME_TRUNK_Z, World
    from mjlab_microduck.sim.camera import Camera, HEIGHT, WIDTH

    name, scene, xy, yaw, geom_name = spec
    if (not isinstance(scene_dir, Path) or scene_dir.is_symlink()
            or not scene_dir.is_dir() or (WIDTH, HEIGHT) != (FRAME_W, FRAME_H)):
        raise BallGTError("pinned OEM renderer/directory geometry unavailable")
    scene_path = scene_dir / scene
    if (scene_path.is_symlink() or not scene_path.is_file()
            or scene not in {"scene_apartment.xml", "scene_vslam.xml"}):
        raise BallGTError("unapproved or missing pinned OEM scene")
    world = World(scene_path, 1)
    body = Body(world, 0)
    body.place(None, HOME_TRUNK_Z, 0.0)
    data, model = world.data, world.model
    data.qpos[body.trunk:body.trunk+2] = xy
    data.qpos[body.trunk+3:body.trunk+7] = (
        math.cos(yaw/2), 0., 0., math.sin(yaw/2),
    )
    mujoco.mj_forward(model, data)

    camera = Camera(model, "head_camera")
    try:
        mujoco.mj_forward(model, data)  # OEM corrected head mount
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, geom_name)
        if gid < 0:
            raise BallGTError("preregistered OEM reference geom missing")
        if name == "cube_south_living":
            optical = data.cam_xmat[camera.camera].reshape(3, 3)
            forward = -optical[:, 2]
            f2 = forward[:2]
            norm = float(np.linalg.norm(f2))
            if not math.isfinite(norm) or norm < .55:
                raise BallGTError("OEM head camera axis unreliable")
            origin = data.cam_xpos[camera.camera, :2]
            location = origin + f2/norm*CUBE_FORWARD_M
            _set_free_joint(model, data, "obj_0",
                            (float(location[0]), float(location[1]), 0.))
        elif name == OCCLUDED:
            _set_free_joint(model, data, "ball_0",
                            (HIDDEN_BALL_XY[0], HIDDEN_BALL_XY[1], 0.))
        mujoco.mj_forward(model, data)
        at_time = float(data.time)
        q_hash = hashlib.sha256(data.qpos.tobytes()).hexdigest()
        start = time.perf_counter()
        camera.renderer.enable_segmentation_rendering()
        try:
            camera.renderer.update_scene(data, camera=camera.camera)
            segmented = camera.renderer.render().copy()
        finally:
            camera.renderer.disable_segmentation_rendering()
        render_ms = (time.perf_counter() - start) * 1000
        pose_static = (float(data.time) == at_time and
                       hashlib.sha256(data.qpos.tobytes()).hexdigest() == q_hash)
        if segmented.shape != (FRAME_H, FRAME_W, 2) or not np.issubdtype(
                segmented.dtype, np.integer):
            raise BallGTError("OEM segmentation dimensions/dtype changed")
        upright = np.rot90(segmented, k=3)  # same OEM rotation as SIM-VIS-B
        box, count = visible_geom_bbox(
            upright, geom_id=int(gid),
            geom_type=int(mujoco.mjtObj.mjOBJ_GEOM))
        report = {
            "case": name,
            "scene": scene,
            "source_geom": geom_name,
            "robot_xy": list(xy),
            "yaw_deg": round(math.degrees(yaw)),
            "geom_pixels": count,
            "geom_bbox_xyxy": box,
            "static_pose_confirmed": pose_static,
            "segmentation_sha256": hashlib.sha256(segmented.tobytes()).hexdigest(),
            "segmentation_host_ms": round(render_ms, 3),
            "raw_media_saved": False,
        }
        if name == OCCLUDED:
            blocker = mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_GEOM, BLOCKER)
            if blocker < 0:
                raise BallGTError("OEM chair geom missing")
            b_box, b_pixels = visible_geom_bbox(
                upright, geom_id=int(blocker),
                geom_type=int(mujoco.mjtObj.mjOBJ_GEOM))
            report["blocker_geom_pixels"] = b_pixels
            report["blocker_geom_bbox_xyxy"] = b_box
            report["ray"] = _occlusion_ray(
                model, data, camera_id=camera.camera,
                target_id=int(gid), blocker_id=int(blocker))
        return report
    finally:
        camera.renderer.close()


def assess_cases(cases: list[dict]) -> dict:
    """Fail-closed visibility quality gate, independent of any model scores."""
    if (type(cases) is not list or len(cases) != len(SCENES)
            or tuple(x.get("case") for x in cases) != tuple(s[0] for s in SCENES)):
        raise BallGTError("incomplete/reordered preregistered GT observations")
    rows: list[dict] = []
    for original in cases:
        name = original["case"]
        bad = []
        if original.get("static_pose_confirmed") is not True:
            bad.append("pose_changed")
        if (type(original.get("geom_pixels")) is not int or
                original["geom_pixels"] < 0):
            raise BallGTError("invalid geom pixel count")
        pixels = original["geom_pixels"]
        box = original.get("geom_bbox_xyxy")
        if (pixels == 0) != (box is None):
            bad.append("pixel_bbox_inconsistent")
        if name == OCCLUDED:
            if pixels != 0:
                bad.append("occluded_ball_visible")
            if (type(original.get("blocker_geom_pixels")) is not int or
                    original["blocker_geom_pixels"] < MIN_VISIBLE_PIXELS):
                bad.append("occluder_not_visible")
            ray = original.get("ray")
            if not isinstance(ray, dict) or ray.get("intercepted_by_chair") is not True:
                bad.append("chair_ray_not_proven")
        elif pixels < MIN_VISIBLE_PIXELS:
            bad.append("target_not_visible_enough")
        rows.append({
            "case": name,
            "valid_for_future_detector_evaluation": not bad,
            "failed_visibility_reasons": bad,
        })
    return {
        "preflight_gate_met": all(x["valid_for_future_detector_evaluation"]
                                  for x in rows),
        "cases_valid": sum(x["valid_for_future_detector_evaluation"] for x in rows),
        "cases_total": len(SCENES),
        "case_decisions": rows,
        "yolox_inference_attempted": 0,
        "sensor_or_robot_validated": False,
        "motor_commands_issued": 0,
    }


def evaluate(scene_dir: Path) -> dict:
    results = [inspect_case(scene_dir, case) for case in SCENES]
    return {
        "study": "SIM-VIS-F_preregistered_OEM_geometry_only",
        "evidence": assess_cases(results),
        "observations": results,
        "no_model_or_F2_loaded": True,
        "no_rgb_saved": True,
        "upstream_gitlinks_mutated": False,
        "interpretation": "preflight_only_not_object_detection",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-geometry-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_geometry_only:
        parser.error("explicit read-only geometry authorization required")
    try:
        if args.output.is_symlink() or args.output.exists():
            raise BallGTError("refuse to replace an existing evidence report")
        result = evaluate(args.scene_dir)
        args.output.write_text(json.dumps(result, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0  # valid diagnostic execution != visibility gate success
    except (BallGTError, ValueError, OSError, RuntimeError) as exc:
        print(f"SIM-VIS-F stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
