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

    def peer_credentials(self) -> tuple[int, int, int]:
        """Return Linux SO_PEERCRED (pid, uid, gid), never a remote identity.

        Refuse an unavailable kernel peer credential; a claimed JSON revision
        by itself must never authenticate an observation source.
        """
        import struct
        conn = self._socket
        if conn is None or not hasattr(socket, "SO_PEERCRED"):
            raise TelemetryError("local Unix peer credentials unavailable")
        try:
            data = conn.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            pid, uid, gid = struct.unpack("3i", data)
        except (OSError, struct.error) as exc:
            raise TelemetryError("local Unix peer credentials invalid") from exc
        if pid <= 0 or uid < 0 or gid < 0:
            raise TelemetryError("local Unix peer credentials invalid")
        return pid, uid, gid

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


# P15-B2: a single OEM ToF *read*, not a new daemon or perception classifier.
# These identities are for the pinned OEM source; patched/updated binaries with
# a different DUCK_REVISION must be explicitly audited before enabling this gate.
_OEM_TOF_SOCKET = "/run/tofd/tof.sock"
_OEM_TOF_IDENTITY = "/run/tofd/identity.json"
_PINNED_OEM_TOF_REVISION = "942e58e3aa6dbb28e7037203fff11866122c7567"
_MAX_IDENTITY_BYTES = 2048
_MAX_TOF_SAMPLE_AGE_NS = 1_000_000_000


@dataclass(frozen=True)
class OemTofSample:
    """One raw depth reading with LOCAL-OS provenance, not hardware proof.

    A non-None reading is not a detected object, safe floor, safe motion,
    physical sensor attestation, camera image or learned experience. The
    companion must not promote it to the F1 'sensor' trust lane on its own.
    """
    status: str
    provenance: str
    reading: DepthReading | None = None
    age_ms: float | None = None
    local_peer_checked: bool = False
    physical_sensor_validated: bool = False
    robot_validated: bool = False
    motor_commands_issued: int = 0
    camera_frames_requested: int = 0
    sqlite_writes: int = 0


def _strict_identity_json(data: bytes) -> dict[str, Any]:
    """Strict small OEM process identity with no duplicate/NaN fields."""
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict:
        obj: dict[str, object] = {}
        for key, value in pairs:
            if key in obj:
                raise TelemetryError("duplicate identity field")
            obj[key] = value
        return obj

    try:
        value = json.loads(
            data, object_pairs_hook=no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(
                TelemetryError("invalid identity numeric literal")),
        )
    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
        raise TelemetryError("invalid OEM identity JSON") from exc
    if type(value) is not dict:
        raise TelemetryError("OEM identity must be an object")
    return value


def _check_tof_paths(
    sock_path: "Path", identity_path: "Path", uid: int, gid: int,
) -> tuple[int, int]:
    """Verify the existing owner-controlled OEM directory and socket inode.

    Checks are made before connect and again after connect. The peer's real
    kernel credentials are checked separately. These are OS-local gates and
    do not form cryptographic authentication or a read-only Unix ACL.
    """
    import stat
    parent = sock_path.parent
    if identity_path.parent != parent or parent.is_symlink():
        raise TelemetryError("ToF paths must have the same real directory")
    parent_stat = parent.lstat()
    sock_stat = sock_path.lstat()
    if (not stat.S_ISDIR(parent_stat.st_mode)
            or parent_stat.st_uid != uid
            or parent_stat.st_mode & 0o022):
        raise TelemetryError("unsafe ToF runtime directory")
    if (not stat.S_ISSOCK(sock_stat.st_mode)
            or sock_stat.st_uid != uid or sock_stat.st_gid != gid
            or stat.S_IMODE(sock_stat.st_mode) != 0o660):
        raise TelemetryError("unexpected ToF socket owner or mode")
    return sock_stat.st_dev, sock_stat.st_ino


def _load_tof_identity(
    identity_path: "Path", uid: int, expected_revision: str,
    peer_pid: int,
) -> None:
    """Check an owned, non-symlink local identity file against peer PID."""
    import stat
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(identity_path, flags)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode)
                or info.st_uid != uid or info.st_mode & 0o022
                or info.st_nlink != 1 or info.st_size > _MAX_IDENTITY_BYTES):
            raise TelemetryError("unsafe ToF identity file")
        raw = os.read(fd, _MAX_IDENTITY_BYTES + 1)
        if len(raw) > _MAX_IDENTITY_BYTES:
            raise TelemetryError("oversized ToF identity")
    finally:
        os.close(fd)
    data = _strict_identity_json(raw)
    if (set(data) - {"service", "version", "revision", "built_at", "exe", "pid"}
            or not {"service", "version", "revision", "pid"} <= set(data)
            or data["service"] != "tofd"
            or type(data["version"]) is not str
            or not 1 <= len(data["version"]) <= 64
            or type(data["pid"]) is not int or data["pid"] != peer_pid
            or type(data["revision"]) is not str
            or data["revision"] != expected_revision):
        raise TelemetryError("ToF identity not the expected pinned daemon")
    if ("exe" in data and data["exe"] is not None
            and (type(data["exe"]) is not str
                 or not data["exe"].endswith("/bin/tofd")
                 or "/opt/robot/daemon/releases/" not in data["exe"])):
        raise TelemetryError("unexpected OEM executable identity")
    for optional in ("built_at",):
        if optional in data and data[optional] is not None and (
                type(data[optional]) is not str or len(data[optional]) > 128):
            raise TelemetryError("invalid OEM build metadata")


