"""P15-B15: two-UID OEM-shape metadata gate on Linux TEMPORARY fixtures only.

This is intentionally NOT a robot reader. The actual mediad/kwipi identities,
/run mount, kernel options, release executable, ACLs and sensor provenance have
not been verified on RK3566. Reuses the OEM B8 access ACL wire contract,
B13's payload/sequence checks and B14's pinned identity parser. Never sends
an RPC, reads camera bytes, stores memory, or issues a motor command.
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
from .b14_host_identity_gate import B14IdentityRefused, _pinned_identity
from .passive_media_router import PassiveMediaError
from .passive_sources import PassiveSourceError, _connect_unix, _recv_line


class B15HostRefused(ValueError):
    """Fail closed; never promote a cross-UID fixture to sensor provenance."""


@dataclass(frozen=True)
class B15HostResult:
    status: str
    peer_pid: int
    peer_uid: int
    revision: str
    look_seq: int
    reported_boxes: int
    category: str = "unknown"
    verified_sensor: bool = False
    media_bytes_stored: int = 0
    memory_writes: int = 0
    motor_commands_issued: int = 0


def _expected_acl(uid: int, *, directory: bool) -> bytes:
    """Exact 44-byte B8 native Linux ACL. Strict read-back, no writes."""
    named = 1 if directory else 6
    owner = 7 if directory else 6
    entries = ((1, owner, 0xffffffff), (2, named, uid),
               (4, 0, 0xffffffff), (16, named, 0xffffffff),
               (32, 0, 0xffffffff))
    return struct.pack("=I", 2) + b"".join(
        struct.pack("=HHI", tag, perm, user) for tag, perm, user in entries
    )


def _check_node(path: Path, *, kind: str, uid: int, gid: int | None,
                mode: int, acl: bytes | None = None) -> os.stat_result:
    info = path.lstat()
    pred = {"dir": stat.S_ISDIR, "sock": stat.S_ISSOCK,
            "file": stat.S_ISREG}[kind]
    if (not pred(info.st_mode) or info.st_uid != uid
            or (gid is not None and info.st_gid != gid)
            or stat.S_IMODE(info.st_mode) != mode):
        raise B15HostRefused("fixture node identity, mode or type mismatch")
    if acl is not None:
        if os.getxattr(path, "system.posix_acl_access") != acl:
            raise B15HostRefused("ACL differs from B8 exact named-UID policy")
    return info


def _same_node(old: os.stat_result, new: os.stat_result) -> bool:
    return ((old.st_dev, old.st_ino, old.st_uid, old.st_gid, old.st_mode)
            == (new.st_dev, new.st_ino, new.st_uid, new.st_gid, new.st_mode))


def _identity(runtime: Path, mediad_uid: int, mediad_gid: int) -> tuple[bytes, tuple[int, ...]]:
    """Single-bounded openat read of an OEM-shaped identity (no symlinks)."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    dfd = os.open(runtime, flags | os.O_DIRECTORY)
    try:
        parent = os.fstat(dfd)
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != mediad_uid
                or parent.st_gid != mediad_gid
                or stat.S_IMODE(parent.st_mode) != 0o755):
            raise B15HostRefused("runtime parent changed")
        fd = os.open("identity.json", flags, dir_fd=dfd)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != mediad_uid
                    or info.st_gid != mediad_gid or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o644
                    or info.st_size > 2048):
                raise B15HostRefused("identity inode or permissions unexpected")
            data = bytearray()
            while len(data) <= 2048:
                block = os.read(fd, 2049 - len(data))
                if not block:
                    break
                data.extend(block)
            if (not data or len(data) > 2048 or data.count(b"\n") != 1
                    or not data.endswith(b"\n")):
                raise B15HostRefused("invalid identity bytes")
            return bytes(data), (info.st_dev, info.st_ino, info.st_uid,
                                 info.st_gid, info.st_mode, info.st_size,
                                 info.st_mtime_ns)
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


