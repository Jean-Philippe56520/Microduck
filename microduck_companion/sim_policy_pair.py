"""P0i: exactly one bounded policy A/B diagnostic per fresh official MuJoCo run.

This is NOT a robot adapter. Only the pinned clean official headless simulator
is accepted, and *robotd alone* commands actuators. The movement implementation
is the already-tested single J2e walk trial with health, scene, stop and deadman
checks. The separate robotctl CLI is the ONLY permitted policy switch.

A/B can reveal a difference, but one run per arm is NOT causal proof of gait.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tomllib

from .sim_flat_zone import GroundTruthError, verify_body_process
from .sim_motion import SimMotionError
from .sim_policy_contract import (
    EXPECTED_POLICY_SOURCE, MAX_MODEL_BYTES, _sha256_file, verify_oem_sources,
)
from .sim_policy_lineage import MODEL_NAMES, read_sources
from .sim_walk_trial import WALK_SPEED_MPS, WALK_TICKS, run_walk_trial

# The exact v8 model bytes verified in P0h, not a filename-based trust guess.
PINNED_V8_SHA256 = {
    "alpha_walk": "e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c",
    "alpha_stand": "1569268713e40deea795dd2922dba50d3621e15a872855408b6b1b125b1c094b",
    "velstand": "2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492",
}
EXPERIMENT_ARMS = {
    "alpha": ("alpha_walk", "alpha_stand"),
    "velstand": ("velstand", None),
}
TRANSLATION_THRESHOLD_M = 0.01


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise SimMotionError("P0i: " + reason)


def _load_toml(path: Path) -> dict:
    try:
        with path.open("rb") as f:
            result = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SimMotionError("P0i: unreadable simulator config") from exc
    require(isinstance(result.get("policy"), dict), "policy config absent")
    return result["policy"]


def _official_files(state: Path) -> dict[str, Path]:
    root = state / "policies/current"
    try:
        release = root.resolve(strict=True)
        rows = (release / ".source").read_text(encoding="utf-8").splitlines()
        facts = dict(s.split("=", 1) for s in rows if "=" in s)
        manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise SimMotionError("P0i: official policy set metadata unavailable") from exc
    require((facts.get("repo"), facts.get("version")) == EXPECTED_POLICY_SOURCE,
            "unexpected policy seeder source/version")
    require(isinstance(manifest, dict) and isinstance(manifest.get("policies"), list),
            "unexpected policy manifest")
    entries = manifest["policies"]
    require(all(isinstance(item, dict) and isinstance(item.get("file"), str)
                for item in entries), "invalid policy manifest entries")
    names = [item["file"] for item in entries]
    require(len(names) == len(set(names)), "duplicate policy names")
    require(all(n in names for n in MODEL_NAMES.values()),
            "missing policy in official v8 manifest")
    paths = {}
    for role, name in MODEL_NAMES.items():
        try:
            path = (release / name).resolve(strict=True)
            require(path.is_file() and path.parent == release,
                    "policy file outside its release")
            size = path.stat().st_size
        except OSError as exc:
            raise SimMotionError("P0i: missing official policy file") from exc
        require(1000 < size <= MAX_MODEL_BYTES, "unexpected ONNX file size")
        require(_sha256_file(path) == PINNED_V8_SHA256[role],
                "ONNX bytes differ from the verified P0h v8 reference")
        paths[role] = path
    return paths


def _read_live_policies(state: Path, robot_root: Path) -> dict:
    """Query daemon-selected slots via the OEM robotctl read-only list API."""
    ctl = robot_root / "target/debug/robotctl"
    require(ctl.is_file(), "official robotctl unavailable")
    argv = (
        str(ctl),
        "--robot-socket", str(state / "duck-a.sock"),
        "--socket", str(state / "duck-a-updater.sock"),
        "policy", "--file", str(state / "robotd-duck-a.toml"), "list", "--json",
    )
    try:
        result = subprocess.run(argv, check=True, text=True,
                                capture_output=True, timeout=12)
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise SimMotionError("P0i: live robotd policy list failed") from exc
    require(isinstance(payload, dict) and isinstance(payload.get("policies"), dict),
            "unexpected robotctl policy list schema")
    return payload["policies"]


def verify_active_arm(state: Path, robot_root: Path, arm: str) -> dict:
    """Require config AND live daemon slots to match the exact pinned model."""
    require(arm in EXPERIMENT_ARMS, "unknown experiment arm")
    files = _official_files(state)
    policy = _load_toml(state / "robotd-duck-a.toml")
    require(policy.get("enabled") is True and "mode" not in policy,
            "unexpected OEM mode or disabled policies")
    for key in ("action_scale", "standing_action_scale",
                "standing_gain_ratio", "gain", "head_lowpass", "legs_lowpass"):
        require(key not in policy, "non-default tuning override: " + key)
    walk_role, stand_role = EXPERIMENT_ARMS[arm]
    expected_walk = files[walk_role]
    try:
        actual_walk = Path(policy["walk"]).resolve(strict=True)
    except (OSError, TypeError, KeyError) as exc:
        raise SimMotionError("P0i: configured walk path missing") from exc
    require(actual_walk == expected_walk, "wrong walk model in active robotd-duck-a.toml")
    if stand_role is None:
        require(policy.get("stand") == "none",
                "velstand must be the sole gait network (stand = none)")
        expected_stand = None
    else:
        expected_stand = files[stand_role]
        try:
            actual_stand = Path(policy["stand"]).resolve(strict=True)
        except (OSError, TypeError, KeyError) as exc:
            raise SimMotionError("P0i: configured stand path missing") from exc
        require(actual_stand == expected_stand, "wrong standing model in active robotd-duck-a.toml")

    live = _read_live_policies(state, robot_root)
    require(live.get("mode") == "walk" and live.get("enabled") is True,
            "robotd did not report enabled walk mode")
    slots = live.get("slots")
    require(isinstance(slots, list) and all(isinstance(x, dict) for x in slots),
            "invalid robotd policy slot table")
    by_name = {s.get("slot"): s for s in slots}
    require(len(by_name) == len(slots), "duplicated robotd policy slots")
    for name, expect in (("walk", expected_walk), ("stand", expected_stand)):
        row = by_name.get(name)
        require(isinstance(row, dict) and row.get("error") is None,
                "robotd policy slot has error or is missing")
        if expect is None:
            require(row.get("path") is None,
                    "stand slot remains loaded after switching to velstand")
        else:
            actual = row.get("path")
            require(isinstance(actual, str) and Path(actual).resolve() == expect,
                    "robotd live policy path disagrees with config")
    return {
        "arm": arm,
        "walk_model": expected_walk.name,
        "stand_model": expected_stand.name if expected_stand else None,
        "bundle_sha256": dict(PINNED_V8_SHA256),
        "robotd_live_mode": live["mode"],
        "selected_from_live_robotd_policy_list": True,
        "policy_source_record_is_unsigned": True,
    }


def run_arm(state_dir: Path, robot_root: Path, rl_root: Path,
            memory_path: Path, arm: str, *, port: int = 17801) -> dict:
    """One and only one existing J2e trial; refuse before motion if slots differ."""
    require(arm in EXPERIMENT_ARMS, "experiment arm must be alpha or velstand")
    require(port == 17801, "only pinned official simulator port 17801 is allowed")
    state = state_dir.resolve(strict=True)
    robot, rl = robot_root.resolve(strict=True), rl_root.resolve(strict=True)
    verify_oem_sources(robot, rl)
    read_sources(robot, rl)  # fail if OEM slot/lineage source contract changed
    verify_body_process(state, rl, port)
    arm_record = verify_active_arm(state, robot, arm)
    try:
        body_pid = int((state / "body.pid").read_text(encoding="ascii").strip())
    except (OSError, ValueError) as exc:
        raise SimMotionError("P0i: unverified simulator PID") from exc
    require(body_pid > 1, "invalid simulator PID")
    trial = run_walk_trial(state, rl, memory_path, port=port)
    require(trial.commands_sent == WALK_TICKS and trial.stop_confirmed,
            "trial or stop was incomplete")
    require(trial.requested_speed_mps == WALK_SPEED_MPS,
            "different movement speed across arms")
    trace = trial.policy_diagnostics
    require(trace.get("policy_samples") == WALK_TICKS,
            "incomplete robotd policy feedback")
    return {
        "schema_version": 1,
        "experiment": "p0i_two_independent_official_mujoco_boots",
        "arm": arm,
        "official_body_pid": body_pid,
        "policy": arm_record,
        "trial": asdict(trial),
        "commands_sent": trial.commands_sent,
        "stop_confirmed": trial.stop_confirmed,
        "requested_vx_mps": trial.requested_speed_mps,
        "measured_xy_displacement_m": trial.measured_displacement_m,
        "measured_forward_x_m": trial.measured_forward_x_m,
        "measured_lateral_y_m": trial.measured_lateral_y_m,
        "baseline_drift_m": trial.baseline_displacement_m,
        "policy_feedback": trace,
        "reported_outcome": trial.outcome,
        "translation_threshold_m": TRANSLATION_THRESHOLD_M,
        "threshold_met": trial.measured_displacement_m >= TRANSLATION_THRESHOLD_M,
        "gait_validated": False,
        "root_cause": "undetermined",
        "physical_robot_tested": False,
    }


def _number(value: object, key: str, *, maximum: float) -> float:
    require(type(value) in (int, float) and math.isfinite(value)
            and 0 <= value <= maximum, "invalid paired metric: " + key)
    return float(value)


def compare_arms(alpha: dict, velstand: dict) -> dict:
    """Describe only what two completed, independent, bounded runs measured."""
    require(isinstance(alpha, dict) and isinstance(velstand, dict),
            "both experiment outputs required")
    require(alpha.get("arm") == "alpha" and velstand.get("arm") == "velstand",
            "misordered or missing policy arms")
    require(alpha.get("experiment") == velstand.get("experiment")
            == "p0i_two_independent_official_mujoco_boots",
            "unverified experiment identity")
    require(type(alpha.get("official_body_pid")) is int
            and type(velstand.get("official_body_pid")) is int
            and alpha["official_body_pid"] != velstand["official_body_pid"],
            "both arms must use separate body_server processes")
    for arm in (alpha, velstand):
        require(arm.get("stop_confirmed") is True
                and arm.get("commands_sent") == WALK_TICKS
                and arm.get("requested_vx_mps") == WALK_SPEED_MPS,
                "missing stop, count or matching speed")
        require(arm.get("gait_validated") is False
                and arm.get("root_cause") == "undetermined",
                "arm incorrectly claims gait or root cause")
        _number(arm.get("measured_xy_displacement_m"), "distance", maximum=.30)
        _number(arm.get("baseline_drift_m"), "drift", maximum=.005)
        require(isinstance(arm.get("policy"), dict)
                and arm["policy"].get("bundle_sha256") == PINNED_V8_SHA256,
                "arms used mismatched or unverified ONNX bytes")
        require(arm["policy"].get("selected_from_live_robotd_policy_list") is True,
                "no live policy-slot evidence")
        trace = arm.get("policy_feedback")
        require(isinstance(trace, dict)
                and trace.get("policy_samples") == WALK_TICKS,
                "missing policy feedback")
    require(alpha["policy"]["walk_model"] == MODEL_NAMES["alpha_walk"]
            and alpha["policy"]["stand_model"] == MODEL_NAMES["alpha_stand"],
            "alpha model identity mismatch")
    require(velstand["policy"]["walk_model"] == MODEL_NAMES["velstand"]
            and velstand["policy"]["stand_model"] is None,
            "velstand-only identity mismatch")

    a = alpha["measured_xy_displacement_m"]
    b = velstand["measured_xy_displacement_m"]
    # The last 24 notifications include a tiny initial stand/transition window.
    # As long as a model reports walk and robotd applied the command at least
    # once, a failed run is still a measured outcome, not a successful gait.
    control_ok = all(
        arm["policy_feedback"].get("walk_policy_samples", 0) >= WALK_TICKS - 4
        and arm["policy_feedback"].get("max_applied_vx_mps", 0) >= .10
        for arm in (alpha, velstand)
    )
    return {
        "schema_version": 1,
        "source": "pinned_headless_mujoco_two_clean_boots",
        "per_arm": {
            "alpha": {
                "net_xy_m": a, "forward_x_m": alpha["measured_forward_x_m"],
                "lateral_y_m": alpha["measured_lateral_y_m"],
                "baseline_m": alpha["baseline_drift_m"],
                "outcome": alpha["reported_outcome"],
                "walk_policy_samples": alpha["policy_feedback"]["walk_policy_samples"],
                "max_applied_vx_mps": alpha["policy_feedback"]["max_applied_vx_mps"],
                "stop_confirmed": True,
            },
            "velstand": {
                "net_xy_m": b, "forward_x_m": velstand["measured_forward_x_m"],
                "lateral_y_m": velstand["measured_lateral_y_m"],
                "baseline_m": velstand["baseline_drift_m"],
                "outcome": velstand["reported_outcome"],
                "walk_policy_samples": velstand["policy_feedback"]["walk_policy_samples"],
                "max_applied_vx_mps": velstand["policy_feedback"]["max_applied_vx_mps"],
                "stop_confirmed": True,
            },
        },
        "distance_difference_velstand_minus_alpha_m": b-a,
        "both_arms_observed_requested_control": control_ok,
        "alpha_exceeds_10mm_threshold": a >= TRANSLATION_THRESHOLD_M,
        "velstand_exceeds_10mm_threshold": b >= TRANSLATION_THRESHOLD_M,
        "motor_commands_total": WALK_TICKS * 2,
        "explicit_stop_confirmations": 2,
        "one_bounded_trial_per_arm": True,
        "robotd_sole_motor_authority": True,
        "simulated_displacement_is_not_validated_gait": True,
        "causal_root_cause_proven": False,
        "physical_hardware_validated": False,
        "limitations": (
            "One trial per arm is a preliminary comparison, not a controlled "
            "repeatability or gait/contact proof. The velstand arm uses the "
            "official robotctl live policy load then returns to a stable "
            "baseline; unlike initial alpha startup, the swap history can be "
            "a confounder. No contacts or motor targets are accessible through "
            "the official read-only body API. No physical robot involved."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="P0i: simulator-only bounded A/B walking comparison")
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--arm", choices=tuple(EXPERIMENT_ARMS))
    modes.add_argument("--compare", action="store_true")
    p.add_argument("--state-dir", type=Path)
    p.add_argument("--robot-root", type=Path)
    p.add_argument("--rl-root", type=Path)
    p.add_argument("--memory", type=Path)
    p.add_argument("--alpha-json", type=Path)
    p.add_argument("--velstand-json", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--enable-once", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.compare:
            require(args.alpha_json is not None and args.velstand_json is not None,
                    "compare requires both saved arm reports")
            report = compare_arms(
                json.loads(args.alpha_json.read_text(encoding="utf-8")),
                json.loads(args.velstand_json.read_text(encoding="utf-8")),
            )
        else:
            require(args.enable_once and os.environ.get("MICRODUCK_SIM_P0I") == "YES",
                    "motor test needs --enable-once and MICRODUCK_SIM_P0I=YES")
            require(all(x is not None for x in (
                args.state_dir, args.robot_root, args.rl_root, args.memory
            )), "simulator roots and separate SQLite path required")
            report = run_arm(
                args.state_dir, args.robot_root, args.rl_root, args.memory,
                args.arm,
            )
        args.output.write_text(json.dumps(
            report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({
            "mode": args.arm or "compare",
            "comparison": report.get("distance_difference_velstand_minus_alpha_m"),
            "distance_m": report.get("measured_xy_displacement_m"),
            "stop_confirmed": report.get("stop_confirmed"),
            "both_arms_observed_requested_control":
                report.get("both_arms_observed_requested_control"),
            "gait_validated": False,
            "causal_root_cause_proven": False,
        }, sort_keys=True))
        return 0
    except (SimMotionError, GroundTruthError, OSError, ValueError, TypeError, KeyError,
            RuntimeError, subprocess.SubprocessError) as exc:
        print("P0i refused or aborted: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
