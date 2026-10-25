"""Single measured walking-policy trial in a pinned, empty MuJoCo scene.

Never import/use this on an actual Microduck. This experiment runs solely
against duck-sim's authenticated headless body and the unchanged robotd IPC.
A velocity above the OEM 0.05 m/s standing-policy threshold is used, but
a change in trunk coordinates is NOT by itself proof of a walking gait.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import socket
import time

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .sim_bridge import read_simulator_telemetry
from .sim_flat_zone import (
    GroundTruthError, FlatGroundTruth, flat_zone_snapshot,
    read_verified_flat_ground,
)
from .sim_ipc import ReadOnlyUnixRpc, TelemetryError, read_health
from .sim_policy_trace import PolicySample, parse_policy_sample, summarize_policy_samples
from .sim_motion import _healthy, _safe_ground, _send_stop, SimMotionError

WALK_SPEED_MPS = 0.12  # Above OEM default standing threshold 0.05 m/s.
WALK_TICKS = 24
WALK_PERIOD_S = 0.10
MAX_COMMAND_WINDOW_S = 4.0
BASELINE_WAIT_S = 0.30
BASELINE_LIMIT_M = 0.005
MAX_DISPLACEMENT_M = 0.30


@dataclass(frozen=True)
class WalkTrialResult:
    commands_sent: int
    stop_confirmed: bool
    requested_speed_mps: float
    measured_displacement_m: float
    baseline_displacement_m: float
    simulated_duration_s: float
    measured_forward_x_m: float
    measured_lateral_y_m: float
    outcome: str
    reward: float | None
    preference_before: float
    preference_after: float
    next_intention: str
    trials_in_memory: int
    memory_source: str
    policy_diagnostics: dict


def _read_ground(state: Path, rl_root: Path, port: int) -> FlatGroundTruth:
    return read_verified_flat_ground(state, rl_root, port=port, timeout_s=.5)


def _send_forward(sock: socket.socket) -> None:
    # Fixed command; the caller cannot supply arbitrary velocity/axis values.
    cmd = {
        "jsonrpc": "2.0", "method": "robot.move",
        "params": {"vx": WALK_SPEED_MPS, "vy": 0.0, "vyaw": 0.0},
    }
    sock.sendall((json.dumps(cmd, separators=(",", ":")) + "\n").encode("ascii"))


def _distance(a: FlatGroundTruth, b: FlatGroundTruth) -> float:
    return math.hypot(b.x_m - a.x_m, b.y_m - a.y_m)


def run_walk_trial(
    state_dir: str | Path, rl_root: str | Path, memory_path: str | Path, *,
    port: int = 17801,
) -> WalkTrialResult:
    """One fixed-velocity trial; no repetition, alternate scenes or hardware.

    A stable no-command baseline is measured first. If the learned preference
    makes the brain choose to remain idle instead of explore, this function
    refuses to send anything, leaving that learned decision intact.
    """
    state, rl, memory_file = Path(state_dir), Path(rl_root), Path(memory_path)
    if str(memory_file) == ":memory:":
        raise ValueError("walk trials require a persistent SQLite file")
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    telemetry = read_simulator_telemetry(state, timeout_s=3., hz=2)
    try:
        first = _read_ground(state, rl, port)
        time.sleep(BASELINE_WAIT_S)
        stable = _read_ground(state, rl, port)
    except (GroundTruthError, OSError) as exc:
        raise SimMotionError("simulator baseline could not be verified") from exc

    if not _safe_ground(first) or not _safe_ground(stable):
        raise SimMotionError("flat-scene baseline is outside verified safe zone")
    if stable.sim_time_s <= first.sim_time_s:
        raise SimMotionError("MuJoCo clock did not advance during baseline")
    drift = _distance(first, stable)
    if drift > BASELINE_LIMIT_M:
        raise SimMotionError("robot unstable without movement: trial refused")
    now = time.monotonic()
    snapshot = flat_zone_snapshot(telemetry, stable, now=now)
    scene = snapshot.to_scene(now=now)
    if (not scene.safe_area or not scene.floor_clear or not scene.perception_valid
            or scene.battery_pct <= 25 or not _safe_ground(stable)):
        raise SimMotionError("simulated safety preflight denied walking trial")

    memory = ExperienceMemory(memory_file)
    try:
        prior = memory.intent_preference("simulator", "explore")
        brain = AutonomyBrain(memory)
        plan = brain.choose_from_snapshot(snapshot, now=now)
        if plan.intention != "explore":
            raise SimMotionError(
                f"brain chose {plan.intention}, not explore; no trial attempted"
            )

        sock_path = str(state / "duck-a.sock")
        count = 0
        policy_samples: list[PolicySample] = []
        attempted = False
        stopped = False
        primary: BaseException | None = None
        stop_failure: BaseException | None = None
        last_sim_time = stable.sim_time_s
        started = time.monotonic()

        try:
            # Subscribe separately to the official stream that tells us
            # which policy ran and which velocity robotd actually applied.
            # Missing/invalid feedback stops the experiment; it never
            # grants permission independently of ground truth.
            with ReadOnlyUnixRpc(sock_path, timeout_s=.45) as stream:
                stream.request("robot.subscribe", hz=10)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(.45)
                    sock.connect(sock_path)
                    try:
                        for i in range(WALK_TICKS):
                            tick_started = time.monotonic()
                            if tick_started - started > MAX_COMMAND_WINDOW_S:
                                raise SimMotionError("walk trial time budget exceeded")
                            pose = _read_ground(state, rl, port)
                            if (not _safe_ground(pose)
                                    or (i > 0 and pose.sim_time_s <= last_sim_time)):
                                raise SimMotionError(
                                    "MuJoCo pose unsafe or simulation clock stalled"
                                )
                            last_sim_time = pose.sim_time_s
                            fresh_health = read_health(sock_path, timeout_s=.35)
                            if not _healthy(fresh_health):
                                raise SimMotionError("robotd health degraded")
                            attempted = True
                            _send_forward(sock)
                            count += 1
                            # robot.state is a read-only notification; the
                            # sampled policy can be "stand", "walk" or "held".
                            policy_samples.append(parse_policy_sample(
                                stream.next_notification()
                            ))
                            remaining = WALK_PERIOD_S - (time.monotonic() - tick_started)
                            if remaining > 0:
                                time.sleep(remaining)
                    except (OSError, GroundTruthError, TelemetryError, SimMotionError) as exc:
                        primary = exc
                    finally:
                        if attempted:
                            try:
                                _send_stop(sock)
                                stopped = True
                            except (OSError, SimMotionError) as exc:
                                stop_failure = exc
        except (OSError, TelemetryError) as exc:
            raise SimMotionError("simulated robotd state stream unavailable") from exc

        if stop_failure is not None:
            raise SimMotionError(
                "stop unconfirmed; robotd continuous-command deadman still applies"
            ) from stop_failure
        if primary is not None:
            raise SimMotionError(f"walking trial aborted after {count} command(s)") from primary
        if count != WALK_TICKS or not stopped:
            raise SimMotionError("walking trial did not finish with confirmed stop")

        # Wait for the official controller's post-command state; do not
        # declare success from an unconfirmed command or stale pose.
        time.sleep(.18)
        try:
            after = _read_ground(state, rl, port)
            final_health = read_health(sock_path, timeout_s=.5)
        except (GroundTruthError, TelemetryError, OSError) as exc:
            raise SimMotionError("final simulator observation is unavailable") from exc
        duration = after.sim_time_s - stable.sim_time_s
        if duration <= 0 or duration > 10:
            raise SimMotionError("final simulator clock inconsistent")
        measured = _distance(stable, after)
        if measured > MAX_DISPLACEMENT_M:
            raise SimMotionError("implausible simulator displacement: measurement rejected")
        healthy_after = _healthy(final_health)
        safe_after = _safe_ground(after)

        outcome = memory.record_simulated_motion(
            measured_m=measured, baseline_m=drift,
            simulated_duration_s=duration, stop_confirmed=stopped,
            healthy_after=healthy_after, safe_after=safe_after,
        )
        # Only the next independently verified snapshot may authorize another
        # movement, and this trial has NO loop or automatic second attempt.
        # A current snapshot is used here solely to demonstrate a later choice.
        later_telemetry = read_simulator_telemetry(state, timeout_s=3., hz=2)
        later_ground = _read_ground(state, rl, port)
        later_now = time.monotonic()
        next_snapshot = flat_zone_snapshot(later_telemetry, later_ground, now=later_now)
        next_plan = AutonomyBrain(memory).choose_from_snapshot(
            next_snapshot, now=later_now,
        )
        return WalkTrialResult(
            commands_sent=count, stop_confirmed=stopped,
            requested_speed_mps=WALK_SPEED_MPS,
            measured_displacement_m=measured,
            baseline_displacement_m=drift,
            simulated_duration_s=duration,
            measured_forward_x_m=after.x_m - stable.x_m,
            measured_lateral_y_m=after.y_m - stable.y_m,
            outcome=outcome.outcome, reward=outcome.reward,
            preference_before=prior, preference_after=outcome.updated_preference,
            next_intention=next_plan.intention,
            trials_in_memory=outcome.observed_trials,
            memory_source=outcome.source,
            policy_diagnostics=summarize_policy_samples(policy_samples),
        )
    finally:
        memory.close()
