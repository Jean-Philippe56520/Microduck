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
_ASSESSMENT_STATES = frozenset({
    "coherent", "source_error", "missing_stream", "invalid_payload",
    "unsafe_state", "slow_control", "future_sample", "stale_sample",
    "timestamp_skew",
})
_SIMULATOR_CLAIM = "simulator_ipc_unverified"


@dataclass(frozen=True, slots=True)
class SimulatorTelemetryAssessment:
    """Quality of *claimed* simulator telemetry, never source authentication.

    Only the OEM daemon's own response/notification formats have been parsed.
    Unix socket names and well-formed JSON do not authenticate a physical
    robot, establish safe floor, classify objects, or grant motor authority.
    """

    status: str
    source: str = _SIMULATOR_CLAIM
    physical_robot_verified: bool = False
    floor_certified: bool = False
    motor_authorized: bool = False
    semantic_category_verified: bool = False

    def __post_init__(self) -> None:
        if (type(self.status) is not str
                or self.status not in _ASSESSMENT_STATES
                or self.source != _SIMULATOR_CLAIM
                or any(getattr(self, flag) is not False for flag in (
                    "physical_robot_verified", "floor_certified",
                    "motor_authorized", "semantic_category_verified"))):
            raise ValueError("simulation assessment cannot grant real authority")


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class SimulatorTelemetry:
    """Measurements read from a simulated daemon pair, never a safety grant."""

    health: HealthReading | None = None
    state: StateReading | None = None
    depth: DepthReading | None = None
    errors: tuple[str, ...] = ()

    def assess(self, *, now: float | None = None,
               max_age_s: float = DEFAULT_MAX_AGE_S) -> SimulatorTelemetryAssessment:
        """Classify freshness and consistency without promoting any sensor.

        Directly constructed dataclasses are allowed in host fixtures; their
        status is *never* proof of OEM process identity, hardware or robotd
        execution. A malformed field fails closed instead of raising TypeError.
        """
        if not _finite(max_age_s) or not 0 < max_age_s <= 5:
            raise ValueError("max_age_s must be finite in (0, 5]")
        at = time.monotonic() if now is None else now
        if not _finite(at) or at < 0:
            raise ValueError("now must be a nonnegative finite monotonic time")

        def result(status: str) -> SimulatorTelemetryAssessment:
            return SimulatorTelemetryAssessment(status)

        if self.errors:
            return result("source_error")
        health, state, depth = self.health, self.state, self.depth
        if health is None or state is None or depth is None:
            return result("missing_stream")
        if (not isinstance(health, HealthReading)
                or not isinstance(state, StateReading)
                or not isinstance(depth, DepthReading)):
            return result("invalid_payload")
        if (type(health.healthy) is not bool
                or type(state.fallen) is not bool
                or type(state.limp) is not bool):
            return result("invalid_payload")
        if not health.healthy or state.fallen or state.limp:
            return result("unsafe_state")
        if (type(depth.seq) is not int or depth.seq < 0
                or type(depth.distance_mm) is not tuple
                or type(depth.status) is not tuple
                or len(depth.distance_mm) != 64
                or len(depth.status) != 64
                or any(type(x) is not int or not -32768 <= x <= 32767
                       for x in depth.distance_mm)
                or any(type(x) is not int or not 0 <= x <= 255
                       for x in depth.status)):
            return result("invalid_payload")
        if (type(state.missed_ticks) is not int or state.missed_ticks < 0
                or (health.missed_ticks is not None and
                    (type(health.missed_ticks) is not int
                     or health.missed_ticks < 0))
                or (health.battery_pct is not None and
                    (not _finite(health.battery_pct)
                     or not 0 <= health.battery_pct <= 100))
                or any(v is not None and
                       (type(v) is not int or v < 0)
                       for v in (state.t_ns, depth.t_ns))):
            return result("invalid_payload")
        rates = (health.target_hz, health.achieved_hz, state.achieved_hz)
        if any(v is not None and not _finite(v) for v in rates):
            return result("invalid_payload")
        if any(v is None or v < MIN_CONTROL_HZ for v in rates):
            return result("slow_control")
        timestamps = (health.received_at, state.received_at, depth.received_at)
        if any(not _finite(v) or v < 0 for v in timestamps):
            return result("invalid_payload")
        ages = tuple(at - v for v in timestamps)
        if any(age < 0 for age in ages):
            return result("future_sample")
        if any(age > max_age_s for age in ages):
            return result("stale_sample")
        if (state.t_ns is not None and depth.t_ns is not None
                and abs(state.t_ns - depth.t_ns) > MAX_SENSOR_SKEW_NS):
            return result("timestamp_skew")
        return result("coherent")

    def to_snapshot(self, now: float | None = None,
                    max_age_s: float = DEFAULT_MAX_AGE_S) -> PerceptionSnapshot:
        """Expose at most the reported battery, never a safe floor or label."""
        timestamp = time.monotonic() if now is None else now
        assessment = self.assess(now=timestamp, max_age_s=max_age_s)
        events: tuple[PerceptionEvent, ...] = ()
        if assessment.status == "coherent":
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
        """Compatibility adapter for P2b; share the single assessment logic."""
        return self.assess(now=now, max_age_s=max_age_s).status == "coherent"


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
        with ReadOnlyUnixRpc(directory / "duck-a.sock", timeout_s=timeout_s,
                             role="robotd") as robot:
            health = parse_health(robot.request("robot.health"), time.monotonic())
            robot.request("robot.subscribe", hz=hz)
            state = parse_state(robot.next_notification())
    except (TelemetryError, OSError):
        errors.append("robotd telemetry unavailable")
    try:
        with ReadOnlyUnixRpc(directory / "duck-a-tof.sock", timeout_s=timeout_s,
                             role="tofd") as tof:
            ack = tof.request("tof.stream")
            if not ack.get("sensor"):
                raise TelemetryError("ToF sensor unavailable")
            depth = parse_depth(tof.next_notification())
    except (TelemetryError, OSError):
        errors.append("tofd telemetry unavailable")
    return SimulatorTelemetry(health, state, depth, tuple(errors))
