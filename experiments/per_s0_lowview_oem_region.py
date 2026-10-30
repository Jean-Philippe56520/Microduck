"""PER-S0: frozen OEM low-view GT versus existing YOLOX class/region decoders.

Host-only test, source-only MuJoCo, zero robotd/mediad, model edits, SQLite,
Qwen, camera socket, action, image storage or new visual component.
All cases are fixed in docs/per-s0-lowview-unknown-regions-2026-10-30.md.
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
    BallGTError, FRAME_H, FRAME_W, MIN_VISIBLE_PIXELS,
)
from microduck_companion.yolox_attention_candidates import _iou, decode_candidates


@dataclass(frozen=True)
class Case:
    name: str
    scene: str
    robot_xy: tuple[float, float]
    yaw: float
    geoms: tuple[str, ...]
    role: str
    free_body: str | None = None
    forward_m: float = 0.
    left_m: float = 0.


# Frozen before any PER-S0 model inference. Never tune these after results.
CASES = (
    Case("office_blue_cube", "scene_apartment.xml", (2.15, -.55),
         math.pi / 2, ("obj_1_geom",), "outside_five",
         free_body="obj_1", forward_m=.50),
    Case("living_plant", "scene_apartment.xml", (-2.15, -2.70),
         0., ("liv_plant",), "outside_five"),
    Case("living_sofa", "scene_apartment.xml", (-2.65, -.95),
         math.pi, ("liv_sofa_seat", "liv_sofa_back"), "outside_five"),
    Case("vslam_cyan_pillar", "scene_vslam.xml", (2.20, -.60),
         0., ("vs_pil_c",), "outside_five"),
    Case("office_green_ball", "scene_apartment.xml", (2.15, -.55),
         math.pi / 2, ("ball_1_geom",), "known_ball",
         free_body="ball_1", forward_m=.72, left_m=.10),
    Case("empty_floor", "scene.xml", (0., 0.),
         0., (), "empty_negative"),
)
ALLOWED_SCENES = frozenset(x.scene for x in CASES)
OUTSIDE = tuple(x.name for x in CASES if x.role == "outside_five")
ALL_NAMES = tuple(x.name for x in CASES)
MIN_OUTSIDE_TOP3 = 2
MIN_INCREMENTAL_TOP3 = 1
STRONG_NEGATIVE_SCORE = .80
MIN_MATCH_IOU = .50


def _ids_and_target(segmentation, geoms: tuple[int, ...], geom_type: int):
    """Use one independent mask for the UNION of all target MuJoCo geoms."""
    import numpy as np

    arr = np.asarray(segmentation)
    if (arr.shape != (FRAME_W, FRAME_H, 2)
            or not np.issubdtype(arr.dtype, np.integer)
            or type(geoms) is not tuple
            or any(type(g) is not int or g < 0 for g in geoms)):
        raise BallGTError("segmentation target contract invalid")
    if not geoms:
        return None, 0
    mask = (np.isin(arr[:, :, 0], list(geoms))
            & (arr[:, :, 1] == geom_type))
    ys, xs = np.nonzero(mask)
    pixels = int(xs.size)
    if pixels == 0:
        return None, 0
    return [int(xs.min()), int(ys.min()),
            int(xs.max()) + 1, int(ys.max()) + 1], pixels


def validate_preflight(cases: list[dict]) -> bool:
    """Fail closed before loading any model. No statistics from invalid GT."""
    if (type(cases) is not list
            or [v.get("case") for v in cases] != list(ALL_NAMES)):
        raise BallGTError("missing/reordered PER-S0 geometry cases")
    for original, row in zip(CASES, cases):
        if (type(row.get("valid_geometry")) is not bool
                or type(row.get("pose_static")) is not bool
                or type(row.get("geom_pixels")) is not int
                or row["geom_pixels"] < 0
                or row.get("role") != original.role):
            raise BallGTError("invalid or forged geometry report")
        bbox = row.get("geom_bbox_xyxy")
        if original.role == "empty_negative":
            if row["geom_pixels"] != 0 or bbox is not None:
                raise BallGTError("target inferred in empty negative")
        else:
            if ((row["geom_pixels"] == 0) != (bbox is None)
                    or bbox is not None and (
                        type(bbox) is not list or len(bbox) != 4
                        or any(type(n) is not int for n in bbox)
                        or not (0 <= bbox[0] < bbox[2] <= FRAME_H
                                and 0 <= bbox[1] < bbox[3] <= FRAME_W))):
                raise BallGTError("inconsistent independent MuJoCo mask bbox")
    return all(v["valid_geometry"] and v["pose_static"] for v in cases)


def _scene_dir_checked(scene_dir: Path, scene: str) -> Path:
    if (not isinstance(scene_dir, Path) or scene_dir.is_symlink()
            or not scene_dir.is_dir() or scene not in ALLOWED_SCENES):
        raise BallGTError("not a pinned allowed OEM scene directory")
    src = scene_dir / scene
    if src.is_symlink() or not src.is_file():
        raise BallGTError("missing/symlinked approved OEM scene")
    return src


def render_case(scene_dir: Path, spec: Case):
    """Return ephemeral upright RGB and a source-only geometry record."""
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import Body, HOME_TRUNK_Z, World
    from mjlab_microduck.sim.camera import Camera, HEIGHT, WIDTH
    from microduck_companion.sim_vis_f_gt_preflight import _set_free_joint

    if (spec not in CASES or (WIDTH, HEIGHT) != (FRAME_W, FRAME_H)):
        raise BallGTError("unregistered case or OEM optical dimensions changed")
    world = World(_scene_dir_checked(scene_dir, spec.scene), 1)
    body = Body(world, 0)
    body.place(None, HOME_TRUNK_Z, 0.)
    model, data = world.model, world.data
    data.qpos[body.trunk:body.trunk + 2] = spec.robot_xy
    data.qpos[body.trunk + 3:body.trunk + 7] = (
        math.cos(spec.yaw / 2), 0., 0., math.sin(spec.yaw / 2))
    mujoco.mj_forward(model, data)
    camera = Camera(model, "head_camera")
    try:
        mujoco.mj_forward(model, data)
        if spec.free_body:
            rot = data.cam_xmat[camera.camera].reshape(3, 3)
            forward = -rot[:, 2].astype(float)
            norm = float(np.linalg.norm(forward[:2]))
            if not math.isfinite(norm) or norm < .55:
                raise BallGTError("unusable OEM camera forward vector")
            face = forward[:2] / norm
            side = np.asarray([-face[1], face[0]])
            origin = data.cam_xpos[camera.camera, :2]
            xy = origin + face * spec.forward_m + side * spec.left_m
            _set_free_joint(model, data, spec.free_body,
                            (float(xy[0]), float(xy[1]), 0.))
            mujoco.mj_forward(model, data)

        ids = []
        for geom in spec.geoms:
            gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, geom)
            if gid < 0:
                raise BallGTError("preregistered OEM target geom unavailable")
            ids.append(int(gid))
        if spec.role == "empty_negative":
            # All static world geoms must be just the pinned floor; robot body
            # geoms may exist, and their visible pixels are counted separately.
            floor_id = mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
            world_extra = [
                i for i in range(model.ngeom)
                if int(model.geom_bodyid[i]) == 0 and i != floor_id
            ]
            if floor_id < 0 or world_extra:
                raise BallGTError("blank OEM world has additional geometry")

        t0 = float(data.time)
        qhash = hashlib.sha256(data.qpos.tobytes()).hexdigest()
        camera.renderer.update_scene(data, camera=camera.camera)
        rgb = camera.renderer.render().copy()
        camera.renderer.enable_segmentation_rendering()
        try:
            camera.renderer.update_scene(data, camera=camera.camera)
            seg = camera.renderer.render().copy()
        finally:
            camera.renderer.disable_segmentation_rendering()
        static = (float(data.time) == t0
                  and hashlib.sha256(data.qpos.tobytes()).hexdigest() == qhash)
        if (rgb.shape != (FRAME_H, FRAME_W, 3)
                or seg.shape != (FRAME_H, FRAME_W, 2)
                or not np.issubdtype(seg.dtype, np.integer)):
            raise BallGTError("wrong/unmatched OEM RGB or segmentation frame")

        upright = np.rot90(rgb, k=3)
        segmentation = np.rot90(seg, k=3)
        box, pixels = _ids_and_target(
            segmentation, tuple(ids), int(mujoco.mjtObj.mjOBJ_GEOM))
        body_visible_pixels = 0
        if spec.role == "empty_negative":
            geom_pixels = segmentation[:, :, 1] == int(
                mujoco.mjtObj.mjOBJ_GEOM)
            visible_ids = segmentation[:, :, 0][geom_pixels]
            # World-floor is not a target; robot pixels are not evidence for
            # an external object. No non-floor worldbody geometry is present.
            body_visible_pixels = int(sum(
                int(model.geom_bodyid[int(g)]) != 0
                for g in visible_ids if 0 <= g < model.ngeom
            ))
        valid = (static and (pixels == 0 and box is None
                 if spec.role == "empty_negative"
                 else pixels >= MIN_VISIBLE_PIXELS and box is not None))
        record = {
            "case": spec.name, "scene": spec.scene,
            "robot_xy": list(spec.robot_xy),
            "yaw_deg": round(math.degrees(spec.yaw), 3),
            "role": spec.role,
            "geom_pixels": pixels, "geom_bbox_xyxy": box,
            "pose_static": static, "valid_geometry": bool(valid),
            "self_robot_pixels_in_negative": body_visible_pixels
                if spec.role == "empty_negative" else None,
            "source_rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
            "source_mask_sha256": hashlib.sha256(seg.tobytes()).hexdigest(),
        }
        return upright, record
    finally:
        camera.renderer.close()


def score_case(spec: Case, oracle: dict, raw, *, width=FRAME_H,
               height=FRAME_W) -> dict:
    """One unmodified YOLOX head for 5-class baseline and top1/3/5."""
    from microduck_companion.cata2_bbox_eval import decode_boxes

    if (spec not in CASES or oracle.get("case") != spec.name
            or not oracle.get("valid_geometry")):
        raise BallGTError("invalid or missing target geometry")
    recognized = decode_boxes(raw, width=width, height=height)
    region_caps = {}
    named = []
    box = oracle["geom_bbox_xyxy"]
    if box is not None:
        named = [float(_iou(tuple(box), item.xyxy)) for item in recognized]
    best_named = max(named, default=0.)
    best_top3 = 0.
    for cap in (1, 3, 5):
        regions = decode_candidates(
            raw, width=width, height=height, max_results=cap)
        matches = [(float(_iou(tuple(box), r["xyxy"])), r)
                   for r in regions] if box else []
        best_iou = max((p[0] for p in matches), default=0.)
        if cap == 3:
            best_top3 = best_iou
        region_caps[str(cap)] = {
            "region_count": len(regions),
            "strong_ge_0_80": sum(
                r["score"] >= STRONG_NEGATIVE_SCORE for r in regions),
            "best_geom_iou": round(best_iou, 6) if box else None,
            "iou50": bool(best_iou >= MIN_MATCH_IOU) if box else None,
            "regions_class_index_and_score": [
                [r["untrusted_coco_class_index"], r["score"]]
                for r in regions
            ],
        }
    return {
        "case": spec.name, "role": spec.role,
        "best_five_class_bbox_iou": round(best_named, 6) if box else None,
        "five_class_bbox_iou50": bool(best_named >= MIN_MATCH_IOU) if box else None,
        "top3_recovers_without_five_class_box": (
            best_top3 >= MIN_MATCH_IOU and best_named < MIN_MATCH_IOU
        ) if box else None,
        "region_caps": region_caps,
    }


def gate(rows: list[dict]) -> dict:
    """Predeclared value gate; green CI MUST NOT imply green vision."""
    if (type(rows) is not list
            or [r.get("case") for r in rows] != list(ALL_NAMES)
            or any(r.get("role") != s.role for r, s in zip(rows, CASES))):
        raise BallGTError("missing/reordered scored PER-S0 cases")
    for row in rows:
        caps = row.get("region_caps")
        if type(caps) is not dict or set(caps) != {"1", "3", "5"}:
            raise BallGTError("incomplete region cap scores")
        for cap in ("1", "3", "5"):
            c = caps[cap]
            if (type(c.get("region_count")) is not int
                    or not 0 <= c["region_count"] <= int(cap)
                    or type(c.get("strong_ge_0_80")) is not int
                    or not 0 <= c["strong_ge_0_80"] <= c["region_count"]):
                raise BallGTError("invalid proposal statistics")
            if row["role"] != "empty_negative" and (
                    type(c.get("iou50")) is not bool
                    or type(c.get("best_geom_iou")) not in (float, int)
                    or not math.isfinite(c["best_geom_iou"])
                    or not 0 <= c["best_geom_iou"] <= 1):
                raise BallGTError("invalid GT association statistics")
    targets = [row for row in rows if row["role"] == "outside_five"]
    matched = sum(x["region_caps"]["3"]["iou50"] for x in targets)
    recovered = sum(bool(x["top3_recovers_without_five_class_box"])
                    for x in targets)
    negative = rows[-1]["region_caps"]["3"]["strong_ge_0_80"]
    value = (matched >= MIN_OUTSIDE_TOP3
             and recovered >= MIN_INCREMENTAL_TOP3 and negative == 0)
    return {
        "unknown_outside_five_cases": 4,
        "unknown_region_top3_iou50": matched,
        "unknown_incremental_over_five_class": recovered,
        "known_ball_top3_iou50": bool(
            rows[-2]["region_caps"]["3"]["iou50"]),
        "negative_top3_high_confidence_count": negative,
        "functional_value_gate_met": value,
        "status": "PC_criterion_met_not_robot_validation"
            if value else "STOP_no_property_extractor_on_this_model",
    }


def evaluate(scene_dir: Path, model: Path | None, *,
             preflight_only: bool) -> dict:
    import numpy as np
    from PIL import Image

    frames = []
    geometry = []
    try:
        for spec in CASES:
            frame, oracle = render_case(scene_dir, spec)
            frames.append(frame)
            geometry.append(oracle)
        okay = validate_preflight(geometry)
        report = {
            "study": "PER_S0_OEM_lowview_region_vs_category_once",
            "oem_sim_camera_only": True,
            "preflight_geometry_valid": okay,
            "geometry": geometry,
            "yolox_inference_cases": 0,
            "oem_or_NPU_or_robot_validated": False,
            "motors_qwen_sqlite_medias_written": 0,
            "model_weights_or_images_published": False,
        }
        if not okay:
            report["status"] = "STOP_invalid_geometry"
            report["functional_value_gate_met"] = None
            return report
        if preflight_only:
            report["status"] = "geometry_preflight_only_NO_model"
            report["functional_value_gate_met"] = None
            return report
        if model is None:
            raise BallGTError("approved model required after geometry gate")
        from microduck_companion.cata_yolox_categories import (
            prepare_image, validate_model_file,
        )
        import onnxruntime as ort

        validate_model_file(model)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(model), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        if len(session.get_inputs()) != 1 or session.get_inputs()[0].name != "images":
            raise BallGTError("unexpected ONNX input head")
        scored = []
        infer_times = []
        decode_times = []
        for spec, image, oracle in zip(CASES, frames, geometry):
            jpeg = BytesIO()
            Image.fromarray(image).save(jpeg, format="JPEG", quality=95)
            tensor = prepare_image(jpeg.getvalue(), mode="original")
            before = time.perf_counter()
            outputs = session.run(None, {"images": tensor})
            infer_times.append((time.perf_counter() - before) * 1000.)
            if len(outputs) != 1:
                raise BallGTError("unexpected ONNX output count")
            before = time.perf_counter()
            scored.append(score_case(spec, oracle, outputs[0]))
            decode_times.append((time.perf_counter() - before) * 1000.)
        report["yolox_inference_cases"] = len(scored)
        report["observations"] = scored
        report["decision"] = gate(scored)
        report["status"] = report["decision"]["status"]
        report["functional_value_gate_met"] = (
            report["decision"]["functional_value_gate_met"])
        for key, values in (("inference", infer_times), ("decode", decode_times)):
            report[key + "_host_ms_p50"] = round(
                statistics.median(values), 3)
            report[key + "_host_ms_p95"] = round(
                float(np.percentile(values, 95)), 3)
        return report
    finally:
        frames.clear()  # no file-backed media or singleton camera exists


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-static-oem-render", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_static_oem_render:
        parser.error("static read-only OEM render must be explicitly authorized")
    try:
        if args.output.exists() or args.output.is_symlink():
            raise BallGTError("refuse to overwrite evidence")
        report = evaluate(args.scene_dir, args.model,
                          preflight_only=args.preflight_only)
        args.output.write_text(json.dumps(report, sort_keys=True) + "\n",
                               encoding="utf-8")
        # Print numbers only, never image bytes, raw ONNX or private media.
        print(json.dumps(report, sort_keys=True))
        return 0  # procedure passed; NOT equivalent to S0 value gate passing
    except (BallGTError, OSError, RuntimeError, ValueError) as exc:
        print(f"PER-S0 STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
