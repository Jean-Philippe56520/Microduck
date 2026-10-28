"""Simulation-only evidence from the OFFICIAL pinned flat-floor MuJoCo world.

The ToF 8x8 cannot establish floor clearance. Here the *simulator's* own
ground truth is read through its local TCP body protocol after verifying:
  - the exact pinned RL revision and clean checkout,
  - the default scene.xml Git blob (a single infinite plane),
  - the identity and launch options of the running body_server process.
This is NOT a sensor suitable for a physical robot or an arbitrary scene.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import time

from .perception import PerceptionEvent, PerceptionSnapshot
from .sim_bridge import SimulatorTelemetry

RL_COMMIT = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
FLAT_SCENE_BLOB = "a3848be52113a50138d54921748733f09488d496"
SCENE_PATH = "src/mjlab_microduck/robot/microduck/scene.xml"
SIM_PROTOCOL = 1
JOINT_COUNT = 15
ZONE_RADIUS_M = 0.90
ROBOT_RADIUS_MARGIN_M = 0.16
MAX_GROUND_AGE_S = 0.35
MAX_TELEMETRY_AGE_S = 1.00


class GroundTruthError(RuntimeError):
    """Simulation provenance, process, scene or frame cannot be verified."""


@dataclass(frozen=True)
class FlatGroundTruth:
    observed_at: float
    sim_time_s: float
    x_m: float
    y_m: float
    z_m: float
    gravity_z: float
    boundary_clearance_m: float
    safe_area: bool
    floor_clear: bool
    # These fields can only describe a simulator scene, not real sensor proof.


def _number(value: object) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise GroundTruthError("invalid finite simulator number")
    return float(value)


def _git(rl_root: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ("git", "-C", str(rl_root), *args),
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise GroundTruthError("cannot verify pinned RL checkout") from exc


def verify_flat_scene(rl_root: Path) -> None:
    """Accept only the known default flat scene and an unmodified pinned tree."""
    if _git(rl_root, "rev-parse", "HEAD") != RL_COMMIT:
        raise GroundTruthError("simulator revision does not match the pinned version")
    if _git(rl_root, "status", "--porcelain", "--untracked-files=no"):
        raise GroundTruthError("official simulator tracked files were modified")
    try:
        data = (rl_root / SCENE_PATH).read_bytes()
    except OSError as exc:
        raise GroundTruthError("official default scene is missing") from exc
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if blob != FLAT_SCENE_BLOB:
        raise GroundTruthError("the default floor geometry is not the pinned scene")
    # Trust is based on the entire pinned, clean RL tree (which contains
    # the scene's included MJCF files), not on a free-form operator assertion.


def verify_body_process(state_dir: Path, rl_root: Path, port: int, *,
                        allow_viewer: bool = False) -> None:
    """Linux-only: check the actual body started by official duck-sim."""
    if os.name != "posix" or not Path("/proc/self/cmdline").exists():
        raise GroundTruthError("requires Linux procfs for simulator verification")
    try:
        pid = int((state_dir / "body.pid").read_text(encoding="ascii").strip())
        if pid <= 1:
            raise ValueError("invalid pid")
        proc = Path("/proc") / str(pid)
        argv = (proc / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
        expected = [
            b"-m", b"mjlab_microduck.sim.body_server",
            b"--port", str(port).encode(), b"--ducks", b"1",
            b"--keyframe", b"SIT", b"--headless",
        ]
        # Viewer mode is a separate opt-in for read-only manual traces.
        # Exactly one known launch form is accepted, never arbitrary argv.
        if type(allow_viewer) is not bool:
            raise GroundTruthError("viewer permission must be boolean")
        allowed = (expected, expected[:-1]) if allow_viewer else (expected,)
        if argv[1:] not in allowed:
            raise GroundTruthError("simulator process is not the pinned headless/viewer scene")
        python = Path(os.fsdecode(argv[0])).resolve()
        if python != (rl_root / ".venv/bin/python").resolve():
            raise GroundTruthError("simulator Python executable mismatch")
        uids = next(
            line.split()[1:] for line in (proc / "status").read_text().splitlines()
            if line.startswith("Uid:")
        )
        if not uids or int(uids[0]) != os.geteuid():
            raise GroundTruthError("simulator process owned by another user")
    except (OSError, ValueError, IndexError, StopIteration) as exc:
        raise GroundTruthError("simulator process identity cannot be verified") from exc


def _reply(reader: object) -> dict:
    line = reader.readline(16_385)
    if not line or len(line) > 16_384 or not line.endswith(b"\n"):
        raise GroundTruthError("invalid or oversized body protocol reply")
    try:
        frame = json.loads(
            line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError())
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise GroundTruthError("body protocol returned invalid JSON") from exc
    if not isinstance(frame, dict) or "error" in frame:
        raise GroundTruthError("body protocol returned an error")
    return frame


def _read_body(port: int, timeout_s: float) -> dict:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout_s) as sock:
            sock.settimeout(timeout_s)
            with sock.makefile("rwb", buffering=0) as stream:
                stream.write(b'{"op":"hello","protocol":1,"joints":15}\n')
                hello = _reply(stream)
                if hello.get("protocol") != SIM_PROTOCOL:
                    raise GroundTruthError("unknown simulator body protocol")
                stream.write(b'{"op":"read"}\n')
                return _reply(stream)
    except (OSError, TimeoutError) as exc:
        raise GroundTruthError("simulator TCP body read failed") from exc


def parse_flat_frame(payload: dict, observed_at: float) -> FlatGroundTruth:
    """Validate simulator pose and classify a conservative radial test zone.

    The pinned scene has a single horizontal plane and one robot; therefore
    the distance to the *artificial zone boundary* is the relevant static
    clearance. It is NOT a ToF obstacle measurement.
    """
    if not isinstance(payload, dict):
        raise GroundTruthError("missing simulator state")
    sim_time = _number(payload.get("sim_time"))
    trunk = payload.get("trunk")
    imu = payload.get("imu")
    if not isinstance(trunk, list) or len(trunk) != 3 or not isinstance(imu, dict):
        raise GroundTruthError("missing body pose")
    gravity = imu.get("gravity")
    if not isinstance(gravity, list) or len(gravity) != 3:
        raise GroundTruthError("missing projected gravity")
    x, y, z = (_number(v) for v in trunk)
    gx, gy, gz = (_number(v) for v in gravity)
    _number(observed_at)
    if observed_at < 0 or sim_time < 0:
        raise GroundTruthError("invalid timestamp")
    upright = -1.10 <= gz <= -0.92 and math.hypot(gx, gy) < 0.35
    standing = 0.095 <= z <= 0.18
    boundary = ZONE_RADIUS_M - math.hypot(x, y) - ROBOT_RADIUS_MARGIN_M
    inside = boundary >= 0.35
    return FlatGroundTruth(
        observed_at=observed_at, sim_time_s=sim_time, x_m=x, y_m=y,
        z_m=z, gravity_z=gz,
        boundary_clearance_m=max(0.0, boundary),
        safe_area=inside and upright and standing,
        floor_clear=upright and standing and boundary > 0,
    )


def read_verified_body_state(
    state_dir: str | Path, rl_root: str | Path, *,
    port: int = 17801, timeout_s: float = 0.5,
    allow_viewer: bool = False,
) -> tuple[dict, float]:
    """Read the raw pinned simulator body frame WITHOUT any write operation.

    This diagnostic-only API returns more data than FlatGroundTruth, including
    joint states. It has the same scene/process checks as the safety probe.
    Callers must separately validate each raw field before interpreting it.
    """
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("invalid simulator TCP port")
    if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= 3:
        raise ValueError("invalid simulator timeout")
    root, state = Path(rl_root).resolve(), Path(state_dir).resolve()
    verify_flat_scene(root)
    if allow_viewer:
        verify_body_process(state, root, port, allow_viewer=True)
    else:
        verify_body_process(state, root, port)
    payload = _read_body(port, float(timeout_s))
    if allow_viewer:
        verify_body_process(state, root, port, allow_viewer=True)
    else:
        verify_body_process(state, root, port)
    return payload, time.monotonic()


def read_verified_flat_ground(
    state_dir: str | Path, rl_root: str | Path, *,
    port: int = 17801, timeout_s: float = 0.5,
) -> FlatGroundTruth:
    """Read-only simulator truth; never use with any physical robot."""
    payload, at = read_verified_body_state(
        state_dir, rl_root, port=port, timeout_s=timeout_s,
    )
    return parse_flat_frame(payload, at)


def flat_zone_snapshot(
    telemetry: SimulatorTelemetry, ground: FlatGroundTruth | None,
    *, now: float | None = None,
) -> PerceptionSnapshot:
    """Combine the verified truth with fresh robotd+tofd telemetry.

    Without BOTH streams and a fresh verified ground frame, this falls back
    to the existing conservative battery-only snapshot. Physical robot data
    cannot enter this simulator-only path.
    """
    timestamp = time.monotonic() if now is None else now
    base = telemetry.to_snapshot(now=timestamp, max_age_s=MAX_TELEMETRY_AGE_S)
    if ground is None or not base.events:
        return base
    age = timestamp - ground.observed_at
    if not 0 <= age <= MAX_GROUND_AGE_S:
        return base
    def event(kind: str, value: bool | float) -> PerceptionEvent:
        return PerceptionEvent(
            kind=kind, value=value, source="simulator",
            observed_at=ground.observed_at,
            ttl_s=MAX_GROUND_AGE_S, confidence=1.0,
        )
    return PerceptionSnapshot(
        "simulator", base.events + (
            event("safe_area", ground.safe_area),
            event("floor_clear", ground.floor_clear),
            event("obstacle_m", ground.boundary_clearance_m),
        ), timestamp,
    )
