"""P0f: passive contract audit of the pinned official walking ONNX and robotd.

This diagnostic NEVER invokes a motor API or changes an OEM config/policy.
ONNX calls use an independent, zero-state CPU session on synthetic, labeled
observations, NOT robotd's unobservable in-loop inputs, LSTM state, or actions.
It cannot establish gait, policy parity on live ticks, or training equivalence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET

from .sim_flat_zone import RL_COMMIT, GroundTruthError, verify_body_process, verify_flat_scene

OEM_COMMIT = "942e58e3aa6dbb28e7037203fff11866122c7567"
OBS_WIDTH = 61
ACTION_WIDTH = 14
JOINTS_WITH_MOUTH = (
    "left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee",
    "left_ankle", "neck_pitch", "head_pitch", "head_yaw", "head_roll",
    "mouth", "right_hip_yaw", "right_hip_roll", "right_hip_pitch",
    "right_knee", "right_ankle",
)
EXPECTED_POLICY_SOURCE = ("pollen-robotics/microduck-policies", "v8")
MAX_MODEL_BYTES = 24 * 1024 * 1024


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise GroundTruthError("P0f: " + reason)


def _source(root: Path, name: str) -> str:
    try:
        return (root / name).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GroundTruthError(f"P0f: cannot read pinned {name}") from exc


def verify_oem_sources(robot_root: Path, rl_root: Path) -> None:
    verify_flat_scene(rl_root)
    try:
        sha = subprocess.run(
            ("git", "-C", str(robot_root), "rev-parse", "HEAD"),
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ("git", "-C", str(robot_root), "status", "--porcelain",
             "--untracked-files=no"),
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise GroundTruthError("P0f: cannot verify pinned official robotd") from exc
    _require(sha == OEM_COMMIT and not dirty, "OEM robotd revision or tracked files differ")


def _read_home_training(src: str) -> dict[str, float]:
    match = re.search(
        r"HOME_FRAME\s*=\s*EntityCfg\.InitialStateCfg\(\s*joint_pos\s*=\s*\{(.*?)\}\s*,\s*joint_vel",
        src, re.S,
    )
    _require(match is not None, "training HOME_FRAME missing")
    rules = [
        (rule, float(value)) for rule, value in re.findall(
            r'r"([^"]+)"\s*:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)',
            match.group(1),
        )
    ]
    expected = {}
    for name in JOINTS_WITH_MOUTH:
        if name == "mouth":
            continue
        fits = [value for rule, value in rules if re.fullmatch(rule, name)]
        _require(bool(fits), f"training HOME_FRAME does not match {name}")
        expected[name] = fits[0]
    return expected


def _read_home_runtime(src: str) -> dict[str, float]:
    m = re.search(r"pub const DEFAULT_POSITION:[^=]*=\s*\[(.*?)\];", src, re.S)
    _require(m is not None, "robotd home pose declaration missing")
    values = {}
    for raw in m.group(1).splitlines():
        entry = re.search(
            r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*,\s*//\s*(\w+)",
            raw,
        )
        if entry:
            values[entry.group(2)] = float(entry.group(1))
    _require(set(values) == set(JOINTS_WITH_MOUTH), "runtime home joint mapping incomplete")
    return values


def compare_pinned_source_contract(robot_root: Path, rl_root: Path) -> dict:
    obs = _source(robot_root, "duck-control/src/obs.rs")
    controller = _source(robot_root, "robotd/src/control.rs")
    policy = _source(robot_root, "duck-control/src/policy.rs")
    model = _source(robot_root, "duck-control/src/model.rs")
    rl = _source(rl_root, "src/mjlab_microduck/robot/microduck_constants.py")
    training = _source(rl_root, "src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py")
    training_velstand = _source(rl_root, "src/mjlab_microduck/tasks/microduck_velstand_env_cfg.py")
    scene = _source(rl_root, "src/mjlab_microduck/robot/microduck/scene.xml")

    for expected in (
        "pub const OBS_LEN: usize = 61;",
        "pub const ACTION_LEN: usize = 14;",
        "let angles = policy_joints(joint_positions);",
        "fill(positions, std::array::from_fn(|i| angles[i] - home[i]));",
        "*previous_action = *last_action;",
    ):
        _require(expected in obs, "runtime observation contract changed: " + expected)
    for expected in (
        '\"obs\" => &input',
        "check_matrix(path, outlet(path, inputs, \"obs\")?, OBS_LEN)?;",
        "check_matrix(path, action, ACTION_LEN)?;",
    ):
        _require(expected in policy, "OEM ONNX contract changed: " + expected)
    for expected in (
        "action_scale: 0.9,",
        "standing_action_scale: 1.0,",
        "head_lowpass: Some(0.5),",
        "legs_lowpass: Some(0.7),",
        "targets[joint] = DEFAULT_POSITION[joint] + scale * offsets[joint];",
        "self.last_action = action;",
    ):
        _require(expected in controller, "OEM target conversion changed: " + expected)
    for expected in (
        "joint_pos_action.scale = 1.0",
        "MICRODUCK_WALK_ROBOT_CFG",
        "USE_PROJECTED_GRAVITY = True",
    ):
        _require(expected in training, "training locomotion contract changed: " + expected)
    _require(
        'cfg.scene.entities = {"robot": MICRODUCK_ALLCOLLISIONS_ROBOT_CFG}'
        in training_velstand,
        "velstand training robot variant changed",
    )
    _require('<include file="robot_groundcontact.xml" />' in scene,
             "official headless scene variant changed")
    _require('spec_fn=get_walk_spec' in rl and
             'MICRODUCK_WALK_XML: Path = _ROBOT_DIR / "robot_walk.xml"' in rl,
             "training walk geometry variant changed")
    home_rt = _read_home_runtime(model)
    home_rl = _read_home_training(rl)
    deviations = {
        name: home_rt[name] - home_rl[name] for name in home_rl
    }
    _require(all(math.isfinite(v) and abs(v) < 1e-4 for v in deviations.values()),
             "home pose differs between training and robotd")
    _require("joint_pos_action.scale = 1.0" in training and
             "action_scale: 0.9," in controller,
             "action scaling source not verified")
    collision = {}
    robot_dir = rl_root / "src/mjlab_microduck/robot/microduck"
    for name in ("robot_walk.xml", "robot_groundcontact.xml", "robot_allcollisions.xml"):
        try:
            tree = ET.parse(robot_dir / name)
        except (ET.ParseError, OSError) as exc:
            raise GroundTruthError(f"P0f: missing training/runtime model {name}") from exc
        geoms = tree.findall(".//geom")
        collision[name] = {
            "geom_total": len(geoms),
            "explicit_collision_class": sum(
                g.get("class") == "collision" for g in geoms),
            "named_sole_geoms": sorted(
                g.get("name") for g in geoms
                if g.get("name") in
                ("left_foot_collision", "right_foot_collision")
            ),
        }
    _require(all(len(v["named_sole_geoms"]) == 2 for v in collision.values()),
             "training/runtime foot geometry names are not both present")
    return {
        "observation_width": OBS_WIDTH,
        "action_width": ACTION_WIDTH,
        "observation_layout": {
            "angular_velocity": [0, 3],
            "gravity_projected": [3, 6],
            "joint_positions_minus_home": [6, 20],
            "joint_velocities": [20, 34],
            "previous_raw_action": [34, 48],
            "command_twist": [48, 51],
            "command_head": [51, 55],
            "command_body_xyz_roll_pitch_yaw": [55, 61],
        },
        "home_pose_max_abs_deviation_rad": max(abs(v) for v in deviations.values()),
        "home_pose_14_joints_match": True,
        "runtime_action_scale": 0.9,
        "training_position_action_scale_source_value": 1.0,
        "runtime_leg_lowpass_new_target_weight": 0.7,
        "runtime_head_lowpass_new_target_weight": 0.5,
        "runtime_stand_action_scale": 1.0,
        "runtime_policy_joint_order_without_mouth": [
            name for name in JOINTS_WITH_MOUTH if name != "mouth"
        ],
        "training_robot_variant_for_velocity": "robot_walk.xml",
        "training_robot_variant_for_velstand": "robot_allcollisions.xml",
        "headless_runtime_robot_variant": "robot_groundcontact.xml",
        "robot_geometry_sources_differ": True,
        "geometry_inventory": collision,
        "different_source_config_is_not_proof_of_incompatible_policy": True,
    }


def policy_paths(state_dir: Path) -> tuple[dict[str, Path], dict]:
    try:
        config = tomllib.loads(
            (state_dir / "robotd.toml").read_text(encoding="utf-8")
        )
        values = config["policy"]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise GroundTruthError("P0f: missing or invalid official robotd policy TOML") from exc
    _require(values.get("enabled") is True, "policy disabled")
    paths = {}
    for key, name in (("walk", "alpha_walking.onnx"),
                      ("stand", "alpha_stand.onnx")):
        _require(isinstance(values.get(key), str), "missing policy " + key)
        expected = state_dir / "policies" / "current" / name
        try:
            current = Path(values[key]).resolve(strict=True)
            pinned = expected.resolve(strict=True)
        except OSError as exc:
            raise GroundTruthError("P0f: missing seeded official policy") from exc
        _require(current == pinned, "non-official policy path for " + key)
        _require(current.is_file() and 1000 < current.stat().st_size <= MAX_MODEL_BYTES,
                 "unexpected policy artifact size")
        paths[key] = current
    source = (state_dir / "policies/current/.source")
    try:
        facts = dict(
            line.split("=", 1) for line in source.read_text().splitlines()
            if "=" in line
        )
    except OSError as exc:
        raise GroundTruthError("P0f: official policy source record absent") from exc
    _require((facts.get("repo"), facts.get("version")) == EXPECTED_POLICY_SOURCE,
             "policy set does not match pinned seeder's expected source")
    return paths, {
        "repo": facts["repo"], "version": facts["version"],
        "source_is_a_local_provenance_claim_not_a_signature": True,
    }


def _tensor_matrix(meta, width: int, label: str) -> None:
    shape = meta.shape
    _require(meta.type == "tensor(float)", f"{label} tensor must be float32")
    _require(len(shape) == 2 and shape[1] == width and
             (shape[0] == 1 or isinstance(shape[0], str) or shape[0] is None),
             f"{label} unexpected matrix shape: {shape}")


def inspect_session(session) -> dict:
    inputs, outputs = session.get_inputs(), session.get_outputs()
    in_map = {x.name: x for x in inputs}
    out_map = {x.name: x for x in outputs}
    _require(len(in_map) == len(inputs) and len(out_map) == len(outputs),
             "duplicated ONNX input/output names")
    _require("obs" in in_map, "ONNX observation input missing")
    _tensor_matrix(in_map["obs"], OBS_WIDTH, "obs")
    if len(inputs) == 1 and len(outputs) == 1:
        action_name = outputs[0].name
        recurrent = False
        state_shape = None
    elif (len(inputs) == 3 and len(outputs) == 3 and
          set(in_map) == {"obs", "h_in", "c_in"} and
          set(out_map) == {"actions", "h_out", "c_out"}):
        action_name = "actions"
        recurrent = True
        states = [in_map[k].shape for k in ("h_in", "c_in")] + [
            out_map[k].shape for k in ("h_out", "c_out")
        ]
        first = states[0]
        _require(all(len(s) == 3 and isinstance(s[0], int) and s[0] > 0
                     and isinstance(s[2], int) and s[2] > 0
                     and (s[1] in (None, 1) or isinstance(s[1], str))
                     for s in states),
                 "invalid LSTM state dimensions")
        _require(all(s[0] == first[0] and s[2] == first[2] for s in states),
                 "incompatible LSTM state sizes")
        _require(all(x.type == "tensor(float)" for k, x in in_map.items()
                     if k != "obs") and
                 all(x.type == "tensor(float)" for k, x in out_map.items()
                     if k != "actions"),
                 "non-float LSTM state")
        state_shape = [first[0], 1, first[2]]
    else:
        raise GroundTruthError("P0f: unsupported ONNX input/output contract")
    _tensor_matrix(out_map[action_name], ACTION_WIDTH, "actions")
    return {
        "recurrent": recurrent,
        "state_shape": state_shape,
        "action_name": action_name,
        "inputs": {m.name: list(m.shape) for m in inputs},
        "outputs": {m.name: list(m.shape) for m in outputs},
    }


def independent_probe(session, contract: dict, vx: float) -> list[float]:
    """Fresh synthetic, zero-history observation; NEVER live robotd inference."""
    import numpy as np
    obs = np.zeros((1, OBS_WIDTH), dtype=np.float32)
    obs[0, 3:6] = [0.0, 0.0, -1.0]
    obs[0, 48:51] = [vx, 0.0, 0.0]
    feeds = {"obs": obs}
    if contract["recurrent"]:
        shape = contract["state_shape"]
        feeds["h_in"] = np.zeros(shape, dtype=np.float32)
        feeds["c_in"] = np.zeros(shape, dtype=np.float32)
    result = session.run([contract["action_name"]], feeds)[0]
    _require(result.shape == (1, ACTION_WIDTH), "ONNX output shape changed during inference")
    values = [float(x) for x in result[0]]
    _require(all(math.isfinite(x) for x in values), "ONNX action is nonfinite")
    return values


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_policy_contract(
    robot_root: Path, rl_root: Path, state_dir: Path, *, ort=None,
    check_process: bool = True,
) -> dict:
    verify_oem_sources(robot_root, rl_root)
    if check_process:
        verify_body_process(state_dir, rl_root, 17801)
    sources = compare_pinned_source_contract(robot_root, rl_root)
    paths, provenance = policy_paths(state_dir)
    if ort is None:
        import onnxruntime as ort
    policy_report = {}
    for key, path in paths.items():
        session = ort.InferenceSession(
            str(path), providers=["CPUExecutionProvider"]
        )
        contract = inspect_session(session)
        neutral = independent_probe(session, contract, 0.0)
        forward = independent_probe(session, contract, 0.12) if key == "walk" else None
        policy_report[key] = {
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "onnx_contract": contract,
            "synthetic_zero_history_zero_twist_raw_actions": neutral,
            "synthetic_zero_history_forward_0_12_raw_actions": forward,
            "fresh_session_zero_hidden_state_each_probe": True,
            "not_a_capture_of_robotd_policy_observation_or_action": True,
        }
        if forward is not None:
            policy_report[key]["raw_action_delta_l2"] = math.sqrt(
                sum((a-b)**2 for a,b in zip(forward,neutral))
            )
    return {
        "schema_version": 1,
        "source": "pinned_official_repository_and_offline_onnx_cpu_sessions",
        "revisions": {"microduck": OEM_COMMIT, "microduck_rl": RL_COMMIT},
        "policy_source_record": provenance,
        "contract": sources,
        "models": policy_report,
        "motor_commands_sent": 0,
        "modified_oem_files": False,
        "observed_robotd_input_or_raw_output": False,
        "gait_validated": False,
        "root_cause": "unknown",
        "limitations": (
            "ONNX metadata and independent synthetic inference do not reveal "
            "the 61-D observations, history, recurrent state or 14 raw actions "
            "used by the running robotd. No tick-aligned policy-to-actuator "
            "comparison is possible without a separately verified read-only "
            "diagnostic. Different training/runtime geometry variants and "
            "action scaling are factual source differences, not causal proof. "
            "This audit does not validate physical robot locomotion."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0f pinned policy contract audit, no motor writes")
    parser.add_argument("--robot-root", type=Path, required=True)
    parser.add_argument("--rl-root", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit_policy_contract(
            args.robot_root.resolve(strict=True),
            args.rl_root.resolve(strict=True),
            args.state_dir.resolve(strict=True),
        )
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "walk_sha256": result["models"]["walk"]["sha256"],
            "stand_sha256": result["models"]["stand"]["sha256"],
            "onnx_shapes_verified": True,
            "home_pose_max_abs_deviation_rad":
                result["contract"]["home_pose_max_abs_deviation_rad"],
            "synthetic_walk_forward_delta_l2":
                result["models"]["walk"]["raw_action_delta_l2"],
            "training_robot_variant_for_velocity":
                result["contract"]["training_robot_variant_for_velocity"],
            "headless_runtime_robot_variant":
                result["contract"]["headless_runtime_robot_variant"],
            "observed_robotd_input_or_raw_output": False,
            "motor_commands_sent": 0,
            "gait_validated": False,
        }, sort_keys=True))
        return 0
    except (GroundTruthError, OSError, ValueError, KeyError, TypeError,
            RuntimeError, ImportError) as exc:
        print(f"P0f policy contract audit rejected: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
