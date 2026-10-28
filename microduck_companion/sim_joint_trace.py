"""P0a: bounded, passive joint/body trace of the pinned OFFICIAL MuJoCo server.

The only body operations are hello/read. The only robotd operation is
robot.subscribe. This tool never sends robot.move, robot.stop or joint targets,
and it cannot be used to authorize motion on a real robot.

IMPORTANT: The pinned body_server exposes joint positions, velocities and a
simulated current *proxy*, but NOT contact pairs or actuator targets. Optional
--joint-tracking reuses robotd's OWN single-tick joint/target telemetry, not
body_server data.ctrl or a proof of a completed motor write. Foot contacts
and actual actuator targets remain unknown.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

from .sim_flat_zone import (
    FLAT_SCENE_BLOB, GroundTruthError, JOINT_COUNT, RL_COMMIT,
    parse_flat_frame, read_verified_body_state,
)
from .sim_ipc import Notification, ReadOnlyUnixRpc, TelemetryError
from .sim_policy_trace import PolicySample, parse_policy_sample, summarize_policy_samples

# The pinned OEM body_server's wire order, including unactuated mouth (index 9).
JOINT_NAMES = (
    "left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee",
    "left_ankle", "neck_pitch", "head_pitch", "head_yaw", "head_roll",
    "mouth", "right_hip_yaw", "right_hip_roll", "right_hip_pitch",
    "right_knee", "right_ankle",
)
assert len(JOINT_NAMES) == JOINT_COUNT

MAX_SAMPLES = 40
MAX_POLICY_SKEW_S = 0.45
MAX_ROBOTD_FRAME_AGE_S = 0.35
MAX_ROBOTD_FUTURE_S = 0.03
# Exact duck-sim policy selection in OEM 942e58e3; no switching or loading here.
EXPECTED_DUCK_SIM_POLICY = ("alpha_walking.onnx", "alpha_stand.onnx")
LEG_INDICES = (0, 1, 2, 3, 4, 10, 11, 12, 13, 14)


def _vector(payload: dict, field: str, *, nonnegative: bool = False) -> list[float]:
    values = payload.get(field)
    if not isinstance(values, list) or len(values) != JOINT_COUNT:
        raise GroundTruthError(f"body.{field} must have exactly {JOINT_COUNT} joints")
    if any(type(value) not in (int, float) or not math.isfinite(value)
           or (nonnegative and value < 0) for value in values):
        raise GroundTruthError(f"body.{field} contains an invalid joint value")
    return [float(value) for value in values]


def _quaternion_or_unknown(payload: dict) -> list[float] | None:
    """The OEM reports the full trunk orientation under imu.quat.

    Old traces and synthetic tests may lack it: mark it UNKNOWN rather than
    fabricating a horizontal trunk. A replay requires all four valid values.
    """
    imu = payload.get("imu", {})
    quat = imu.get("quat") if isinstance(imu, dict) else None
    if quat is None:
        return None
    if (not isinstance(quat, list) or len(quat) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in quat)):
        raise GroundTruthError("invalid simulator trunk quaternion")
    norm = math.sqrt(sum(float(v) ** 2 for v in quat))
    if not math.isfinite(norm) or abs(norm - 1.0) > 0.01:
        raise GroundTruthError("simulator trunk quaternion is not unit length")
    return [float(v) / norm for v in quat]


def parse_joint_observation(payload: dict, observed_at: float) -> dict:
    """Parse only telemetry the pinned body_server actually publishes."""
    pose = parse_flat_frame(payload, observed_at)
    return {
        "observed_monotonic_s": pose.observed_at,
        "sim_time_s": pose.sim_time_s,
        "trunk_xyz_m": [pose.x_m, pose.y_m, pose.z_m],
        "trunk_quat_wxyz": _quaternion_or_unknown(payload),
        "flat_scene_safe_area": pose.safe_area,
        "positions_rad": _vector(payload, "positions"),
        "velocities_rad_s": _vector(payload, "velocities"),
        # OEM uses abs(simulated actuator force) * 100, NOT calibrated amps.
        "reported_currents_ma_proxy": _vector(payload, "currents_ma", nonnegative=True),
        # No actual contact or actuator target observation exists in this API.
        "foot_contacts": None,
        "joint_targets_rad": None,
    }


def _join_policy(observation: dict, policy: PolicySample) -> None:
    observed = observation["observed_monotonic_s"]
    if (type(policy.received_at) not in (float, int)
            or not math.isfinite(policy.received_at)
            or policy.received_at < 0
            or abs(policy.received_at - observed) > MAX_POLICY_SKEW_S):
        raise TelemetryError("robot.state and MuJoCo observations are not time-aligned")
    observation["policy_received_monotonic_s"] = policy.received_at
    observation["policy_skew_s"] = policy.received_at - observed
    observation["robotd"] = {
        "policy": policy.policy,
        # vx, vy in m/s; vyaw in rad/s. These are body intentions,
        # NOT per-joint motor targets or proof of effective translation.
        "requested_vx_vy_mps_vyaw_rad_s": list(policy.requested),
        "applied_vx_vy_mps_vyaw_rad_s": list(policy.applied),
        "limited_by": list(policy.limited_by),
    }



def _verify_alpha_subscription(ack: dict) -> dict:
    """Confirm policy names from robotd's OEM subscription acknowledgement.

    Names are not file hashes or live inference evidence. Require the known
    duck-sim alpha slots so an unexpected policy is not silently compared.
    """
    if (not isinstance(ack, dict) or ack.get("accepted") is not True
            or ack.get("walk") != EXPECTED_DUCK_SIM_POLICY[0]
            or ack.get("stand") != EXPECTED_DUCK_SIM_POLICY[1]
            or ack.get("unavailable") is not None):
        raise TelemetryError("robotd subscription policy differs from pinned duck-sim alpha slots")
    return {"walk": ack["walk"], "stand": ack["stand"],
            "identity_only_not_model_hash": True}


def _robotd_joint_vector(payload: dict, field: str) -> list[float]:
    values = payload.get(field)
    if (not isinstance(values, list) or len(values) != JOINT_COUNT
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in values)):
        raise TelemetryError(f"invalid robot.state.{field}: expected 15 finite joint radians")
    return [float(v) for v in values]


def parse_robotd_joint_tracking(note: Notification, body_received_at: float) -> dict:
    """Pair measured joints and controller targets from ONE OEM robot.state tick.

    The two arrays in robot.state share a tick but targets are from robotd's
    control calculation BEFORE safety.apply/write confirmation. The independently
    read MuJoCo body pose is nearby in time, never asserted to be that tick.
    """
    if note.method != "robot.state":
        raise TelemetryError("robotd joint tracking expects robot.state")
    t_ns = note.params.get("t_ns")
    if type(t_ns) is not int or t_ns <= 0:
        raise TelemetryError("missing or invalid robot.state monotonic tick t_ns")
    tick_s = t_ns / 1_000_000_000
    if (type(note.received_at) not in (int, float)
            or not math.isfinite(note.received_at)):
        raise TelemetryError("invalid robot.state receipt time")
    age_s = float(note.received_at) - tick_s
    if not -MAX_ROBOTD_FUTURE_S <= age_s <= MAX_ROBOTD_FRAME_AGE_S:
        raise TelemetryError("stale or future robot.state tick")
    if (type(body_received_at) not in (int, float)
            or not math.isfinite(body_received_at)):
        raise TelemetryError("invalid MuJoCo body receipt time")
    skew_s = tick_s - float(body_received_at)
    if abs(skew_s) > MAX_POLICY_SKEW_S:
        raise TelemetryError("robot.state tick and MuJoCo body read too far apart")
    measured = _robotd_joint_vector(note.params, "joints")
    targets = _robotd_joint_vector(note.params, "targets")
    return {
        "robotd_tick_monotonic_ns": t_ns,
        "robotd_state_receive_age_s": age_s,
        "robotd_tick_vs_body_read_skew_s": skew_s,
        "measured_joints_rad": measured,
        "controller_targets_rad": targets,
        "controller_target_minus_measured_rad": [
            target - joint for target, joint in zip(targets, measured)
        ],
        "target_before_safety_write_not_motor_effect": True,
    }


def _summarize_robotd_tracking(observations: list[dict]) -> dict:
    frames = [o["robotd_joint_tracking"] for o in observations]
    measured = [f["measured_joints_rad"] for f in frames]
    targets = [f["controller_targets_rad"] for f in frames]
    errors = [f["controller_target_minus_measured_rad"] for f in frames]
    return {
        "sample_count": len(frames),
        "leg_target_range_rad": {
            JOINT_NAMES[j]: max(f[j] for f in targets) - min(f[j] for f in targets)
            for j in LEG_INDICES
        },
        "leg_measured_range_rad": {
            JOINT_NAMES[j]: max(f[j] for f in measured) - min(f[j] for f in measured)
            for j in LEG_INDICES
        },
        "leg_peak_abs_target_minus_measured_rad": {
            JOINT_NAMES[j]: max(abs(f[j]) for f in errors)
            for j in LEG_INDICES
        },
        "max_state_age_at_receive_s": max(f["robotd_state_receive_age_s"] for f in frames),
        "max_abs_robotd_tick_vs_body_read_skew_s": max(
            abs(f["robotd_tick_vs_body_read_skew_s"]) for f in frames
        ),
        "motor_write_or_contact_verified": False,
        "locomotion_validated": False,
    }

def _summarize(observations: list[dict], policies: list[PolicySample]) -> dict:
    first, last = observations[0], observations[-1]
    positions = [entry["positions_rad"] for entry in observations]
    velocities = [entry["velocities_rad_s"] for entry in observations]
    path_length = sum(
        math.hypot(b["trunk_xyz_m"][0] - a["trunk_xyz_m"][0],
                   b["trunk_xyz_m"][1] - a["trunk_xyz_m"][1])
        for a, b in zip(observations, observations[1:])
    )
    return {
        "sample_count": len(observations),
        "sim_duration_s": last["sim_time_s"] - first["sim_time_s"],
        "net_trunk_xy_displacement_m": math.hypot(
            last["trunk_xyz_m"][0] - first["trunk_xyz_m"][0],
            last["trunk_xyz_m"][1] - first["trunk_xyz_m"][1],
        ),
        "trunk_xy_path_length_m": path_length,
        "max_abs_policy_time_skew_s": max(abs(o["policy_skew_s"]) for o in observations),
        "joint_position_range_rad": {
            name: max(p[j] for p in positions) - min(p[j] for p in positions)
            for j, name in enumerate(JOINT_NAMES)
        },
        "peak_abs_joint_velocity_rad_s": {
            name: max(abs(v[j]) for v in velocities)
            for j, name in enumerate(JOINT_NAMES)
        },
        "robotd_policy": summarize_policy_samples(policies),
        "locomotion_validated": False,
        "gait_contact_evidence": None,
    }


def collect_joint_trace(
    state_dir: str | Path, rl_root: str | Path, *, port: int = 17801,
    samples: int = 8, hz: int = 5,
    verified_viewer: bool = False,
    joint_tracking: bool = False,
) -> dict:
    """Bounded passive trace, strictly tied to the pinned official simulator.

    Every body read re-verifies the pinned scene and the body_server process
    before and after the read. No snapshot here is permitted as real-world
    safety or a successful walking-gait certificate.
    """
    if type(verified_viewer) is not bool:
        raise ValueError("verified_viewer must be boolean")
    if type(joint_tracking) is not bool:
        raise ValueError("joint_tracking must be boolean")
    if type(samples) is not int or not 1 <= samples <= MAX_SAMPLES:
        raise ValueError(f"samples must be an integer in [1,{MAX_SAMPLES}]")
    if type(hz) is not int or not 1 <= hz <= 10:
        raise ValueError("hz must be an integer in [1,10]")
    state = Path(state_dir)
    observations: list[dict] = []
    policies: list[PolicySample] = []
    prior_sim_time: float | None = None
    prior_robotd_ns: int | None = None
    with ReadOnlyUnixRpc(state / "duck-a.sock", timeout_s=0.6, role="robotd") as stream:
        subscription = stream.request("robot.subscribe", hz=hz)
        policy_identity = (_verify_alpha_subscription(subscription)
                           if joint_tracking else None)
        for _ in range(samples):
            tick_started = time.monotonic()
            if verified_viewer:
                payload, observed_at = read_verified_body_state(
                    state, rl_root, port=port, allow_viewer=True)
            else:
                payload, observed_at = read_verified_body_state(state, rl_root, port=port)
            observation = parse_joint_observation(payload, observed_at)
            if (prior_sim_time is not None
                    and observation["sim_time_s"] <= prior_sim_time):
                raise GroundTruthError("simulator clock did not advance between joint samples")
            note = stream.next_notification()
            policy = parse_policy_sample(note)
            _join_policy(observation, policy)
            if joint_tracking:
                if policy.policy not in ("stand", "walk", "held"):
                    raise TelemetryError("unexpected active OEM skill in leg tracking")
                frame = parse_robotd_joint_tracking(
                    note, observation["observed_monotonic_s"])
                now_ns = frame["robotd_tick_monotonic_ns"]
                if prior_robotd_ns is not None and now_ns <= prior_robotd_ns:
                    raise TelemetryError("robot.state tick clock did not advance")
                observation["robotd_joint_tracking"] = frame
                prior_robotd_ns = now_ns
            prior_sim_time = observation["sim_time_s"]
            observations.append(observation)
            policies.append(policy)
            remaining = 1.0 / hz - (time.monotonic() - tick_started)
            if remaining > 0 and len(observations) < samples:
                time.sleep(remaining)
    summary = _summarize(observations, policies)
    if joint_tracking:
        summary["robotd_joint_tracking"] = _summarize_robotd_tracking(observations)
    return {
        "schema_version": 2 if joint_tracking else 1,
        "mode": "passive_read_only",
        "verified_viewer_opt_in": verified_viewer,
        "joint_tracking_opt_in": joint_tracking,
        "robotd_subscribed_policy_names": policy_identity,
        "source": "pinned_official_mujoco_body_and_robotd",
        "rl_commit": RL_COMMIT,
        "flat_scene_git_blob": FLAT_SCENE_BLOB,
        "joint_names_wire_order": list(JOINT_NAMES),
        "mouth_index_unactuated": 9,
        "sampling_requested_hz": hz,
        "commands_sent": 0,
        "foot_contacts_available": False,
        "joint_targets_available": False,
        "robotd_controller_targets_available": joint_tracking,
        "missing_reason": "body_server_read_does_not_expose_actuator_targets_or_contacts",
        "currents_warning": "OEM simulation proxy: abs(actuator_force) * 100, not calibrated mA",
        "observations": observations,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0a passive joint trace; MuJoCo only")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--rl-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=17801)
    parser.add_argument("--verified-viewer", action="store_true",
                        help="read-only trace of the exact OEM GUI launch, never motor authorization")
    parser.add_argument("--joint-tracking", action="store_true",
                        help="read same-tick robotd joints/targets; no motor write proof")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--hz", type=int, default=5)
    parser.add_argument("--output", type=Path,
                        help="optional JSON trace output, e.g. CI diagnostic artifact")
    args = parser.parse_args(argv)
    try:
        result = collect_joint_trace(
            args.state_dir, args.rl_root, port=args.port,
            samples=args.samples, hz=args.hz,
            verified_viewer=args.verified_viewer,
            joint_tracking=args.joint_tracking,
        )
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
        if args.output is not None:
            args.output.write_text(encoded + "\n", encoding="utf-8")
        if args.joint_tracking and args.output is not None:
            # Keep detailed pose/target telemetry local, print only aggregate data.
            print(json.dumps({
                "output_file": str(args.output),
                "commands_sent": 0,
                "robotd_subscribed_policy_names": result["robotd_subscribed_policy_names"],
                "summary": result["summary"]["robotd_joint_tracking"],
            }, indent=2, sort_keys=True, allow_nan=False))
        else:
            print(encoded)
    except (GroundTruthError, TelemetryError, ValueError, OSError) as exc:
        print(f"P0a read-only trace unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
