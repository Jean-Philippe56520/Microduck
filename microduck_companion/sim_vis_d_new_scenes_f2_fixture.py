"""SIM-VIS-D: independent pinned OEM static worlds -> YOLOX regions -> MOCK F2.

The rendered camera/segmentation really uses the pinned OEM RL MuJoCo model.
The downstream F2 input is an explicitly synthetic, host-only mock proxy:
it is NOT an authenticated OEM vision adapter, a sensor, or robot cognition.
No mj_step, robotd, mediad, PC, speaker, persistent SQLite or motor RPC.
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

from .autonomy import AutonomyBrain
from .cata_yolox_categories import (
    MIN_SCORE, MODEL_SHA256, SIZE, prepare_image, validate_model_file,
)
from .episodic_memory import ExperienceMemory
from .passive_memory import PassiveObservationJournal
from .passive_sources import PassiveRead
from .perception import (
    DETECTION_CONFIDENCE, PerceptionEvent, PerceptionSnapshot,
)
from .sim_ball_segmentation_gt import (
    BallGTError, FRAME_H, FRAME_W, MIN_VISIBLE_PIXELS, visible_geom_bbox,
)
from .yolox_attention_candidates import _iou, decode_candidates

SCENE_CASES = (
    ("flat_ball_ahead", "scene_ball.xml", "ball_geom"),
    ("flat_ball_behind", "scene_ball.xml", "ball_geom"),
    ("vslam_pillar", "scene_vslam.xml", "vs_pil_r"),
)
DISTANCE_AHEAD_M = 0.62
DISTANCE_BEHIND_M = 0.70
VSLAM_ROBOT_XY = (1.65, 1.80)
MONO_AT = 120.0
MONO_NOW = 120.2
WALL_AT = 1_780_700_000.0


def mock_f2_from_regions(regions: list[dict], *,
                         sample_at: float = MONO_AT,
                         now: float = MONO_NOW,
                         claimed_source: str = "mock") -> dict:
    """One F2-B cycle over a visibly labeled synthetic fixture projection.

    Uses only YOLOX's UNTRUSTED spatial scores, never its category, an
    independent geom label, an image, a real mediad message, or a reward.
    Even a perfectly overlapping region is not a semantic observation.
    """
    if type(regions) is not list or len(regions) > 3:
        raise ValueError("at most three untrusted regions are allowed")
    for region in regions:
        if (type(region) is not dict
                or set(region) != {
                    "xyxy", "score", "untrusted_coco_class_index"
                }
                or type(region["score"]) is not float
                or not math.isfinite(region["score"])
                or not 0 <= region["score"] <= 1
                or type(region["untrusted_coco_class_index"]) is not int
                or not 0 <= region["untrusted_coco_class_index"] < 80
                or not isinstance(region["xyxy"], tuple)
                or len(region["xyxy"]) != 4
                or any(type(v) is not float or not math.isfinite(v)
                       for v in region["xyxy"])):
            raise ValueError("malformed untrusted region; no mock promotion")

    events = tuple(PerceptionEvent(
        kind="object_label", value="unknown", source=claimed_source,
        observed_at=sample_at, ttl_s=1.0,
        confidence=region["score"], track_id=f"fixture-region-{i}",
    ) for i, region in enumerate(regions))
    # Deliberately MOCK on both sides of the F1/F2 boundary. This does
    # not claim the simulator's camera is an authorized production source.
    reading = PassiveRead(
        "ok", PerceptionSnapshot("mock", events, sample_at),
        sequence=1, channel="mock_fixture_unix",
    )
    memory = ExperienceMemory(":memory:")
    try:
        journal = PassiveObservationJournal(memory)
        brain = AutonomyBrain(memory)
        before = memory.conn.total_changes
        intent = brain.propose_balanced_passive(
            reading, journal=journal,
            now_monotonic_s=now, now_wall_epoch_s=WALL_AT,
        )
        if memory.conn.total_changes != before:
            raise BallGTError("decision wrote to the mock ExperienceMemory")
        if any(memory.conn.execute(
                f"SELECT count(*) FROM {table}").fetchone()[0] != 0
               for table in (
                   "objects", "experiences", "intent_preferences",
                   "passive_observation_log", "sim_motion_trials")):
            raise BallGTError("decision created a false memory or effect")
        if (intent.intention not in ("idle", "inspect")
                or intent.target_category not in (None, "unknown")
                or intent.request_pc_analysis
                or intent.executed
                or intent.motor_commands_issued):
            raise BallGTError("mock F2 response exceeds passive intent scope")
        if not any(r["score"] >= DETECTION_CONFIDENCE for r in regions):
            if intent.intention != "idle":
                raise BallGTError("subthreshold region got an active intention")
        return {
            "intention": intent.intention,
            "reason": intent.reason,
            "target_category": intent.target_category,
            "model_scores_unverified": [r["score"] for r in regions],
            "f2_detection_confidence_threshold": DETECTION_CONFIDENCE,
            "eligible_score_count": sum(
                r["score"] >= DETECTION_CONFIDENCE for r in regions),
            "fixture_source": "mock_fixture_unix_host_projection_only",
            "sensor_source_authenticated": False,
            "known_category_promoted": False,
            "motor_commands_issued": 0,
            "experience_writes": 0,
        }
    finally:
        memory.close()


def _prepare_static_world(scene_dir: Path, case: str):
    import mujoco
    import numpy as np
    from mjlab_microduck.sim.body_server import Body, HOME_TRUNK_Z, World
    from mjlab_microduck.sim.camera import Camera

    found = next((scene for name, scene, _ in SCENE_CASES
                  if name == case), None)
    if found is None:
        raise BallGTError("unknown preregistered scene")
    if (not isinstance(scene_dir, Path) or scene_dir.is_symlink()
            or not scene_dir.is_dir()):
        raise BallGTError("pinned scene directory required")
    scene_path = scene_dir / found
    if scene_path.is_symlink() or not scene_path.is_file():
        raise BallGTError("pinned OEM scene XML missing or symlinked")

    world = World(scene_path, 1)
    body = Body(world, 0)
    body.place(None, HOME_TRUNK_Z, 0.0)
    if case == "vslam_pillar":
        world.data.qpos[body.trunk:body.trunk + 2] = VSLAM_ROBOT_XY
    mujoco.mj_forward(world.model, world.data)

    camera = Camera(world.model, "head_camera")
    try:
        mujoco.mj_forward(world.model, world.data)  # OEM optical fix
        optical = world.data.cam_xmat[camera.camera].reshape(3, 3)
        forward = -optical[:, 2].astype(float)
        xy_forward = forward[:2]
        norm = float(np.linalg.norm(xy_forward))
        if not math.isfinite(norm) or norm < 0.55:
            raise BallGTError("OEM camera horizontal forward invalid")
        xy_forward /= norm
        target_name = next(target for name, _, target in SCENE_CASES
                           if name == case)
        target_gid = mujoco.mj_name2id(
            world.model, mujoco.mjtObj.mjOBJ_GEOM, target_name)
        if target_gid < 0:
            raise BallGTError("target absent from pinned OEM scene")

        if case.startswith("flat_ball_"):
            bid = mujoco.mj_name2id(
                world.model, mujoco.mjtObj.mjOBJ_BODY, "ball")
            if bid < 0 or world.model.body_jntnum[bid] != 1:
                raise BallGTError("pinned OEM ball body changed")
            joint = int(world.model.body_jntadr[bid])
            if int(world.model.jnt_type[joint]) != int(mujoco.mjtJoint.mjJNT_FREE):
                raise BallGTError("OEM ball is not a free joint")
            adr = int(world.model.jnt_qposadr[joint])
            origin = world.data.cam_xpos[camera.camera, :2].copy()
            signed_distance = (
                DISTANCE_AHEAD_M if case == "flat_ball_ahead"
                else -DISTANCE_BEHIND_M
            )
            xy = origin + xy_forward * signed_distance
            world.data.qpos[adr:adr + 3] = [float(xy[0]), float(xy[1]), 0.035]
            world.data.qpos[adr + 3:adr + 7] = [1., 0., 0., 0.]
            mujoco.mj_forward(world.model, world.data)
        else:
            target_xy = world.data.geom_xpos[target_gid, :2]
            cam_xy = world.data.cam_xpos[camera.camera, :2]
            if float(np.dot(target_xy - cam_xy, xy_forward)) < 0.2:
                raise BallGTError("declared vslam pillar not in forward hemisphere")
        return world, camera, target_gid
    except Exception:
        camera.renderer.close()
        raise


def render_and_evaluate(scene_dir: Path, case: str, session) -> dict:
    import mujoco
    import numpy as np
    from PIL import Image

    world, camera, geom_id = _prepare_static_world(scene_dir, case)
    try:
        data = world.data
        qpos_hash = hashlib.sha256(data.qpos.tobytes()).hexdigest()
        static_time = float(data.time)
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
            raise BallGTError("OEM RGB and geom segmentation are not aligned")
        if (float(data.time) != static_time
                or hashlib.sha256(data.qpos.tobytes()).hexdigest() != qpos_hash):
            raise BallGTError("world changed between independent observations")
        rgb_upright = np.rot90(rgb, k=3)
        seg_upright = np.rot90(seg, k=3)
        gt_xyxy, pixels = visible_geom_bbox(
            seg_upright, geom_id=int(geom_id),
            geom_type=int(mujoco.mjtObj.mjOBJ_GEOM),
        )
        if case == "flat_ball_behind":
            if pixels != 0:
                raise BallGTError("out-of-view negative has visible ball pixels")
        elif pixels < MIN_VISIBLE_PIXELS or gt_xyxy is None:
            raise BallGTError("positive geom not visible enough, stop experiment")

        frame = BytesIO()
        Image.fromarray(rgb_upright).save(frame, format="JPEG", quality=95)
        sample = prepare_image(frame.getvalue(), mode="original")
        started = time.perf_counter()
        raw = session.run(None, {"images": sample})[0]
        infer_ms = round((time.perf_counter() - started) * 1000., 3)
        region_caps = {}
        best_regions = []
        for cap in (1, 3, 5):
            started = time.perf_counter()
            regions = decode_candidates(
                raw, width=FRAME_H, height=FRAME_W,
                max_results=cap,
            )
            decode_ms = round((time.perf_counter() - started) * 1000., 3)
            best_iou = (
                max((_iou(tuple(gt_xyxy), region["xyxy"])
                     for region in regions), default=0.)
                if gt_xyxy is not None else None
            )
            region_caps[str(cap)] = {
                "regions": len(regions),
                "best_geom_iou": round(float(best_iou), 6)
                    if best_iou is not None else None,
                "target_located_iou50": (
                    best_iou is not None and best_iou >= .5),
                "decode_ms_host": decode_ms,
            }
            if cap == 3:
                best_regions = regions
        # The independent MuJoCo geom and its category NEVER enter F2.
        f2 = mock_f2_from_regions(best_regions)
        return {
            "case": case,
            "oem_scene": next(s for n, s, _ in SCENE_CASES if n == case),
            "geom_visible_pixels": pixels,
            "geom_bbox_xyxy": gt_xyxy,
            "region_comparison": region_caps,
            "f2_mock_projection": f2,
            "rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
            "geom_mask_sha256": hashlib.sha256(seg.tobytes()).hexdigest(),
            "static_mujoco_time_s": static_time,
            "infer_ms_host": infer_ms,
            "model_category_or_identity_verified": False,
            "motor_commands_issued": 0,
        }
    finally:
        camera.renderer.close()


def evaluate(scene_dir: Path, model_path: Path) -> dict:
    import onnxruntime as ort
    from mjlab_microduck.sim.camera import HEIGHT, WIDTH

    if (WIDTH, HEIGHT) != (FRAME_W, FRAME_H):
        raise BallGTError("pinned OEM camera resolution changed")
    validate_model_file(model_path)
    opt = ort.SessionOptions()
    opt.intra_op_num_threads = 1
    opt.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path), sess_options=opt,
        providers=["CPUExecutionProvider"],
    )
    if (len(session.get_inputs()) != 1
            or len(session.get_outputs()) != 1
            or session.get_inputs()[0].name != "images"
            or session.get_outputs()[0].name != "output"
            or session.get_inputs()[0].shape != [1, 3, SIZE, SIZE]
            or session.get_outputs()[0].shape != [1, 3549, 85]):
        raise BallGTError("unreviewed YOLOX contract")

    cases = [render_and_evaluate(scene_dir, name, session)
             for name, _, _ in SCENE_CASES]
    positives = (cases[0], cases[2])
    localized = sum(
        case["region_comparison"]["3"]["target_located_iou50"]
        for case in positives)
    return {
        "study": "SIM-VIS-D_two_distinct_pinned_OEM_worlds_and_mock_F2",
        "model_sha256": MODEL_SHA256,
        "region_min_score_unchanged": MIN_SCORE,
        "f2_threshold_unchanged": DETECTION_CONFIDENCE,
        "preregistered_positive_cases": 2,
        "top3_geom_localized": localized,
        "region_gate_met": localized >= 1,
        "cases": cases,
        "semantics_or_real_sensor_verified": False,
        "true_mediad_frame_consumed": False,
        "f2_real_cognitive_cycle_over_mock": True,
        "physical_motor_or_effect_verified": False,
        "motor_commands_issued": 0,
        "qwen_calls": 0,
        "persistent_sqlite_writes": 0,
        "published_raw_media": False,
        "physical_occlusion_verified": False,
        "conclusion_scope": "OEM_static_camera_plus_host_only_mock_F2_projection",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene-dir", type=Path, required=True)
    ap.add_argument("--model-path", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--authorize-static-oem-fixtures", action="store_true")
    args = ap.parse_args(argv)
    if not args.authorize_static_oem_fixtures:
        ap.error("explicit static OEM fixture opt-in required")
    try:
        result = evaluate(args.scene_dir, args.model_path)
        if args.output.exists() or args.output.is_symlink():
            raise BallGTError("refuse to overwrite independent experiment report")
        args.output.write_text(json.dumps(result, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        # A procedure can succeed while its detection gate fails.
        return 0
    except (BallGTError, ValueError, TypeError, RuntimeError, OSError) as exc:
        print(f"SIM-VIS-D stopped: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
