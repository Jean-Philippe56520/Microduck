"""Single bounded *simulator-only* movement via the official robotd JSON-RPC.

This demonstration deliberately cannot run on a physical Microduck:
- fixed pinned MuJoCo revision, clean flat scene and Linux body PID;
- live robot pose and robotd health rechecked before every notification;
- 0.05 m/s forward for at most 0.4 s, no steering/rotation;
- robot.stop requested and checked in all post-send paths;
- robotd's own continuous-intent deadman remains authoritative.
This is an experiment, NOT a general motor adapter or obstacle avoidance.
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
    FlatGroundTruth, GroundTruthError, flat_zone_snapshot,
    read_verified_flat_ground,
)
from .sim_ipc import HealthReading, TelemetryError, read_health

SPEED_MPS = 0.05
TICK_S = 0.10
TICKS = 4
MIN_CLEARANCE_M = 0.50
MIN_BATTERY_PCT = 25.0
MIN_HEALTH_HZ = 45.0


class SimMotionError(RuntimeError):
    """An attempted simulation impulse was refused or not fully verified."""


@dataclass(frozen=True)
class SimMotionResult:
    commands_sent: int
    stop_confirmed: bool
    measured_displacement_m: float
    before_xyz_m: tuple[float, float, float]
    after_xyz_m: tuple[float, float, float]
    sim_time_before_s: float
    sim_time_after_s: float


def _healthy(reading: HealthReading) -> bool:
    return (
        reading.healthy
        and reading.battery_pct is not None
        and reading.battery_pct > MIN_BATTERY_PCT
        and reading.target_hz is not None
        and reading.target_hz >= MIN_HEALTH_HZ
        and reading.achieved_hz is not None
        and reading.achieved_hz >= MIN_HEALTH_HZ
    )


def _safe_ground(reading: FlatGroundTruth) -> bool:
    return (
        reading.safe_area and reading.floor_clear
        and reading.boundary_clearance_m >= MIN_CLEARANCE_M
    )


def _send_move(sock: socket.socket) -> None:
    """Only the official continuous robot.move notification, fixed speed."""
    frame = {
        "jsonrpc": "2.0", "method": "robot.move",
        "params": {"vx": SPEED_MPS, "vy": 0.0, "vyaw": 0.0},
    }
    sock.sendall((json.dumps(frame, separators=(",", ":")) + "\n").encode())


def _send_stop(sock: socket.socket) -> None:
    """Discrete robot.stop request; require matching response without an error."""
    sock.sendall(b'{"jsonrpc":"2.0","id":1,"method":"robot.stop"}\n')
    chunks = bytearray()
    while b"\n" not in chunks:
        block = sock.recv(4096)
        if not block or len(chunks) + len(block) > 8192:
            raise SimMotionError("robot.stop response missing or oversized")
        chunks.extend(block)
    try:
        response = json.loads(
            bytes(chunks).split(b"\n", 1)[0],
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise SimMotionError("robot.stop returned invalid JSON") from exc
    if (not isinstance(response, dict) or response.get("jsonrpc") != "2.0"
            or type(response.get("id")) is not int or response["id"] != 1
            or "error" in response or "result" not in response):
        raise SimMotionError("robot.stop was not acknowledged")


def move_once(
    state_dir: str | Path, rl_root: str | Path, *, port: int = 17801,
) -> SimMotionResult:
    """Only one fixed, short simulator-only forward impulse.

    No caller-specified velocities and no way to reuse this for a real robot.
    If any safety verification fails, no new movement is sent; robotd still
    expires continuous intents after 500 ms if the client disconnects.
    """
    state, rl = Path(state_dir), Path(rl_root)
    telemetry = read_simulator_telemetry(state, timeout_s=3.0, hz=2)
    try:
        before = read_verified_flat_ground(state, rl, port=port)
    except (GroundTruthError, ValueError) as exc:
        raise SimMotionError("pinned simulator ground truth not available") from exc
    now = time.monotonic()
    snapshot = flat_zone_snapshot(telemetry, before, now=now)
    scene = snapshot.to_scene(now=now)
    if not (scene.safe_area and scene.floor_clear and scene.perception_valid
            and scene.battery_pct > MIN_BATTERY_PCT and _safe_ground(before)):
        raise SimMotionError("preflight safety verification refused movement")
    memory = ExperienceMemory()
    try:
        plan = AutonomyBrain(memory).choose_from_snapshot(snapshot, now=now)
    finally:
        memory.close()
    if plan.intention != "explore":
        raise SimMotionError("autonomy brain did not authorize exploration")

    socket_path = str(state / "duck-a.sock")
    count = 0
    stop_error: BaseException | None = None
    primary_error: BaseException | None = None
    previous_sim_time = before.sim_time_s
    started_at = time.monotonic()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.4)
            sock.connect(socket_path)
            try:
                for index in range(TICKS):
                    if time.monotonic() - started_at > 0.65:
                        raise SimMotionError("bounded movement deadline exceeded")
                    current = read_verified_flat_ground(state, rl, port=port)
                    if (current.sim_time_s <= previous_sim_time
                            or not _safe_ground(current)):
                        raise SimMotionError("ground truth changed or simulator stalled")
                    previous_sim_time = current.sim_time_s
                    latest = read_health(socket_path, timeout_s=0.35)
                    if not _healthy(latest):
                        raise SimMotionError("robotd health degraded during movement")
                    _send_move(sock)
                    count += 1
                    if index + 1 < TICKS:
                        time.sleep(TICK_S)
            except (OSError, GroundTruthError, TelemetryError, SimMotionError) as exc:
                primary_error = exc
            finally:
                if count:
                    try:
                        _send_stop(sock)
                    except (OSError, SimMotionError) as exc:
                        stop_error = exc
    except OSError as exc:
        raise SimMotionError("robotd movement socket unavailable") from exc
    if stop_error is not None:
        raise SimMotionError(
            "robot.stop could not be confirmed; official 500 ms deadman remains active"
        ) from stop_error
    if primary_error is not None:
        raise SimMotionError(
            f"movement aborted after {count} notification(s): {primary_error}"
        ) from primary_error
    if count != TICKS:
        raise SimMotionError("bounded movement did not complete")

    try:
        after = read_verified_flat_ground(state, rl, port=port)
    except GroundTruthError as exc:
        raise SimMotionError("robot.stop acknowledged but final pose unavailable") from exc
    if after.sim_time_s <= before.sim_time_s or not _safe_ground(after):
        raise SimMotionError("robot.stop acknowledged but final pose was unsafe")
    displacement = math.hypot(after.x_m - before.x_m, after.y_m - before.y_m)
    return SimMotionResult(
        count, True, displacement,
        (before.x_m, before.y_m, before.z_m),
        (after.x_m, after.y_m, after.z_m),
        before.sim_time_s, after.sim_time_s,
    )
