"""P15-B16: opt-in, read-only OEM mediad B12 metadata receiver.

This is a TARGET-PATH-CAPABLE candidate, NOT installed in B10 or a proof
that the detector is active, the live binary is B12, or a camera was used.
Never request media.frame / robot RPC, create a service, write SQLite,
interpret one-class boxes, or grant motor permissions.

B4/B8/B12 producer remains opt-in and the OEM detector is disabled by
default. This module alone cannot start it. Success means a Linux peer and
a self-published OEM identity *claim* are internally consistent.
"""
from __future__ import annotations

from dataclasses import dataclass
import grp
import math
import os
from pathlib import Path
import pwd
import socket
import struct
import tempfile
import time

from .b12_local_wire_contract import (
    B12LocalSequenceGate, parse_b12_local_shape_notification,
)
from .b14_host_identity_gate import B14IdentityRefused, _pinned_identity
from .b15_cross_uid_host_gate import (
    B15HostRefused, _check_node, _expected_acl, _identity, _same_node,
)
from .passive_media_router import PassiveMediaError
from .passive_sources import PassiveSourceError, _connect_unix, _recv_line

_RUN = Path("/run")
_SOCKET_NAME = "detections.sock"
_MAX_READ_S = 0.5
_MIN_INTERVAL_S = 0.5


class B16Refused(ValueError):
    """No trusted B12 metadata was accepted. No side effects."""


@dataclass(frozen=True)
class B16ReadResult:
    status: str
    reported_boxes: int = 0
    look_seq: int | None = None
    captured_at_monotonic_ns: int | None = None
    peer_pid: int | None = None
    peer_uid: int | None = None
    revision_claim: str | None = None
    category: str = "unknown"
    provenance: str = "b12_oem_peer_self_claim_not_sensor"
    verified_sensor: bool = False
    executable_verified: bool = False
    media_bytes_stored: int = 0
    camera_frames_requested: int = 0
    memory_writes: int = 0
    motor_commands_issued: int = 0


def _observer_ids() -> tuple[int, int, int, int, int]:
    """Only existing NSS identities; never create users or add a group."""
    try:
        media = pwd.getpwnam("mediad")
        kwipi = pwd.getpwnam("kwipi")
        robot_gid = grp.getgrnam("robot").gr_gid
    except KeyError as exc:
        raise B16Refused("installed OEM accounts unavailable") from exc
    return (media.pw_uid, media.pw_gid, kwipi.pw_uid, kwipi.pw_gid,
            robot_gid)