def _read_tof_once(
    sock_path: "Path", identity_path: "Path", *, uid: int, gid: int,
    revision: str, timeout_s: float, official: bool,
) -> OemTofSample:
    """Internal bounded contract reader; custom paths remain UNTRUSTED fixtures.

    On failed identity, deadline, unavailable sensor, bad seq/timestamp or
    malformed notification, discard the reading and report only a short status.
    This is one request and one notification, with no retry or SQLite write.
    """
    from pathlib import Path

    trusted_path = (official and str(sock_path) == _OEM_TOF_SOCKET
                    and str(identity_path) == _OEM_TOF_IDENTITY
                    and revision == _PINNED_OEM_TOF_REVISION)
    provenance = ("oem_local_unix_peer_not_hardware"
                  if trusted_path else "untrusted_local_fixture")
    refused = OemTofSample("unavailable_or_unverified", provenance)
    if (not isinstance(sock_path, Path) or not isinstance(identity_path, Path)
            or not sock_path.is_absolute() or not identity_path.is_absolute()
            or type(uid) is not int or uid < 0
            or type(gid) is not int or gid < 0
            or type(revision) is not str or not revision
            or not _finite(timeout_s) or not .05 <= timeout_s <= 1.):
        return refused

    try:
        inode = _check_tof_paths(sock_path, identity_path, uid, gid)
        with ReadOnlyUnixRpc(sock_path, timeout_s=timeout_s, role="tofd") as rpc:
            pid, peer_uid, _ = rpc.peer_credentials()
            if peer_uid != uid:
                raise TelemetryError("ToF Unix peer UID mismatch")
            if _check_tof_paths(sock_path, identity_path, uid, gid) != inode:
                raise TelemetryError("ToF socket changed during connect")
            _load_tof_identity(identity_path, uid, revision, pid)
            ack = rpc.request("tof.stream")
            # tofd --fake and --sim deliberately share the same wire shape.
            # Their own handshake names the source, which must not be trusted
            # as a real VL53L8CX sensor. Even this label isn't hardware proof.
            if (type(ack.get("rows")) is not int or ack["rows"] != 8
                    or type(ack.get("cols")) is not int or ack["cols"] != 8
                    or type(ack.get("hz")) is not int
                    or not 1 <= ack["hz"] <= 15
                    or ack.get("sensor") != "VL53L8CX"
                    or ack.get("unavailable") is not None):
                raise TelemetryError("ToF stream has no declared OEM physical sensor")
            notification = rpc.next_notification()
            depth = parse_depth(notification)
        if depth.seq <= 0 or depth.t_ns is None:
            raise TelemetryError("missing depth sequence or OEM monotonic stamp")
        age_ns = time.monotonic_ns() - depth.t_ns
        if age_ns < 0 or age_ns > _MAX_TOF_SAMPLE_AGE_NS:
            raise TelemetryError("stale/future ToF sample")
        return OemTofSample(
            "local_oem_contract_checked_not_hardware" if trusted_path
            else "fixture_protocol_only",
            provenance, depth, age_ns / 1_000_000,
            local_peer_checked=bool(trusted_path),
        )
    except (OSError, TelemetryError, TypeError, ValueError):
        return refused


def read_verified_local_tof_once(*, timeout_s: float = .5) -> OemTofSample:
    """Opt-in local OEM ToF gate. Never opens a caller-provided socket.

    Real robot use requires preflight/permission approval: 'robot' is NOT a
    read-only OS capability for robotd. The expected revision is deliberately
    pinned; unknown patched releases remain unavailable until audited.
    """
    from pathlib import Path
    if not _finite(timeout_s) or not .05 <= timeout_s <= 1.:
        raise ValueError("ToF one-shot timeout must be in [0.05,1] seconds")
    try:
        import grp
        import pwd
        uid = pwd.getpwnam("tofd").pw_uid
        gid = grp.getgrnam("robot").gr_gid
    except (ImportError, KeyError, OSError):
        return OemTofSample("unavailable_or_unverified",
                            "oem_local_unix_peer_not_hardware")
    return _read_tof_once(
        Path(_OEM_TOF_SOCKET), Path(_OEM_TOF_IDENTITY),
        uid=uid, gid=gid, revision=_PINNED_OEM_TOF_REVISION,
        timeout_s=timeout_s, official=True,
    )
