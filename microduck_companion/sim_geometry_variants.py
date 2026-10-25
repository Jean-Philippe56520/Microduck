"""P0g: OFFLINE compiled MuJoCo geometry/contact comparisons of pinned OEM XMLs.

Never connects to robotd, advances physics, commands motors or edits the
pinned submodules. For each variant, create a temporary *copy* of the pinned
scene with just its include swapped, compile a separate MjModel/MjData,
restore the same STAND keyframe, and call mj_forward ONCE. Static collision
candidates and compiler parameters are not live solver contacts or proof
that the trained ONNX network used that variant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

from .sim_flat_zone import (
    FLAT_SCENE_BLOB, GroundTruthError, RL_COMMIT, SCENE_PATH,
    verify_flat_scene,
)

VARIANTS = (
    "robot_walk.xml", "robot_groundcontact.xml", "robot_allcollisions.xml",
)
SCENE_INCLUDE = '<include file="robot_groundcontact.xml" />'
SCENE_DIRECTORY = Path(SCENE_PATH).parent
FOOT_GEOMS = ("left_foot_collision", "right_foot_collision")
KEYFRAME = "STAND"


def isolated_scene(scene: str, variant: str) -> str:
    """Change only the include in an ephemeral copy, not an OEM source."""
    # The pinned OEM scene contains a commented old STAND keyframe:
    # counting literal strings would count that inactive comment as a key.
    try:
        root = ET.fromstring(scene)
    except ET.ParseError as exc:
        raise GroundTruthError("P0g invalid pinned scene XML") from exc
    if (variant not in VARIANTS
            or scene.count(SCENE_INCLUDE) != 1
            or len(root.findall("./include[@file='robot_groundcontact.xml']")) != 1
            or len(root.findall(".//geom[@name='floor']")) != 1
            or len(root.findall("./keyframe/key[@name='STAND']")) != 1):
        raise GroundTruthError("P0g expects the exact pinned flat-floor scene")
    return scene.replace(SCENE_INCLUDE, f'<include file="{variant}" />')


def contact_mask_allows(floor_type: int, floor_affinity: int,
                        geom_type: int, geom_affinity: int) -> bool:
    """Contact mask eligibility only; excludes, parent filtering also matter."""
    return bool((floor_type & geom_affinity) or
                (geom_type & floor_affinity))


def _finite(values, label: str) -> list[float]:
    result = [float(v) for v in values]
    if not result or any(not math.isfinite(v) for v in result):
        raise GroundTruthError(f"P0g invalid compiled {label}")
    return result


def _geom(model, idx: int, mj) -> dict:
    name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, idx)
    return {
        "name": name,
        "geom_id": idx,
        "type": int(model.geom_type[idx]),
        "group": int(model.geom_group[idx]),
        "contype": int(model.geom_contype[idx]),
        "conaffinity": int(model.geom_conaffinity[idx]),
        "condim": int(model.geom_condim[idx]),
        "friction": _finite(model.geom_friction[idx], "friction"),
        "solref": _finite(model.geom_solref[idx], "solref"),
        "solimp": _finite(model.geom_solimp[idx], "solimp"),
        "priority": int(model.geom_priority[idx]),
    }


def _compiled_summary(model, data, mj, variant: str) -> dict:
    """Pure reading: only mj_forward is called by the orchestrator."""
    name_id = lambda kind, name: int(mj.mj_name2id(model, kind, name))
    floor_id = name_id(mj.mjtObj.mjOBJ_GEOM, "floor")
    if floor_id < 0:
        raise GroundTruthError(f"P0g compiled {variant} has no floor")
    foot_ids = [name_id(mj.mjtObj.mjOBJ_GEOM, n) for n in FOOT_GEOMS]
    if any(i < 0 for i in foot_ids):
        raise GroundTruthError(f"P0g compiled {variant} missing foot geometries")
    stand_id = name_id(mj.mjtObj.mjOBJ_KEY, KEYFRAME)
    if stand_id < 0:
        raise GroundTruthError(f"P0g compiled {variant} has no STAND keyframe")

    floor = _geom(model, floor_id, mj)
    feet = {name: _geom(model, idx, mj)
            for name, idx in zip(FOOT_GEOMS, foot_ids)}
    if int(model.nq) != 21 or int(model.nu) != 14:
        raise GroundTruthError("P0g inconsistent OEM joint/actuator dimensions")
    data_qpos = _finite(data.qpos, "STAND qpos")
    if len(data_qpos) != 21 or not 0.09 <= data_qpos[2] <= 0.18:
        raise GroundTruthError("P0g inconsistent OEM STAND pose")
    if abs(math.sqrt(sum(v*v for v in data_qpos[3:7])) - 1.) > 1e-4:
        raise GroundTruthError("P0g STAND root orientation not normalized")

    ftype, faff = floor["contype"], floor["conaffinity"]
    mask = [idx for idx in range(int(model.ngeom))
            if idx != floor_id and contact_mask_allows(
                ftype, faff, int(model.geom_contype[idx]),
                int(model.geom_conaffinity[idx]))]
    robot_foot_pairs = {frozenset((floor_id, idx)): name
                        for idx, name in zip(foot_ids, FOOT_GEOMS)}
    static_pairs = []
    foot_pair_counts = {name: 0 for name in FOOT_GEOMS}
    floor_other_count = 0
    for index in range(int(data.ncon)):
        c = data.contact[index]
        first, second = int(c.geom1), int(c.geom2)
        dist = float(c.dist)
        if not math.isfinite(dist):
            raise GroundTruthError("P0g nonfinite static collision distance")
        if floor_id in (first, second):
            floor_other_count += 1
        pair = frozenset((first, second))
        if pair in robot_foot_pairs:
            foot_pair_counts[robot_foot_pairs[pair]] += 1
        if len(static_pairs) < 40:
            static_pairs.append({
                "geom1": mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, first),
                "geom2": mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, second),
                "signed_distance_m": dist,
            })
    geom_counts = {}
    for idx in range(int(model.ngeom)):
        group = str(int(model.geom_group[idx]))
        geom_counts[group] = geom_counts.get(group, 0) + 1
    return {
        "variant": variant,
        "compiled_geom_count_including_floor": int(model.ngeom),
        "compiled_geom_groups": geom_counts,
        "compiled_body_count": int(model.nbody),
        "compiled_dof_count": int(model.nv),
        "compiled_actuator_count": int(model.nu),
        "mass_total_kg": sum(_finite(model.body_mass, "body masses")),
        "stand_qpos": data_qpos,
        "floor_compiled": floor,
        "feet_compiled": feet,
        "floor_mask_eligible_geom_count": len(mask),
        "mask_eligibility_is_not_full_collision_filtering": True,
        "static_contacts_total": int(data.ncon),
        "static_contacts_with_floor": floor_other_count,
        "static_foot_floor_contact_candidates": foot_pair_counts,
        "static_first_40_pairs": static_pairs,
        "static_pair_list_truncated": int(data.ncon) > 40,
        "physical_steps": 0,
        "original_live_solver_contacts_measured": False,
    }


def compare_variants(rl_root: Path, *, mj=None) -> dict:
    """Compile copies of all three OEM robots in identical pinned scene."""
    rl_root = Path(rl_root).resolve()
    verify_flat_scene(rl_root)
    if mj is None:
        import mujoco as mj
    root = rl_root / SCENE_DIRECTORY
    original_scene = (rl_root / SCENE_PATH).read_text(encoding="utf-8")
    variants = {}
    for variant in VARIANTS:
        source = root / variant
        if not source.is_file():
            raise GroundTruthError(f"P0g pinned variant missing: {variant}")
        # Never alter the official checkout; only temporary XML is changed.
        with tempfile.TemporaryDirectory(prefix="microduck-p0g-") as tmp:
            temporary = Path(tmp)
            (temporary / "scene.xml").write_text(
                isolated_scene(original_scene, variant), encoding="utf-8")
            (temporary / variant).write_bytes(source.read_bytes())
            # Read-only reference to pinned meshes; no files are copied back.
            (temporary / "assets").symlink_to(
                (root / "assets").resolve(strict=True), target_is_directory=True)
            model = mj.MjModel.from_xml_path(str(temporary / "scene.xml"))
            data = mj.MjData(model)
            key = int(mj.mj_name2id(model, mj.mjtObj.mjOBJ_KEY, KEYFRAME))
            if key < 0:
                raise GroundTruthError(f"P0g variant has no STAND keyframe: {variant}")
            mj.mj_resetDataKeyframe(model, data, key)
            mj.mj_forward(model, data)  # ONLY kinematics/collision; NEVER mj_step
            summary = _compiled_summary(model, data, mj, variant)
        summary["oem_xml_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        variants[variant] = summary

    pose = variants[VARIANTS[0]]["stand_qpos"]
    if any(len(variants[v]["stand_qpos"]) != len(pose) or any(
           abs(a-b) > 1e-10 for a,b in zip(
               variants[v]["stand_qpos"], pose))
           for v in VARIANTS[1:]):
        raise GroundTruthError("P0g comparable STAND poses differ across variants")
    baseline = variants["robot_groundcontact.xml"]
    deltas = {
        v: {
            "geom_count_vs_runtime": variants[v]["compiled_geom_count_including_floor"]
                                     - baseline["compiled_geom_count_including_floor"],
            "mask_eligible_floor_geoms_vs_runtime":
                variants[v]["floor_mask_eligible_geom_count"]
                - baseline["floor_mask_eligible_geom_count"],
            "static_floor_candidate_count_vs_runtime":
                variants[v]["static_contacts_with_floor"]
                - baseline["static_contacts_with_floor"],
        }
        for v in VARIANTS if v != "robot_groundcontact.xml"
    }
    return {
        "schema_version": 1,
        "source": "pinned_official_MuJoCo_compiled_offline_comparison",
        "provenance": {"rl_sha": RL_COMMIT,
                       "scene_blob": FLAT_SCENE_BLOB},
        "same_stand_pose": True,
        "different_compiled_geometries_not_root_cause_proof": True,
        "independent_models": True,
        "motor_commands_sent": 0,
        "mj_step_calls": 0,
        "gait_validated": False,
        "real_robot_validated": False,
        "root_cause": "unknown",
        "method": "identical_scene_STAND_keyframe_mj_forward_only",
        "limits": (
            "Only static pose, contact eligibility, compiled friction, "
            "solref and solimp are examined. No dynamic contact forces, "
            "slip, ONNX controller observations, commanded locomotion, "
            "causal intervention, real robot motion or safety validation."
        ),
        "variants": variants,
        "deltas": deltas,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P0g: read-only compiled MuJoCo comparison")
    ap.add_argument("--rl-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        report = compare_variants(args.rl_root)
        args.output.write_text(
            json.dumps(report, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(json.dumps({
            "p0g_variants_compiled": list(report["variants"]),
            "static_groundcontact_pairs": {
                k: v["static_contacts_with_floor"]
                for k,v in report["variants"].items()
            },
            "compiled_geom_counts": {
                k: v["compiled_geom_count_including_floor"]
                for k,v in report["variants"].items()
            },
            "motor_commands_sent": 0,
            "root_cause": "unknown",
            "gait_validated": False,
        }, sort_keys=True))
    except (GroundTruthError, OSError, ValueError, TypeError) as exc:
        print(f"P0g compiled geometry comparison unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
