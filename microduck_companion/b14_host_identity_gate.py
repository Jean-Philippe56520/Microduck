"""P15-B14: unshipped Linux host fixture for mediad's existing identity.json.

The real OEM mediad publishes /run/mediad/identity.json at startup. It has
no reason for Kwipi to access /run/mediad/media.sock (robot-group, frame RPC).
Here we exercise read-only file + SO_PEERCRED + B13 wire guards ONLY under a
private temporary host fixture directory. This is not robot authentication.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import socket
import stat
import struct
import tempfile
import time

from .b12_local_wire_contract import (
    B12LocalSequenceGate, parse_b12_local_shape_notification,
)
from .passive_media_router import PassiveMediaError
from .passive_sources import PassiveSourceError, _connect_unix, _recv_line, _strict_json

B12_REVISION = "e2e9bfef7d7c4f46fe51924937e7939d78d00383"
_MAX_IDENTITY_BYTES = 2048
_MAX_DETECTION_BYTES = 4096


class B14IdentityRefused(ValueError):
    """Fail-closed identity-file + socket fixture guard."""


@dataclass(frozen=True)
class B14HostIdentityResult:
    status: str
    peer_pid: int
    peer_uid: int
    identity_revision: str
    look_seq: int
    reported_boxes: int
    category: str = "unknown"
    verified_sensor: bool = False
    media_bytes_stored: int = 0
    memory_writes: int = 0
    motor_commands_issued: int = 0


def _private_host_root(root: Path) -> os.stat_result:
    """Only a direct 0700 directory inside the host temporary directory."""
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (not root.is_absolute() or root.name in ("", "kwipi-b14-")
            or not root.name.startswith("kwipi-b14-")
            or root.parent.resolve(strict=True) != temp):
        raise B14IdentityRefused("not a permitted Linux test fixture")
    info = root.lstat()  # Do not follow a symlink named as the fixture root.
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise B14IdentityRefused("fixture root is not private")
    return info


def _socket_info(path: Path, uid: int) -> os.stat_result:
    info = path.lstat()
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != uid
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise B14IdentityRefused("unexpected fixture socket owner or mode")
    return info


def _same_stat(before: os.stat_result, after: os.stat_result) -> bool:
    return ((before.st_dev, before.st_ino, before.st_uid, before.st_mode)
            == (after.st_dev, after.st_ino, after.st_uid, after.st_mode))


def _read_identity(root: Path, uid: int) -> tuple[bytes, tuple[int, ...]]:
    """Bounded no-follow openat on a held private directory FD, never exec."""
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    dfd = os.open(root, flags | os.O_DIRECTORY)
    try:
        directory = os.fstat(dfd)
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != uid
                or stat.S_IMODE(directory.st_mode) != 0o700):
            raise B14IdentityRefused("fixture directory changed")
        fd = os.open("identity.json", flags, dir_fd=dfd)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
                    or (stat.S_IMODE(info.st_mode) & 0o022) != 0
                    or info.st_nlink != 1 or info.st_size > _MAX_IDENTITY_BYTES):
                raise B14IdentityRefused("identity file is not a safe regular file")
            blob = bytearray()
            while len(blob) <= _MAX_IDENTITY_BYTES:
                block = os.read(fd, _MAX_IDENTITY_BYTES + 1 - len(blob))
                if not block:
                    break
                blob.extend(block)
            if (not blob or len(blob) > _MAX_IDENTITY_BYTES
                    or blob.count(b"\n") != 1 or not blob.endswith(b"\n")):
                raise B14IdentityRefused("invalid bounded identity file")
            fingerprint = (info.st_dev, info.st_ino, info.st_uid,
                           info.st_mode, info.st_size, info.st_mtime_ns)
            return bytes(blob), fingerprint
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


def _pinned_identity(raw: bytes, pid: int) -> str:
    """Validate the OEM Identity struct's B12 claim (not a binary signature)."""
    obj = _strict_json(raw)
    required = {"service", "version", "revision", "pid"}
    optional = {"built_at", "exe"}
    if (not required.issubset(obj) or not set(obj).issubset(required | optional)
            or obj["service"] != "mediad" or type(obj["version"]) is not str
            or not 0 < len(obj["version"]) <= 80
            or obj["revision"] != B12_REVISION
            or type(obj["pid"]) is not int or obj["pid"] != pid):
        raise B14IdentityRefused("identity does not match pinned B12 peer")
    for key in optional:
        if key in obj and obj[key] is not None:
            if type(obj[key]) is not str or len(obj[key]) > 512:
                raise B14IdentityRefused("invalid OEM optional identity field")
    if "exe" in obj and obj["exe"] is not None:
        exe = obj["exe"]
        if not exe.startswith("/") or not exe.endswith("/mediad"):
            raise B14IdentityRefused("unexpected claimed OEM executable name")
    return obj["revision"]


