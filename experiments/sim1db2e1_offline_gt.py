"""SIM-1D/B2-E1: deferred independent MuJoCo geom-ID GT after duck-sim down.

Only frozen kinematics, exact OEM scene and corrected OEM Camera may make a
mask. First reproduce the original mediad UYVY SHA from the reconstructed RGB;
without byte identity the GT is UNKNOWN, even when a ball appears visible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from experiments.sim1db2e1_frame_match import B2GTError, validate_record
from microduck_companion.yolox_attention_candidates import _iou


def evaluate(scene_path: Path, report: dict, *, case: str) -> dict:
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import World
    from mjlab_microduck.sim.camera import Camera, to_uyvy

    expected = "scene_ball.xml" if case == "ball" else "scene.xml"
    if (case not in ("ball", "empty") or scene_path.name != expected
            or not scene_path.is_file() or scene_path.is_symlink()
            or type(report) is not dict
            or report.get("status") != "PASS_E1_MEDIAD_EXACT_POSE_CAPTURE_ONLY"
            or report.get("case") != case or report.get("completed_cycles") != 4
            or report.get("same_step_pixel_gt_verified") is not False
            or report.get("motor_commands_companion") != 0
            or report.get("experience_writes") != 0
            or report.get("image_persisted") is not False):
        raise B2GTError("STOP_E1_UNVERIFIED_REPLAY_INPUT")
    samples = report.get("samples")
    if type(samples) is not list or len(samples) != 4:
        raise B2GTError("STOP_E1_INVALID_REPLAY_COUNT")
    world = World(scene_path, 1)
    model, data = world.model, world.data
    camera = Camera(model, "head_camera")
    results = []
    used = set()
    previous_seq = 0
    try:
        geom = int(mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_GEOM, "ball_geom"))
        for index, sample in enumerate(samples):
            if type(sample) is not dict or sample.get("cycle") != index:
                raise B2GTError("STOP_E1_WRONG_SAMPLE_ORDER")
            row = sample.get("pose_sidecar")
            validate_record(row, case)
            if (row["render_seq"] in used or row["render_seq"] <= previous_seq
                    or sample["render_seq"] != row["render_seq"]):
                raise B2GTError("STOP_E1_DUPLICATE_REPLAY")
            used.add(row["render_seq"])
            previous_seq = row["render_seq"]
            if (len(row["qpos"]) != model.nq or len(row["qvel"]) != model.nv
                    or geom != (row["ball_geom_id"]
                                if row["ball_geom_id"] is not None else -1)):
                raise B2GTError("STOP_E1_MODEL_GEOMETRY_MISMATCH")
            qpos = np.asarray(row["qpos"], dtype=np.float64)
            qvel = np.asarray(row["qvel"], dtype=np.float64)
            if hashlib.sha256(qpos.tobytes()).hexdigest() != row["qpos_sha256"]:
                raise B2GTError("STOP_E1_QPOS_HASH_MISMATCH")
            data.qpos[:] = qpos
            data.qvel[:] = qvel
            data.time = row["sim_time_s"]
            mujoco.mj_forward(model, data)
            pos = data.cam_xpos[camera.camera]
            mat = data.cam_xmat[camera.camera].reshape(9)
            if (not np.allclose(pos, row["camera_pos_xyz"], atol=1e-7, rtol=0)
                    or not np.allclose(mat, row["camera_mat9"], atol=1e-7, rtol=0)):
                raise B2GTError("STOP_E1_CAMERA_POSE_NOT_REPRODUCED")
            # A completely new renderer is used ONLY after robotd shutdown.
            camera.renderer.update_scene(data, camera=camera.camera)
            rgb = camera.renderer.render().copy()
            if (rgb.shape != (360, 640, 3) or rgb.dtype != np.uint8
                    or hashlib.sha256(to_uyvy(rgb)).hexdigest()
                       != row["uyvy_sha256"]):
                raise B2GTError("STOP_E1_RGB_REPLAY_NOT_EXACT_MEDIAD_FRAME")
            # GT is independent of YOLOX and rendered at the SAME offline
            # scene state, after the exact RGB replay digest has passed.
            camera.renderer.enable_segmentation_rendering()
            try:
                camera.renderer.update_scene(data, camera=camera.camera)
                segmentation = camera.renderer.render().copy()
            finally:
                camera.renderer.disable_segmentation_rendering()
            if (segmentation.shape != (360, 640, 2)
                    or not np.issubdtype(segmentation.dtype, np.integer)):
                raise B2GTError("STOP_E1_INVALID_GEOM_SEGMENTATION")
            upright = np.rot90(segmentation, k=3)
            if geom >= 0:
                mask = ((upright[:, :, 0] == geom)
                        & (upright[:, :, 1] == int(mujoco.mjtObj.mjOBJ_GEOM)))
                ys, xs = np.where(mask)
                count = int(xs.size)
                bbox = [int(xs.min()), int(ys.min()),
                        int(xs.max())+1, int(ys.max())+1] if count else None
            else:
                count, bbox = 0, None
            if (case == "ball" and (bbox is None or count < 80)
                    or case == "empty" and (bbox is not None or count != 0)):
                raise B2GTError("STOP_E1_GT_VISIBILITY_WITNESS_FAILED")
            proposals = sample.get("regions_unverified")
            if (type(proposals) is not list or len(proposals) > 3
                    or any(type(p) is not dict or
                           set(p) != {"xyxy", "score", "untrusted_coco_class_index"}
                           for p in proposals)):
                raise B2GTError("STOP_E1_UNTRUSTED_REGION_SCHEMA")
            iou = (max((_iou(tuple(bbox), p["xyxy"])
                        for p in proposals), default=0.0)
                   if bbox is not None else None)
            results.append({
                "cycle": index, "render_seq": row["render_seq"],
                "sim_time_s": row["sim_time_s"],
                "mediad_uyvy_sha256": row["uyvy_sha256"],
                "replayed_rgb_exact_uyvy_sha256": True,
                "camera_pose_exact": True,
                "ball_visible_pixels": count,
                "ball_bbox_upright_xyxy": bbox,
                "region_count_unverified": len(proposals),
                "best_region_ball_gt_iou": round(iou, 6) if iou is not None else None,
                "localized_by_untrusted_region_iou50": (
                    iou >= 0.5 if iou is not None else False),
            })
    finally:
        camera.renderer.close()
    return {
        "status": "PASS_E1_OFFLINE_EXACT_FRAME_GT_REPLAY" if len(results) == 4
                  else "STOP_E1_OFFLINE_INCOMPLETE",
        "case": case, "matched_frames": len(results),
        "world_uninstrumented_after_shutdown": True,
        "instrumented_live_camera": True,
        "semantic_category_verified": False,
        "gt_provided_to_agent": False,
        "robot_validated": False, "v1_95_percent": False,
        "samples": results,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--case", choices=("ball", "empty"), required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        report = json.loads(args.input.read_text())
        result = evaluate(args.scene, report, case=args.case)
        if result["status"] != "PASS_E1_OFFLINE_EXACT_FRAME_GT_REPLAY":
            raise B2GTError("STOP_E1_INCOMPLETE")
    except (B2GTError, ValueError, TypeError, KeyError, OSError, RuntimeError,
            ImportError, IndexError, OverflowError) as exc:
        print(json.dumps({"status": "STOP_E1_OFFLINE_GT_NOT_PROVEN",
                          "reason": str(exc)[:160],
                          "accepted_matches": 0,
                          "semantic_category_verified": False}),
              file=sys.stderr)
        return 1
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "status": result["status"],
        "case": args.case,
        "exact_matches": result["matched_frames"],
        "ball_visibility": [
            s["ball_visible_pixels"] for s in result["samples"]],
        "best_region_gt_iou": [
            s["best_region_ball_gt_iou"] for s in result["samples"]],
        "semantic_category_verified": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
