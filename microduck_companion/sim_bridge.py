"""Fail-closed bridge between official simulated telemetry and the local brain.

This module cannot command motors, cannot certify floor clearance and does not
interpret raw ToF zones as a traversable surface. Its only trusted provenance
is the explicit Unix-socket role used by the read-only acquisition functions.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time

from .perception import PerceptionEvent, PerceptionSnapshot
from .sim_ipc import (
    DepthReading, HealthReading, ReadOnlyUnixRpc, StateReading, TelemetryError,
    parse_depth, parse_health, parse_state,
)

MIN_CONTROL_HZ = 45.0
DEFAULT_MAX_AGE_S = 2.0
MAX_SENSOR_SKEW_NS = 1_000_000_000


@dataclass(frozen=True)
class SimulatorTelemetry:
    """Measurements read from a simulated daemon pair, never a safety grant."""

    health: HealthReading | None = None
    state: StateReading | None = None
    depth: DepthReading | None = None
    errors: tuple[str, ...] = ()

    def to_snapshot(self, now: float | None = None,
                    max_age_s: float = DEFAULT_MAX_AGE_S) -> PerceptionSnapshot:
        """Produce at most a confirmed battery observation, otherwise none.

        No safe_area, floor_clear, obstacle_m, object or social event is ever
        synthesized. Consequently the autonomous brain must halt by default.
        """
        if not isinstance(max_age_s, (int, float)) or isinstance(max_age_s, bool):
            raise ValueError("max_age_s must be finite and positive")
        if not math.isfinite(max_age_s) or not 0 < max_age_s <= 5:
            raise ValueError("max_age_s must be in (0, 5]")
        timestamp = time.monotonic() if now is None else now
        if (type(timestamp) not in (int, float) or not math.isfinite(timestamp)
                or timestamp < 0):
            raise ValueError("now must be a nonnegative finite monotonic time")
        events: tuple[PerceptionEvent, ...] = ()
        if self._coherent(timestamp, max_age_s):
            assert self.health is not None
            if self.health.battery_pct is not None:
                events = (PerceptionEvent(
                    kind="battery_pct", value=self.health.battery_pct,
                    source="robotd", observed_at=self.health.received_at,
                    ttl_s=float(max_age_s), confidence=1.0,
                ),)
        return PerceptionSnapshot(
            environment="simulator", events=events, observed_at=timestamp,
        )

    def _coherent(self, now: float, max_age_s: float) -> bool:
        health, state, depth = self.health, self.state, self.depth
        if self.errors or health is None or state is None or depth is None:
            return False
        if not health.healthy or state.fallen or state.limp:
            return False
        if (health.target_hz is None or health.achieved_hz is None
                or health.target_hz < MIN_CONTROL_HZ
                or health.achieved_hz < MIN_CONTROL_HZ
                or state.achieved_hz < MIN_CONTROL_HZ):
            return False
        for reading in (health, state, depth):
            age = now - reading.received_at
            if not 0 <= age <= max_age_s:
                return False
        if (state.t_ns is not None and depth.t_ns is not None
                and abs(state.t_ns - depth.t_ns) > MAX_SENSOR_SKEW_NS):
            return False
        return True


def read_simulator_telemetry(state_dir: str | Path, *, timeout_s: float = 3.0,
                             hz: int = 2) -> SimulatorTelemetry:
    """Read a single observation from the official duck-a simulator sockets.

    Failures become missing readings rather than reused cached values. The two
    streams are read independently; neither stream's data authenticates the
    other or proves any property of a real robot.
    """
    directory = Path(state_dir)
    health = state = depth = None
    errors: list[str] = []
    try:
        with ReadOnlyUnixRpc(directory / "duck-a.sock", timeout_s=timeout_s) as robot:
            health = parse_health(robot.request("robot.health"), time.monotonic())
            robot.request("robot.subscribe", hz=hz)
            state = parse_state(robot.next_notification())
    except (TelemetryError, OSError):
        errors.append("robotd telemetry unavailable")
    try:
        with ReadOnlyUnixRpc(directory / "duck-a-tof.sock", timeout_s=timeout_s) as tof:
            ack = tof.request("tof.stream")
            if not ack.get("sensor"):
                raise TelemetryError("ToF sensor unavailable")
            depth = parse_depth(tof.next_notification())
    except (TelemetryError, OSError):
        errors.append("tofd telemetry unavailable")
    return SimulatorTelemetry(health, state, depth, tuple(errors))
