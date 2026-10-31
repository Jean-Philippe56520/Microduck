"""P15-B2: OS-local ToF source provenance gate; one-off, read-only, offline.

Keep sim_ipc.py unchanged: P14A/P14B's audited 19-module source closure
specifically forbids new imports there. This bounded adapter reuses its
existing read-only JSON-RPC and depth parser, without a second socket client,
camera, memory, daemon, or motor path. Its OS checks are not cryptographic
hardware authentication and do not make group 'robot' read-only at OS level.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import socket
import time
from typing import Any

from .sim_ipc import DepthReading, ReadOnlyUnixRpc, TelemetryError, parse_depth


def _finite(v: object) -> bool:
    return type(v) in (float, int) and math.isfinite(v)


def _peer_credentials(reader: ReadOnlyUnixRpc) -> tuple[int, int, int]:
    """Kernel PID/UID/GID from the already-open OEM RPC socket.

    The audited P14A transport does not expose this as public API; use its
    existing connected socket read-only here, not a second connection. If
    the transport ever changes, fail closed rather than guessing the peer.
    """
    import struct
    conn = reader._socket
    if conn is None or not hasattr(socket, "SO_PEERCRED"):
        raise TelemetryError("Unix peer credentials unavailable")
    try:
        data = conn.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", data)
    except (OSError, struct.error) as exc:
        raise TelemetryError("invalid Unix peer credentials") from exc
    if pid <= 0 or uid < 0 or gid < 0:
        raise TelemetryError("invalid Unix peer credentials")
    return pid, uid, gid


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
            pid, peer_uid, _ = _peer_credentials(rpc)
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
