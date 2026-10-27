"""Read-only JSON-RPC/NDJSON telemetry from the official Microduck daemons.

This *cannot* send movement or motor requests. Source roles are selected by the
local Unix socket the caller opens, not by strings supplied by an AI or peer.
No telemetry here certifies safe floor or authorizes motion.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import math
import os
import socket
import time
from typing import Any

MAX_LINE_BYTES = 65_536
_MAX_QUEUED_NOTIFICATIONS = 16
_ALLOWED_READS = frozenset({"robot.health", "robot.subscribe", "tof.stream"})
_ROLE_READS = {
    "robotd": frozenset({"robot.health", "robot.subscribe"}),
    "tofd": frozenset({"tof.stream"}),
}
_SUBSCRIPTIONS = {"robot.subscribe": "robot.state", "tof.stream": "tof.frame"}


class TelemetryError(RuntimeError):
    """Invalid, missing or contradictory data from a telemetry socket."""


class TelemetryTimeout(TelemetryError):
    """A daemon did not respond within the permitted deadline."""


@dataclass(frozen=True)
class Notification:
    method: str
    params: dict[str, Any]
    received_at: float  # local time.monotonic() when the frame arrived


@dataclass(frozen=True)
class HealthReading:
    healthy: bool
    battery_pct: float | None
    target_hz: float | None
    achieved_hz: float | None
    missed_ticks: int | None
    received_at: float


@dataclass(frozen=True)
class StateReading:
    fallen: bool
    limp: bool
    achieved_hz: float
    missed_ticks: int
    t_ns: int | None
    received_at: float


@dataclass(frozen=True)
class DepthReading:
    seq: int
    distance_mm: tuple[int, ...]
    status: tuple[int, ...]
    t_ns: int | None
    received_at: float


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _nonnegative_integer(value: object, key: str) -> int:
    if type(value) is not int or value < 0:
        raise TelemetryError(f"{key} must be a nonnegative integer")
    return value


def _optional_finite(value: object, key: str) -> float | None:
    if value is None:
        return None
    if not _finite(value):
        raise TelemetryError(f"{key} must be finite or absent")
    return float(value)


def _object(value: object, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TelemetryError(f"{key} must be an object")
    return value


def parse_health(payload: dict[str, Any], received_at: float) -> HealthReading:
    """Parse robot.health, preserving unknown readings as None (never zero)."""
    health = _object(payload, "health")
    if type(health.get("healthy")) is not bool:
        raise TelemetryError("health.healthy must be a boolean")
    battery = health.get("battery")
    battery_pct = None
    if battery is not None:
        battery_pct = _optional_finite(_object(battery, "battery").get("percent"),
                                       "battery.percent")
        if battery_pct is not None and not 0 <= battery_pct <= 100:
            raise TelemetryError("battery percentage outside [0,100]")
    loop = health.get("control_loop")
    target = achieved = None
    missed = None
    if loop is not None:
        loop = _object(loop, "control_loop")
        target = _optional_finite(loop.get("target_hz"), "target_hz")
        achieved = _optional_finite(loop.get("achieved_hz"), "achieved_hz")
        if target is not None and target <= 0:
            raise TelemetryError("target_hz must be positive")
        if achieved is not None and achieved < 0:
            raise TelemetryError("achieved_hz cannot be negative")
        if "missed" in loop:
            missed = _nonnegative_integer(loop["missed"], "control_loop.missed")
    return HealthReading(health["healthy"], battery_pct, target, achieved,
                         missed, received_at)


def parse_state(notification: Notification) -> StateReading:
    if notification.method != "robot.state":
        raise TelemetryError("expected robot.state")
    state = _object(notification.params, "robot.state")
    safety = _object(state.get("safety"), "robot.state.safety")
    loop = _object(state.get("loop"), "robot.state.loop")
    if type(safety.get("fallen")) is not bool or type(safety.get("limp")) is not bool:
        raise TelemetryError("missing boolean safety state")
    hz = _optional_finite(loop.get("hz"), "loop.hz")
    if hz is None or hz < 0:
        raise TelemetryError("invalid loop.hz")
    missed = _nonnegative_integer(loop.get("missed"), "loop.missed")
    t_ns = state.get("t_ns")
    if t_ns is not None:
        t_ns = _nonnegative_integer(t_ns, "state.t_ns")
        if t_ns == 0:
            t_ns = None  # older daemon: clock not provided
    return StateReading(safety["fallen"], safety["limp"], hz, missed,
                        t_ns, notification.received_at)


def parse_depth(notification: Notification) -> DepthReading:
    """Retain raw ToF distances and statuses; no 'floor_clear' inference."""
    if notification.method != "tof.frame":
        raise TelemetryError("expected tof.frame")
    frame = _object(notification.params, "tof.frame")
    if type(frame.get("rows")) is not int or type(frame.get("cols")) is not int:
        raise TelemetryError("missing ToF dimensions")
    if (frame["rows"], frame["cols"]) != (8, 8):
        raise TelemetryError("unexpected ToF dimensions")
    distances, status = frame.get("distance_mm"), frame.get("status")
    if not isinstance(distances, list) or not isinstance(status, list):
        raise TelemetryError("missing ToF ranges or zone statuses")
    if len(distances) != 64 or len(status) != 64:
        raise TelemetryError("expected 64 distances and 64 zone statuses")
    if any(type(x) is not int or not -32768 <= x <= 32767 for x in distances):
        raise TelemetryError("ToF distances must be signed 16-bit millimetres")
    if any(type(x) is not int or not 0 <= x <= 255 for x in status):
        raise TelemetryError("ToF zone statuses must be bytes")
    seq = _nonnegative_integer(frame.get("seq"), "tof.seq")
    t_ns = frame.get("t_ns")
    if t_ns is not None:
        t_ns = _nonnegative_integer(t_ns, "tof.t_ns")
        if t_ns == 0:
            t_ns = None
    return DepthReading(seq, tuple(distances), tuple(status),
                        t_ns, notification.received_at)


class ReadOnlyUnixRpc:
    """One Unix-socket telemetry session, never a motor/command transport.

    The caller must open the appropriate official daemon socket. A fabricated
    socket can fabricate its data; this transport does not authenticate hardware.
    """

    def __init__(self, path: str | os.PathLike[str], *, timeout_s: float = 1.0,
                 role: str | None = None):
        if not _finite(timeout_s) or not 0 < timeout_s <= 30:
            raise ValueError("timeout_s must be finite in (0, 30]")
        if role is not None and (type(role) is not str or role not in _ROLE_READS):
            raise ValueError("unsupported simulator daemon role")
        self.path = os.fspath(path)
        # A role is a *local expected endpoint*, not peer authentication.
        # The independent parsers still validate every received frame.
        self.role = role
        self.timeout_s = float(timeout_s)
        self._socket: socket.socket | None = None
        self._buffer = b""
        self._buffer_received_at: float | None = None
        self._pending: deque[Notification] = deque()
        self._request_id = 0
        self._subscription: str | None = None

    def __enter__(self) -> ReadOnlyUnixRpc:
        if self._socket is not None:
            raise TelemetryError("already connected")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout_s)
        try:
            sock.connect(self.path)
        except (OSError, TimeoutError) as exc:
            sock.close()
            raise TelemetryError(f"cannot connect to telemetry socket: {exc}") from exc
        self._socket = sock
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
        self._socket = None
        self._buffer = b""
        self._buffer_received_at = None
        self._pending.clear()
        self._subscription = None

    def _recv(self, deadline: float) -> tuple[dict[str, Any], float]:
        sock = self._socket
        if sock is None:
            raise TelemetryError("not connected")
        while True:
            separator = self._buffer.find(b"\n")
            if separator >= 0:
                if separator > MAX_LINE_BYTES:
                    raise TelemetryError("oversized telemetry frame")
                line, self._buffer = self._buffer[:separator], self._buffer[separator + 1:]
                received_at = self._buffer_received_at or time.monotonic()
                if not self._buffer:
                    self._buffer_received_at = None
                try:
                    frame = json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(
                        ValueError("non-finite JSON value")))
                except (UnicodeDecodeError, ValueError) as exc:
                    raise TelemetryError("invalid JSON telemetry frame") from exc
                if not isinstance(frame, dict) or frame.get("jsonrpc") != "2.0":
                    raise TelemetryError("invalid JSON-RPC envelope")
                return frame, received_at
            if len(self._buffer) > MAX_LINE_BYTES:
                raise TelemetryError("oversized telemetry frame")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TelemetryTimeout("telemetry read timed out")
            sock.settimeout(remaining)
            try:
                chunk = sock.recv(4096)
            except socket.timeout as exc:
                raise TelemetryTimeout("telemetry read timed out") from exc
            except OSError as exc:
                raise TelemetryError("telemetry socket read failed") from exc
            if not chunk:
                raise TelemetryError("telemetry socket closed")
            if not self._buffer:
                self._buffer_received_at = time.monotonic()
            self._buffer += chunk

    def request(self, method: str, *, hz: int | None = None) -> dict[str, Any]:
        """Send only an explicitly permitted read/subscription method."""
        if method not in _ALLOWED_READS:
            raise ValueError(f"method not permitted by read-only client: {method}")
        if self.role is not None and method not in _ROLE_READS[self.role]:
            raise ValueError("read method does not belong to expected daemon role")
        if hz is not None and method != "robot.subscribe":
            raise ValueError("hz only supported for robot.subscribe")
        if method == "robot.subscribe" and (type(hz) is not int or not 1 <= hz <= 10):
            raise ValueError("robot.subscribe requires hz in [1,10]")
        if self._subscription is not None:
            raise TelemetryError("session already subscribed")
        sock = self._socket
        if sock is None:
            raise TelemetryError("not connected")
        self._request_id += 1
        request: dict[str, Any] = {"jsonrpc": "2.0", "id": self._request_id,
                                   "method": method}
        if hz is not None:
            request["params"] = {"hz": hz}
        encoded = (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
        deadline = time.monotonic() + self.timeout_s
        sock.settimeout(self.timeout_s)
        try:
            sock.sendall(encoded)
        except (OSError, socket.timeout) as exc:
            raise TelemetryError("telemetry request could not be sent") from exc
        while True:
            frame, received_at = self._recv(deadline)
            if "id" not in frame:
                self._queue_notification(frame, received_at)
                continue
            if frame["id"] != self._request_id:
                raise TelemetryError("mismatched JSON-RPC response id")
            if "error" in frame:
                raise TelemetryError("daemon rejected telemetry request")
            if "result" not in frame:
                raise TelemetryError("missing JSON-RPC result")
            result = _object(frame["result"], "JSON-RPC result")
            if method in _SUBSCRIPTIONS:
                if result.get("accepted") is not True:
                    raise TelemetryError("telemetry subscription rejected")
                self._subscription = _SUBSCRIPTIONS[method]
            return result

    def _queue_notification(self, frame: dict[str, Any], at: float) -> None:
        method = frame.get("method")
        params = frame.get("params")
        if method not in _SUBSCRIPTIONS.values() or not isinstance(params, dict):
            raise TelemetryError("unexpected telemetry notification")
        if len(self._pending) >= _MAX_QUEUED_NOTIFICATIONS:
            raise TelemetryError("telemetry notification queue full")
        self._pending.append(Notification(method, params, at))

    def next_notification(self) -> Notification:
        """Return the next subscribed notification, with a read deadline."""
        if self._subscription is None:
            raise TelemetryError("no active telemetry subscription")
        deadline = time.monotonic() + self.timeout_s
        if self._pending:
            event = self._pending.popleft()
        else:
            frame, at = self._recv(deadline)
            if "id" in frame:
                raise TelemetryError("unexpected JSON-RPC response in stream")
            self._queue_notification(frame, at)
            event = self._pending.popleft()
        if event.method != self._subscription:
            raise TelemetryError("notification from wrong telemetry stream")
        return event


def read_health(path: str | os.PathLike[str], *, timeout_s: float = 1.) -> HealthReading:
    """Single read-only robot.health call against the robotd Unix socket."""
    with ReadOnlyUnixRpc(path, timeout_s=timeout_s, role="robotd") as reader:
        result = reader.request("robot.health")
        return parse_health(result, time.monotonic())
