"""P0a: bounded, passive joint/body trace of the pinned OFFICIAL MuJoCo server.

The only body operations are hello/read. The only robotd operation is
robot.subscribe. This tool never sends robot.move, robot.stop or joint targets,
and it cannot be used to authorize motion on a real robot.

IMPORTANT: The pinned body_server exposes joint positions, velocities and a
simulated current *proxy*, but NOT contact pairs or joint target commands.
Missing contacts and targets are recorded as unknown, never inferred.
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
from .sim_ipc import ReadOnlyUnixRpc, TelemetryError
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
) -> dict:
    """Bounded passive trace, strictly tied to the pinned official simulator.

    Every body read re-verifies the pinned scene and the body_server process
    before and after the read. No snapshot here is permitted as real-world
    safety or a successful walking-gait certificate.
    """
    if type(samples) is not int or not 1 <= samples <= MAX_SAMPLES:
        raise ValueError(f"samples must be an integer in [1,{MAX_SAMPLES}]")
    if type(hz) is not int or not 1 <= hz <= 10:
        raise ValueError("hz must be an integer in [1,10]")
    state = Path(state_dir)
    observations: list[dict] = []
    policies: list[PolicySample] = []
    prior_sim_time: float | None = None
    with ReadOnlyUnixRpc(state / "duck-a.sock", timeout_s=0.6) as stream:
        stream.request("robot.subscribe", hz=hz)
        for _ in range(samples):
            tick_started = time.monotonic()
            payload, observed_at = read_verified_body_state(state, rl_root, port=port)
            observation = parse_joint_observation(payload, observed_at)
            if (prior_sim_time is not None
                    and observation["sim_time_s"] <= prior_sim_time):
                raise GroundTruthError("simulator clock did not advance between joint samples")
            policy = parse_policy_sample(stream.next_notification())
            _join_policy(observation, policy)
            prior_sim_time = observation["sim_time_s"]
            observations.append(observation)
            policies.append(policy)
            remaining = 1.0 / hz - (time.monotonic() - tick_started)
            if remaining > 0 and len(observations) < samples:
                time.sleep(remaining)
    return {
        "schema_version": 1,
        "mode": "passive_read_only",
        "source": "pinned_official_mujoco_body_and_robotd",
        "rl_commit": RL_COMMIT,
        "flat_scene_git_blob": FLAT_SCENE_BLOB,
        "joint_names_wire_order": list(JOINT_NAMES),
        "mouth_index_unactuated": 9,
        "sampling_requested_hz": hz,
        "commands_sent": 0,
        "foot_contacts_available": False,
        "joint_targets_available": False,
        "missing_reason": "not_exposed_by_pinned_official_body_server_read_protocol",
        "currents_warning": "OEM simulation proxy: abs(actuator_force) * 100, not calibrated mA",
        "observations": observations,
        "summary": _summarize(observations, policies),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0a passive joint trace; MuJoCo only")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--rl-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=17801)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--hz", type=int, default=5)
    parser.add_argument("--output", type=Path,
                        help="optional JSON trace output, e.g. CI diagnostic artifact")
    args = parser.parse_args(argv)
    try:
        result = collect_joint_trace(
            args.state_dir, args.rl_root, port=args.port,
            samples=args.samples, hz=args.hz,
        )
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
        if args.output is not None:
            args.output.write_text(encoded + "\n", encoding="utf-8")
        print(encoded)
    except (GroundTruthError, TelemetryError, ValueError, OSError) as exc:
        print(f"P0a read-only trace unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