def read_b15_cross_uid_host_fixture(
    root: str | Path, *, mediad_uid: int, mediad_gid: int,
    kwipi_uid: int, robot_gid: int, sequence_gate: B12LocalSequenceGate,
    timeout_s: float = .75,
) -> B15HostResult:
    """Read ONE fake mediad notification as a different Linux UID.

    Root MUST be a root-owned temporary kwipi-b15-* directory directly under
    the system temporary directory. Does not access real /run or use privilege
    escalation. The observer must already be a dedicated unprivileged UID.
    """
    if any(type(x) is not int or x <= 0 for x in
           (mediad_uid, mediad_gid, kwipi_uid, robot_gid)):
        raise B15HostRefused("invalid fake identities")
    if (mediad_uid == kwipi_uid or robot_gid == mediad_gid
            or os.geteuid() != kwipi_uid or os.getuid() != kwipi_uid
            or os.getgid() == robot_gid or robot_gid in os.getgroups()):
        raise B15HostRefused("observer identity is not isolated")
    if not isinstance(sequence_gate, B12LocalSequenceGate):
        raise B15HostRefused("B13 monotonic sequence gate required")
    if (type(timeout_s) not in (float, int) or not math.isfinite(timeout_s)
            or not .05 <= timeout_s <= 2.):
        raise B15HostRefused("timeout out of bounds")
    path = Path(root)
    tmp = Path(tempfile.gettempdir()).resolve(strict=True)
    try:
        if (not path.is_absolute() or not path.name.startswith("kwipi-b15-")
                or path.parent.resolve(strict=True) != tmp):
            raise B15HostRefused("not a direct temporary fixture root")
        root_before = _check_node(path, kind="dir", uid=0, gid=None, mode=0o755)
        runtime = path / "mediad"
        runtime_before = _check_node(runtime, kind="dir", uid=mediad_uid,
                                     gid=mediad_gid, mode=0o755)
        private = runtime / "kwipi"
        priv_acl = _expected_acl(kwipi_uid, directory=True)
        priv_before = _check_node(private, kind="dir", uid=mediad_uid,
                                  gid=mediad_gid, mode=0o710, acl=priv_acl)
        sock_path = private / "detections.sock"
        sock_acl = _expected_acl(kwipi_uid, directory=False)
        sock_before = _check_node(sock_path, kind="sock", uid=mediad_uid,
                                  gid=mediad_gid, mode=0o660, acl=sock_acl)
        deadline = time.monotonic() + float(timeout_s)
        with _connect_unix(sock_path, max(.001, deadline-time.monotonic())) as conn:
            if not hasattr(socket, "SO_PEERCRED"):
                raise B15HostRefused("Linux SO_PEERCRED missing")
            pid, uid, gid = struct.unpack(
                "3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                     struct.calcsize("3i")))
            if pid <= 1 or uid != mediad_uid or gid != mediad_gid:
                raise B15HostRefused("wrong daemon credentials")
            before, bstat = _identity(runtime, mediad_uid, mediad_gid)
            revision = _pinned_identity(before, pid)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise B15HostRefused("source deadline")
            raw = _recv_line(conn, remaining, max_bytes=4096)
            after, astat = _identity(runtime, mediad_uid, mediad_gid)
            if before != after or bstat != astat:
                raise B15HostRefused("daemon identity changed mid-read")
            for target, old, kw in (
                (path, root_before, {"kind":"dir", "uid":0,
                                     "gid":None, "mode":0o755}),
                (runtime, runtime_before, {"kind":"dir", "uid":mediad_uid,
                                            "gid":mediad_gid, "mode":0o755}),
                (private, priv_before, {"kind":"dir", "uid":mediad_uid,
                                          "gid":mediad_gid, "mode":0o710,
                                          "acl":priv_acl}),
                (sock_path, sock_before, {"kind":"sock", "uid":mediad_uid,
                                           "gid":mediad_gid, "mode":0o660,
                                           "acl":sock_acl}),
            ):
                if not _same_node(old, _check_node(target, **kw)):
                    raise B15HostRefused("socket/runtime replaced mid-read")
            shape = parse_b12_local_shape_notification(
                raw, now_monotonic_ns=time.monotonic_ns())
            if not sequence_gate.accept(shape):
                raise B15HostRefused("duplicate or regressing capture")
            return B15HostResult(
                status="host_two_uid_claim_consistent_not_sensor",
                peer_pid=pid, peer_uid=uid, revision=revision,
                look_seq=shape.look_seq, reported_boxes=shape.reported_boxes)
    except (B15HostRefused, B14IdentityRefused, PassiveSourceError,
            PassiveMediaError, OSError, ValueError, struct.error) as exc:
        raise B15HostRefused("P15-B15 cross-UID host fixture refused") from exc
