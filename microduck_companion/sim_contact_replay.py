"""P0c: offline MuJoCo contact GEOMETRY from verified, recorded body poses.

This analysis NEVER connects to robotd or body_server and NEVER advances the
physics with mj_step. It loads the pinned official scene as a separate model,
sets qpos from a read-only P0b trace and invokes mj_forward. The resulting
collision candidate pairs are a *geometric replay*, NOT the original
simulation's dynamic contact data, impulses, normals, ground reactions,
friction/traction or actuator targets.

All original solver forces and actual motor targets remain UNKNOWN. Output
must not be used as a gait, motor-safety or real-robot certificate.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from .sim_flat_zone import (
    FLAT_SCENE_BLOB, JOINT_COUNT, RL_COMMIT, SCENE_PATH,
    GroundTruthError, verify_flat_scene,
)
from .sim_joint_trace import JOINT_NAMES
from .sim_walk_trial import WALK_TICKS, WALK_SPEED_MPS
from .sim_walk_compare import REST_SAMPLES

MAX_REPLAY_SAMPLES = REST_SAMPLES + WALK_TICKS


def _finite_list(value: object, length: int, what: str) -> list[float]:
    if (not isinstance(value, list) or len(value) != length
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in value)):
        raise GroundTruthError(f"invalid or unavailable replay {what}")
    return [float(v) for v in value]


def _validated_frames(trace: dict) -> tuple[list[dict], list[dict]]:
    """Only replay complete, provenance-checked, successfully STOPPED P0b."""
    if not isinstance(trace, dict):
        raise GroundTruthError("replay input must be a P0b JSON object")
    if (trace.get("schema_version") != 1
            or trace.get("environment") != "pinned_official_mujoco_only"
            or trace.get("comparison") !=
               "same_simulator_session_stand_then_single_bounded_walk"
            or trace.get("stop_confirmed") is not True
            or trace.get("gait_validated") is not False
            or trace.get("foot_contacts_available") is not False
            or trace.get("joint_targets_available") is not False
            or trace.get("motion_commands_sent_by_existing_j2e_trial") != WALK_TICKS
            or trace.get("requested_walk_speed_mps") != WALK_SPEED_MPS):
        raise GroundTruthError("trace does not attest a stopped pinned P0b comparison")
    rest = trace.get("rest_trace")
    walk = trace.get("walk_trace")
    if not isinstance(rest, dict) or not isinstance(walk, dict):
        raise GroundTruthError("missing P0b trace phases")
    if (rest.get("mode") != "passive_read_only"
            or rest.get("source") != "pinned_official_mujoco_body_and_robotd"
            or rest.get("rl_commit") != RL_COMMIT
            or rest.get("flat_scene_git_blob") != FLAT_SCENE_BLOB
            or rest.get("foot_contacts_available") is not False
            or rest.get("joint_targets_available") is not False
            or rest.get("joint_names_wire_order") != list(JOINT_NAMES)):
        raise GroundTruthError("unverified pinned P0b rest trace")
    if trace.get("read_only_joint_samples") != MAX_REPLAY_SAMPLES:
        raise GroundTruthError("unexpected P0b sample count")
    stand_frames, walk_frames = rest.get("observations"), walk.get("observations")
    if (not isinstance(stand_frames, list) or len(stand_frames) != REST_SAMPLES
            or not isinstance(walk_frames, list) or len(walk_frames) != WALK_TICKS):
        raise GroundTruthError("missing or partial P0b observations")
    before = float("-inf")
    for phase, frames in (("stand", stand_frames), ("walk", walk_frames)):
        for frame in frames:
            if not isinstance(frame, dict):
                raise GroundTruthError("invalid P0b observation")
            sim_time = frame.get("sim_time_s")
            if (type(sim_time) not in (int, float)
                    or not math.isfinite(sim_time)
                    or sim_time <= before):
                raise GroundTruthError("non-increasing recorded MuJoCo time")
            before = float(sim_time)
            if frame.get("flat_scene_safe_area") is not True:
                raise GroundTruthError("unsafe recorded pose")
            if (frame.get("foot_contacts") is not None
                    or frame.get("joint_targets_rad") is not None):
                raise GroundTruthError("unexpected original contact/target claims")
            _finite_list(frame.get("trunk_xyz_m"), 3, "trunk XYZ")
            quat = _finite_list(frame.get("trunk_quat_wxyz"), 4, "trunk quaternion")
            if abs(math.sqrt(sum(v * v for v in quat)) - 1.0) > 0.01:
                raise GroundTruthError("invalid recorded trunk quaternion magnitude")
            _finite_list(frame.get("positions_rad"), JOINT_COUNT, "joint positions")
            robotd = frame.get("robotd")
            if not isinstance(robotd, dict) or robotd.get("policy") != phase:
                # A single initial 'stand' sample during J2e is legitimate.
                if not (phase == "walk" and robotd and
                        robotd.get("policy") == "stand"):
                    raise GroundTruthError("recorded policy is not a stand/walk sample")
            if phase == "stand":
                speed = _finite_list(robotd.get("applied_vx_vy_mps_vyaw_rad_s"), 3,
                                     "stand applied twist")
                if any(abs(v) > 1e-6 for v in speed):
                    raise GroundTruthError("motion during passive baseline")
    return stand_frames, walk_frames


def _ids(model, mj):
    """Resolve names, not indexes: a changed model must fail instead of drifting."""
    kind = mj.mjtObj
    def named(obj, name):
        idx = mj.mj_name2id(model, obj, name)
        if idx < 0:
            raise GroundTruthError(f"missing pinned MuJoCo name: {name}")
        return int(idx)
    root = named(kind.mjOBJ_JOINT, "trunk_base_freejoint")
    foot_l = named(kind.mjOBJ_GEOM, "left_foot_collision")
    foot_r = named(kind.mjOBJ_GEOM, "right_foot_collision")
    floor = named(kind.mjOBJ_GEOM, "floor")
    site_l = named(kind.mjOBJ_SITE, "left_foot")
    site_r = named(kind.mjOBJ_SITE, "right_foot")
    joint_addresses = []
    for name in JOINT_NAMES:
        if name == "mouth":
            joint_addresses.append(None)
        else:
            joint_addresses.append(int(model.jnt_qposadr[named(kind.mjOBJ_JOINT, name)]))
    return {
        "root_qpos": int(model.jnt_qposadr[root]),
        "joint_qpos": joint_addresses,
        "floor": floor,
        "left": foot_l,
        "right": foot_r,
        "left_site": site_l,
        "right_site": site_r,
    }


def _replay_frame(frame: dict, model, data, mj, ident: dict) -> dict:
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0  # original trunk linear/angular velocity was NOT recorded
    trunk = frame["trunk_xyz_m"]
    quat = frame["trunk_quat_wxyz"]
    root = ident["root_qpos"]
    data.qpos[root:root + 3] = trunk
    data.qpos[root + 3:root + 7] = quat
    for index, address in enumerate(ident["joint_qpos"]):
        if address is not None:
            data.qpos[address] = frame["positions_rad"][index]
    # NO mj_step. mj_forward recomputes geometry, does not recreate the
    # original simulation's solver contact forces/impulses.
    mj.mj_forward(model, data)
    floor, left, right = ident["floor"], ident["left"], ident["right"]
    floor_geoms = {"left": left, "right": right}
    counts, minimum = {"left": 0, "right": 0}, {"left": None, "right": None}
    overlaps = {"left": 0, "right": 0}
    for i in range(data.ncon):
        contact = data.contact[i]
        pair = {int(contact.geom1), int(contact.geom2)}
        for side, foot in floor_geoms.items():
            if pair == {floor, foot}:
                distance = float(contact.dist)
                if not math.isfinite(distance):
                    raise GroundTruthError("nonfinite replay geometry distance")
                counts[side] += 1
                minimum[side] = (distance if minimum[side] is None
                                  else min(minimum[side], distance))
                overlaps[side] += int(distance <= 0.0)
    def site_xyz(site_id):
        xyz = [float(v) for v in data.site_xpos[site_id]]
        if not all(math.isfinite(v) for v in xyz):
            raise GroundTruthError("nonfinite replay foot site")
        return xyz
    return {
        "sim_time_s": frame["sim_time_s"],
        "reported_policy": frame["robotd"]["policy"],
        "replayed_ground_foot_candidate_pairs": counts,
        "replayed_ground_foot_overlapping_pairs": overlaps,
        "replayed_min_signed_contact_dist_m": minimum,
        "replayed_foot_site_xyz_m": {
            "left": site_xyz(ident["left_site"]),
            "right": site_xyz(ident["right_site"]),
        },
        "original_contact_forces_n": None,
        "original_contact_impulses_ns": None,
        "original_contact_pairs": None,
        "original_joint_targets_rad": None,
    }


def _summary(frames: list[dict]) -> dict:
    return {
        "frames": len(frames),
        "left_geometric_overlap_frames": sum(
            f["replayed_ground_foot_overlapping_pairs"]["left"] > 0 for f in frames),
        "right_geometric_overlap_frames": sum(
            f["replayed_ground_foot_overlapping_pairs"]["right"] > 0 for f in frames),
        "both_geometric_overlap_frames": sum(
            all(f["replayed_ground_foot_overlapping_pairs"].values()) for f in frames),
        "no_geometric_overlap_frames": sum(
            not any(f["replayed_ground_foot_overlapping_pairs"].values()) for f in frames),
        "max_replay_candidate_pairs_per_frame": max(
            sum(f["replayed_ground_foot_candidate_pairs"].values()) for f in frames),
    }


def replay_contact_geometry(trace: dict, rl_root: str | Path) -> dict:
    """On a separate MjData, replay recorded qpos without touching live robotd."""
    stand, walk = _validated_frames(trace)
    root = Path(rl_root).resolve()
    verify_flat_scene(root)
    try:
        import mujoco
    except ImportError as exc:
        raise GroundTruthError("MuJoCo is required for offline geometric replay") from exc
    model = mujoco.MjModel.from_xml_path(str(root / SCENE_PATH))
    if abs(float(model.opt.timestep) - 0.002) > 1e-8:
        raise GroundTruthError("unexpected pinned MJCF timestep")
    data = mujoco.MjData(model)
    ids = _ids(model, mujoco)
    # No TCP sockets, JSON-RPC, actuator targets, writes or simulation stepping.
    passive = [_replay_frame(f, model, data, mujoco, ids) for f in stand]
    active = [_replay_frame(f, model, data, mujoco, ids) for f in walk]
    return {
        "schema_version": 1,
        "source": "offline_geometric_replay_of_pinned_official_mujoco",
        "provenance": {
            "rl_commit": RL_COMMIT,
            "scene_git_blob": FLAT_SCENE_BLOB,
            "original_trace": "verified_p0b_stand_then_walk",
        },
        "method": "mj_forward_on_independent_MjData_from_recorded_qpos_no_mj_step",
        "trunk_linear_and_angular_velocity": "unknown_set_zero_for_replay",
        "no_motor_commands_sent": True,
        "original_live_solver_contacts_observed": False,
        "original_contact_forces_available": False,
        "original_joint_targets_available": False,
        "replay_contact_geometry_not_measured_live_contacts": True,
        "gait_validated": False,
        "traction_validated": False,
        "locomotion_root_cause": "unknown",
        "stand": {"summary": _summary(passive), "frames": passive},
        "walk": {"summary": _summary(active), "frames": active},
        "limitations": (
            "Replayed geometry approximates MuJoCo collision candidates at "
            "recorded sample poses, not time-continuous stepping, actual live "
            "contacts, forces, tangential friction, slip or true gait."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P0c: offline geometry replay, never motor commands")
    ap.add_argument("--rl-root", type=Path, required=True)
    ap.add_argument("--input", type=Path, required=True, help="recorded P0b JSON")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        trace = json.loads(args.input.read_text(encoding="utf-8"),
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        result = replay_contact_geometry(trace, args.rl_root)
        args.output.write_text(
            json.dumps(result, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "geometry_replayed": True,
            "stand": result["stand"]["summary"],
            "walk": result["walk"]["summary"],
            "original_live_solver_contacts_observed": False,
            "original_contact_forces_available": False,
            "gait_validated": False,
            "locomotion_root_cause": "unknown",
        }, allow_nan=False, sort_keys=True))
    except (GroundTruthError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"P0c geometric replay unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
