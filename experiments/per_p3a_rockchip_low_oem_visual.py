"""PER-P3A: one read-only PP-YOLOE-s ONNX run on pinned low OEM views.

Independent ground truth is an OEM MuJoCo geometry mask, NOT a model output.
This is an offline PC assessment, not mediad, RKNN runtime, or robot control.
Vendor pre/postprocessing is imported unmodified from the pinned RKNN Model Zoo.
No camera, model, or raw image is saved by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

from microduck_companion.sim_ball_segmentation_gt import (
    BallGTError, FRAME_H, FRAME_W, MIN_VISIBLE_PIXELS, _rig_scene,
    visible_geom_bbox,
)
from microduck_companion.sim_vis_d_new_scenes_f2_fixture import _prepare_static_world
from microduck_companion.yolox_attention_candidates import _iou

MODEL_SHA256 = "af72d05b33723f6d18f9784f6bba8e593a5554f465f1800d7ad1ba1e33e38b8a"
MODEL_BYTES = 31734323
PINNED_CASES = (
    ("flat_ball_ahead", "sports ball"),
    ("s2_far_right_yaw105", "sports ball"),
    ("chair_near", "chair"),
    ("vslam_pillar", None),
    ("flat_ball_behind", "absent_sports_ball"),
)
EXPECTED_SHAPES = tuple(
    (1, channels, side, side)
    for side in (20, 40, 80)
    for channels in (68, 80, 1)
)
GT_MIN_IOU = 0.50


def verify_model(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size != MODEL_BYTES:
        raise BallGTError("missing/wrong-size/symlink PP-YOLOE source model")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise BallGTError("PP-YOLOE ONNX checksum mismatch: STOP")


def check_heads(outputs) -> None:
    import numpy as np

    if not isinstance(outputs, (list, tuple)) or len(outputs) != 9:
        raise BallGTError("expected exactly nine vendor PP-YOLOE output heads")
    for i, (value, expected) in enumerate(zip(outputs, EXPECTED_SHAPES)):
        if (not isinstance(value, np.ndarray)
                or value.dtype != np.float32
                or value.shape != expected
                or not np.isfinite(value).all()):
            raise BallGTError(f"unusable vendor output head {i}: shape/dtype/nonfinite")


def check_predictions(predictions: list[dict]) -> None:
    if not isinstance(predictions, list):
        raise BallGTError("invalid model predictions container")
    for item in predictions:
        if (not isinstance(item, dict)
                or set(item) != {"class_index", "score", "xyxy"}
                or type(item["class_index"]) is not int
                or not 0 <= item["class_index"] < 80
                or not isinstance(item["score"], float)
                or not math.isfinite(item["score"])
                or not 0 <= item["score"] <= 1
                or not isinstance(item["xyxy"], list)
                or len(item["xyxy"]) != 4
                or any(not isinstance(x, float) or not math.isfinite(x)
                       for x in item["xyxy"])):
            raise BallGTError("malformed/untrusted PP-YOLOE prediction")
        x0, y0, x1, y1 = item["xyxy"]
        if not (0 <= x0 <= x1 <= FRAME_H and 0 <= y0 <= y1 <= FRAME_W):
            raise BallGTError("PP-YOLOE box outside upright OEM frame")


def score_case(name: str, gt_box, predictions: list[dict],
               *, ball_index: int = 32, chair_index: int = 56) -> dict:
    check_predictions(predictions)
    label = dict(PINNED_CASES).get(name, "__not_declared__")
    if label == "__not_declared__":
        raise BallGTError("unregistered model scene")
    if label == "absent_sports_ball":
        if gt_box is not None:
            raise BallGTError("negative contains positive ball oracle")
        return {
            "case": name, "target_label": label, "gt_exists": False,
            "false_sports_ball_detections": sum(
                p["class_index"] == ball_index for p in predictions),
            "detection_count_all_classes": len(predictions),
            "recognised_iou50": None, "best_iou_any_class": None,
        }
    if gt_box is None:
        raise BallGTError("positive geometry oracle missing")
    if label is None:  # pillar: no COCO target class, no claim about true unknowns
        chosen = None
    else:
        chosen = ball_index if label == "sports ball" else chair_index
    overlaps = [
        (_iou(tuple(map(float, gt_box)), tuple(p["xyxy"])), p)
        for p in predictions
    ]
    same = [(v, p) for v, p in overlaps if p["class_index"] == chosen]
    best_correct = max((v for v, _ in same), default=0.0)
    best_any = max((v for v, _ in overlaps), default=0.0)
    # A wrong category may overlap a geometric oracle: never count it as a TP.
    return {
        "case": name, "target_label": label, "gt_exists": True,
        "detection_count_all_classes": len(predictions),
        "best_iou_correct_class": round(best_correct, 6) if chosen is not None else None,
        "best_iou_any_class": round(best_any, 6),
        "recognised_iou50": (best_correct >= GT_MIN_IOU) if chosen is not None else None,
        "target_class_scores_top3": [
            round(p["score"], 6) for v, p in sorted(
                same, key=lambda t: t[1]["score"], reverse=True
            )[:3]
        ] if chosen is not None else None,
        "top3_all_classes": [
            {"class_index": p["class_index"], "score": round(p["score"], 6)}
            for p in sorted(predictions, key=lambda p: p["score"], reverse=True)[:3]
        ],
    }


def visual_gate(results: list[dict]) -> bool:
    """Predeclared strict gate: both balls + chair, zero negative ball."""
    if (not isinstance(results, list)
            or [r.get("case") for r in results] != [x[0] for x in PINNED_CASES]):
        raise BallGTError("incomplete/reordered model evaluation report")
    by_case = {r["case"]: r for r in results}
    return (
        all(by_case[name]["recognised_iou50"] is True for name in
            ("flat_ball_ahead", "s2_far_right_yaw105", "chair_near"))
        and by_case["flat_ball_behind"]["false_sports_ball_detections"] == 0
    )


def rig_case(scene_dir: Path, name: str):
    """Reuse existing pinned OEM static rigs; add only the frozen chair pose."""
    import mujoco
    if name in ("flat_ball_ahead", "flat_ball_behind", "vslam_pillar"):
        return _prepare_static_world(scene_dir, name)
    if name == "s2_far_right_yaw105":
        world, camera, ids = _rig_scene(
            scene_dir / "scene_apartment.xml", name)
        return world, camera, ids["ball_0"]
    if name == "chair_near":
        from mjlab_microduck.sim.body_server import Body, HOME_TRUNK_Z, World
        from mjlab_microduck.sim.camera import Camera
        world = World(scene_dir / "scene_apartment.xml", 1)
        body = Body(world, 0)
        body.place(None, HOME_TRUNK_Z, 0.0)
        world.data.qpos[body.trunk:body.trunk+2] = (-2.55, 0.05)
        mujoco.mj_forward(world.model, world.data)
        camera = Camera(world.model, "head_camera")
        mujoco.mj_forward(world.model, world.data)
        gid = mujoco.mj_name2id(world.model, mujoco.mjtObj.mjOBJ_GEOM,
                                "liv_chair_seat")
        if gid < 0:
            camera.renderer.close()
            raise BallGTError("pinned OEM chair geom absent")
        return world, camera, gid
    raise BallGTError("not in frozen PER-P3A list")


def render_oracle(scene_dir: Path, name: str):
    """Same static OEM camera frame, RGB kept in memory, masked GT separate."""
    import mujoco
    import numpy as np

    world, camera, geom_id = rig_case(scene_dir, name)
    try:
        model, data = world.model, world.data
        before_t = float(data.time)
        before_q = hashlib.sha256(data.qpos.tobytes()).hexdigest()
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
                or float(data.time) != before_t
                or hashlib.sha256(data.qpos.tobytes()).hexdigest() != before_q):
            raise BallGTError("OEM static camera/mask/pose inconsistent")
        rgb_upright = np.rot90(rgb, k=3)
        seg_upright = np.rot90(seg, k=3)
        bbox, pixels = visible_geom_bbox(
            seg_upright, geom_id=int(geom_id),
            geom_type=int(mujoco.mjtObj.mjOBJ_GEOM))
        expected = dict(PINNED_CASES)[name]
        valid = pixels == 0 if expected == "absent_sports_ball" else (
            pixels >= MIN_VISIBLE_PIXELS and bbox is not None)
        return rgb_upright, {
            "case": name, "valid_gt": bool(valid), "geom_pixels": pixels,
            "geom_bbox_xyxy": bbox,
            "frozen_rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
            "independent_mask_sha256": hashlib.sha256(seg.tobytes()).hexdigest(),
            "oem_simulation_only": True,
        }
    finally:
        camera.renderer.close()


def load_vendor(vendor_root: Path):
    """Use the official Rockchip decode, not a new Companion DFL implementation."""
    p = vendor_root / "examples/ppyoloe/python/ppyoloe.py"
    if (vendor_root.name != "rknn_model_zoo"
            or p.is_symlink() or not p.is_file()):
        raise BallGTError("official vendor PP-YOLOE script missing")
    spec = importlib.util.spec_from_file_location("_official_rockchip_ppyoloe", p)
    if spec is None or spec.loader is None:
        raise BallGTError("cannot load unmodified vendor implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if (module.OBJ_THRESH != .25 or module.NMS_THRESH != .45
            or module.IMG_SIZE != (640, 640)
            or module.CLASSES.index("sports ball") != 32
            or module.CLASSES.index("chair") != 56):
        raise BallGTError("vendor thresholds/class mapping changed")
    return module


def infer_one(rgb_upright, session, vendor):
    import cv2
    import numpy as np
    from py_utils.coco_utils import COCO_test_helper

    if rgb_upright.shape != (FRAME_W, FRAME_H, 3):
        raise BallGTError("unexpected upright OEM frame")
    co_helper = COCO_test_helper(enable_letter_box=True)
    bgr = cv2.cvtColor(rgb_upright, cv2.COLOR_RGB2BGR)
    padded = co_helper.letter_box(
        im=bgr, new_shape=(640, 640), pad_color=(0, 0, 0))
    prepared = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    tensor = np.ascontiguousarray(
        prepared.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    input_nodes = session.get_inputs()
    if (len(input_nodes) != 1
            or list(input_nodes[0].shape) != [1, 3, 640, 640]):
        raise BallGTError("ONNX runtime image interface does not match official")
    start = time.perf_counter()
    outputs = session.run(None, {input_nodes[0].name: tensor})
    infer_ms = (time.perf_counter() - start) * 1e3
    check_heads(outputs)
    start = time.perf_counter()
    boxes, classes, scores = vendor.post_process(outputs)
    decode_ms = (time.perf_counter() - start) * 1e3
    predictions = []
    if boxes is not None:
        mapped = co_helper.get_real_box(boxes)
        for xyxy, cl, score in zip(mapped, classes, scores):
            predictions.append({
                "class_index": int(cl),
                "score": float(score),
                "xyxy": [float(x) for x in xyxy],
            })
    check_predictions(predictions)
    return predictions, round(infer_ms, 3), round(decode_ms, 3)


def run_study(scene_dir: Path, model_file: Path, vendor_root: Path) -> dict:
    import numpy as np
    # The geometry preflight is intentionally completed BEFORE loading the model.
    if (scene_dir.is_symlink() or not scene_dir.is_dir()
            or not all((scene_dir / f).is_file() for f in
                       ("scene_apartment.xml", "scene_ball.xml", "scene_vslam.xml"))):
        raise BallGTError("pinned OEM world directory missing")
    frames = []
    oracles = []
    for name, _ in PINNED_CASES:
        frame, oracle = render_oracle(scene_dir, name)
        frames.append(frame)
        oracles.append(oracle)
    valid = [r for r in oracles if r["valid_gt"]]
    required = {"flat_ball_ahead", "chair_near", "flat_ball_behind"}
    can_infer = (
        len(valid) >= 4 and required.issubset({r["case"] for r in valid}))
    report = {
        "study": "PER-P3A_official_PPYOLOE_low_OEM_static_PC",
        "camera": "pinned_MuJoCo_head_camera_not_physical",
        "oracle_before_model": oracles,
        "preflight_gate_met": can_infer,
        "model_loaded": False,
        "model_inference_cases": 0,
        "weights_or_frames_published": False,
        "mediad_or_robot_or_NPU_started": False,
        "motor_commands_issued": 0,
        "weights_redistribution_license_confirmed": False,
    }
    if not can_infer:
        report["status"] = "STOP_invalid_independent_geometry"
        report["visual_gate_met"] = None
        return report

    verify_model(model_file)
    vendor = load_vendor(vendor_root)
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_file), sess_options=options, providers=["CPUExecutionProvider"])
    report["model_loaded"] = True
    measurements = []
    for i, (name, _) in enumerate(PINNED_CASES):
        if not oracles[i]["valid_gt"]:
            measurements.append({"case": name, "not_evaluated_invalid_gt": True})
            continue
        predictions, infer_ms, decode_ms = infer_one(frames[i], session, vendor)
        scored = score_case(name, oracles[i]["geom_bbox_xyxy"], predictions)
        scored["inference_ms_host"] = infer_ms
        scored["vendor_decode_ms_host"] = decode_ms
        measurements.append(scored)
    report["model_inference_cases"] = sum(
        "inference_ms_host" in x for x in measurements)
    report["observations"] = measurements
    if report["model_inference_cases"] != len(PINNED_CASES):
        report["visual_gate_met"] = False
        report["status"] = "insufficient_incomplete_GT"
    else:
        report["visual_gate_met"] = visual_gate(measurements)
        report["status"] = (
            "visual_gate_met_PC_only_license_and_NPU_blocked"
            if report["visual_gate_met"]
            else "visual_gate_failed_do_not_integrate")
    for k in ("inference_ms_host", "vendor_decode_ms_host"):
        durations = [x[k] for x in measurements if k in x]
        report[k + "_p50"] = round(float(np.percentile(durations, 50)), 3)
        report[k + "_p95"] = round(float(np.percentile(durations, 95)), 3)
    del frames[:]
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--vendor-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--authorize-readonly-oem-simulation", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_readonly_oem_simulation:
        parser.error("explicit read-only simulation authorization required")
    try:
        if args.report.exists() or args.report.is_symlink():
            raise BallGTError("refuse to overwrite prior evidence")
        result = run_study(args.scene_dir, args.model, args.vendor_root)
        args.report.write_text(json.dumps(result, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0  # successful execution is not the visual/model selection gate
    except (BallGTError, ValueError, OSError, RuntimeError) as exc:
        print(f"PER-P3A STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