def _checked_once(
    run_root: Path, *, mediad_uid: int, mediad_gid: int,
    kwipi_uid: int, kwipi_gid: int, robot_gid: int,
    sequence_gate: B12LocalSequenceGate, timeout_s: float,
) -> B16ReadResult:
    """Single bounded passive read. /run in production; B15 root-only fixtures.

    The temporary-root exception exists only to exercise the exact same code
    against Linux ACL and two real dropped UIDs in CI. The public reader
    below NEVER accepts an injected path or identities.
    """
    if (not isinstance(run_root, Path) or not run_root.is_absolute()
            or any(type(n) is not int or n <= 0 for n in
                   (mediad_uid, mediad_gid, kwipi_uid, kwipi_gid, robot_gid))
            or len({mediad_uid, kwipi_uid, 0}) != 3
            or robot_gid == kwipi_gid
            or not isinstance(sequence_gate, B12LocalSequenceGate)
            or type(timeout_s) not in (int, float)
            or not math.isfinite(timeout_s)
            or not .05 <= timeout_s <= _MAX_READ_S):
        raise B16Refused("invalid offline consumer policy")
    if (os.getuid() != kwipi_uid or os.geteuid() != kwipi_uid
            or os.getgid() != kwipi_gid or os.getegid() != kwipi_gid
            or any(group != kwipi_gid for group in os.getgroups())
            or robot_gid in os.getgroups()):
        raise B16Refused("observer requires the isolated Kwipi identity")
    if run_root != _RUN:
        tmp = Path(tempfile.gettempdir()).resolve(strict=True)
        if (run_root.parent.resolve(strict=True) != tmp
                or not run_root.name.startswith("kwipi-b15-")):
            raise B16Refused("only the existing B15 Linux root fixture is allowed")
    try:
        root_before = _check_node(
            run_root, kind="dir", uid=0, gid=None, mode=0o755)
        runtime = run_root / "mediad"
        parent_before = _check_node(
            runtime, kind="dir", uid=mediad_uid, gid=mediad_gid, mode=0o755)
        private = runtime / "kwipi"
        directory_acl = _expected_acl(kwipi_uid, directory=True)
        private_before = _check_node(
            private, kind="dir", uid=mediad_uid, gid=mediad_gid,
            mode=0o710, acl=directory_acl)
        socket_path = private / _SOCKET_NAME
        socket_acl = _expected_acl(kwipi_uid, directory=False)
        socket_before = _check_node(
            socket_path, kind="sock", uid=mediad_uid, gid=mediad_gid,
            mode=0o660, acl=socket_acl)

        deadline = time.monotonic() + timeout_s
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise B16Refused("deadline expired before connection")
        with _connect_unix(socket_path, remaining) as conn:
            if not hasattr(socket, "SO_PEERCRED"):
                raise B16Refused("Linux SO_PEERCRED unavailable")
            raw_cred = conn.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            pid, uid, gid = struct.unpack("3i", raw_cred)
            if pid <= 1 or uid != mediad_uid or gid != mediad_gid:
                raise B16Refused("socket peer is not mediad")
            before, before_stat = _identity(runtime, mediad_uid, mediad_gid)
            revision = _pinned_identity(before, pid)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise B16Refused("deadline expired before metadata")
            line = _recv_line(conn, remaining, max_bytes=4096)
            after, after_stat = _identity(runtime, mediad_uid, mediad_gid)
            if before != after or before_stat != after_stat:
                raise B16Refused("identity changed during reception")

            for path, old, expected in (
                (run_root, root_before,
                 dict(kind="dir", uid=0, gid=None, mode=0o755)),
                (runtime, parent_before,
                 dict(kind="dir", uid=mediad_uid, gid=mediad_gid, mode=0o755)),
                (private, private_before,
                 dict(kind="dir", uid=mediad_uid, gid=mediad_gid,
                      mode=0o710, acl=directory_acl)),
                (socket_path, socket_before,
                 dict(kind="sock", uid=mediad_uid, gid=mediad_gid,
                      mode=0o660, acl=socket_acl)),
            ):
                if not _same_node(old, _check_node(path, **expected)):
                    raise B16Refused("runtime/socket inode replaced")

            shape = parse_b12_local_shape_notification(
                line, now_monotonic_ns=time.monotonic_ns())
            if not sequence_gate.accept(shape):
                raise B16Refused("duplicate or regressing B12 observation")
            return B16ReadResult(
                status="oem_identity_and_b12_claim_consistent_not_sensor",
                reported_boxes=shape.reported_boxes,
                look_seq=shape.look_seq,
                captured_at_monotonic_ns=shape.captured_at_monotonic_ns,
                peer_pid=pid, peer_uid=uid, revision_claim=revision)
    except (B16Refused, B15HostRefused, B14IdentityRefused,
            PassiveSourceError, PassiveMediaError, OSError, ValueError,
            struct.error) as exc:
        raise B16Refused("P15-B16 read-only OEM metadata refused") from exc


class B16OEMDetectionReader:
    """Explicit opt-in, one fresh notification per >=500 ms; no daemon.

    Only this public class is the candidate OEM entrypoint. It hardcodes
    /run/mediad/kwipi/detections.sock, resolves existing system accounts and
    refuses every foreign/privileged observer. The result is diagnostic and
    CANNOT enter cognition, motor control or ExperienceMemory as sensor truth.
    """

    def __init__(self, *, enabled: bool = False, timeout_s: float = 0.4) -> None:
        if type(enabled) is not bool:
            raise ValueError("explicit boolean opt-in required")
        if (type(timeout_s) not in (int, float)
                or not math.isfinite(timeout_s)
                or not .05 <= timeout_s <= _MAX_READ_S):
            raise ValueError("P15-B16 read timeout exceeds its passive budget")
        self.enabled = enabled
        self.timeout_s = float(timeout_s)
        self._sequence_gate = B12LocalSequenceGate()
        self._last_attempt: float | None = None

    def read(self) -> B16ReadResult:
        if not self.enabled:
            return B16ReadResult("disabled_no_oem_contact")
        try:
            now = time.monotonic()
            if not math.isfinite(now) or now < 0:
                return B16ReadResult("clock_unavailable")
            if self._last_attempt is not None:
                if now < self._last_attempt:
                    self._last_attempt = now
                    return B16ReadResult("clock_regressed")
                if now - self._last_attempt < _MIN_INTERVAL_S:
                    return B16ReadResult("rate_limited")
            self._last_attempt = now
            return _checked_once(
                _RUN, mediad_uid=_observer_ids()[0],
                mediad_gid=_observer_ids()[1],
                kwipi_uid=_observer_ids()[2],
                kwipi_gid=_observer_ids()[3],
                robot_gid=_observer_ids()[4],
                sequence_gate=self._sequence_gate, timeout_s=self.timeout_s)
        except (B16Refused, OSError, ValueError, KeyError):
            return B16ReadResult("unavailable_or_refused")