def _remaining(deadline: float) -> float:
    result = deadline - time.monotonic()
    if result <= 0:
        raise B14IdentityRefused("fixture deadline exceeded")
    return result


def read_b14_identity_host_fixture(
    root: str | Path, *, expected_uid: int,
    sequence_gate: B12LocalSequenceGate, timeout_s: float = 0.6,
) -> B14HostIdentityResult:
    """Inspect one real Unix socket and one OEM-shaped identity file on Linux.

    Never accesses /run, never sends any bytes, never opens a frame socket.
    A successful test is only an internally consistent SELF-CLAIMED host
    fixture, not physical provenance, authentication of the code, or safety.
    """
    if (type(expected_uid) is not int or expected_uid <= 0
            or expected_uid != os.geteuid()):
        raise B14IdentityRefused("requires unprivileged fixture UID")
    if not isinstance(sequence_gate, B12LocalSequenceGate):
        raise B14IdentityRefused("persistent B13 sequence gate required")
    if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
            or not .05 <= timeout_s <= 2.):
        raise B14IdentityRefused("invalid timeout")
    home = Path(root)
    try:
        root_info = _private_host_root(home)
        socket_path = home / "detections.sock"
        sock_info = _socket_info(socket_path, expected_uid)
        deadline = time.monotonic() + float(timeout_s)
        with _connect_unix(socket_path, _remaining(deadline)) as conn:
            if not hasattr(socket, "SO_PEERCRED"):
                raise B14IdentityRefused("SO_PEERCRED is required")
            cred = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                   struct.calcsize("3i"))
            pid, uid, gid = struct.unpack("3i", cred)
            if pid <= 1 or uid != expected_uid or gid < 0:
                raise B14IdentityRefused("wrong local producer PID/UID/GID")
            first, first_stat = _read_identity(home, expected_uid)
            revision = _pinned_identity(first, pid)
            message = _recv_line(conn, _remaining(deadline),
                                 max_bytes=_MAX_DETECTION_BYTES)
            second, second_stat = _read_identity(home, expected_uid)
            if first != second or first_stat != second_stat:
                raise B14IdentityRefused("identity changed during read")
            if not _same_stat(root_info, _private_host_root(home)):
                raise B14IdentityRefused("fixture root inode changed")
            if not _same_stat(sock_info, _socket_info(socket_path, expected_uid)):
                raise B14IdentityRefused("detection socket inode changed")
            item = parse_b12_local_shape_notification(
                message, now_monotonic_ns=time.monotonic_ns())
            if not sequence_gate.accept(item):
                raise B14IdentityRefused("duplicate or regressing local look")
            return B14HostIdentityResult(
                status="host_fixture_identity_claim_consistent_not_sensor",
                peer_pid=pid, peer_uid=uid, identity_revision=revision,
                look_seq=item.look_seq, reported_boxes=item.reported_boxes,
            )
    except (B14IdentityRefused, PassiveMediaError, PassiveSourceError,
            OSError, ValueError, struct.error, UnicodeError) as exc:
        raise B14IdentityRefused("P15-B14 host identity fixture refused") from exc
