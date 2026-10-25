"""F1-B: bounded read-only observation transport, not a detector or motor adapter.

Two intentionally separate lanes:
* FixtureUnixReader reads *mock-only* categories from a local Unix socket and
  never upgrades the untrusted sender to "sensor" provenance.
* probe_official_mediad sends ONLY the OEM "hello" RPC (no media.frame
  request). It returns availability/identity metadata, never camera pixels,
  categories, a floor clearance or motor authority.

Neither function stores media, writes SQLite, uses a network API or drives
robotd. The local OEM socket uid and git revision are checks, not remote
cryptographic authentication; the real board has NOT been tested.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import socket
import stat
import struct
import time
from typing import Callable

from .passive_observations import MAX_EVENTS, OBJECT_CATEGORIES
from .perception import PerceptionEvent, PerceptionSnapshot

OEM_SOCKET = "/run/mediad/media.sock"
OEM_UID_NAME = "mediad"
OEM_API_VERSION = 44
PINNED_OEM_REVISION = "942e58e3aa6dbb28e7037203fff11866122c7567"
MAX_WIRE_BYTES = 8192
MAX_FRAME_AGE_S = 2.
MAX_TIMEOUT_S = 3.
MIN_POLL_INTERVAL_S = .5


class PassiveSourceError(ValueError):
    """Untrusted, unavailable, duplicate or malformed passive fixture source."""


@dataclass(frozen=True)
class PassiveRead:
    """One bounded passive acquisition. Status != ok never yields events."""

    status: str
    snapshot: PerceptionSnapshot
    sequence: int | None = None
    channel: str = "mock_fixture_unix"


@dataclass(frozen=True)
class MediaProbe:
    """No observations: only a local, read-only mediad availability check."""

    status: str
    api_version: int | None
    peer_uid: int | None
    revision: str | None
    verified_for_pinned_oem: bool
    channel: str = "oem_media_hello_only"


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _check_timeouts(timeout_s: float, max_age_s: float) -> None:
    if not _finite(timeout_s) or not 0 < timeout_s <= MAX_TIMEOUT_S:
        raise ValueError("timeout_s must be in (0, 3]")
    if not _finite(max_age_s) or not 0 < max_age_s <= MAX_FRAME_AGE_S:
        raise ValueError("max_age_s must be in (0, 2]")


def _strict_json(raw: bytes) -> dict:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise PassiveSourceError("duplicate JSON property")
            obj[key] = value
        return obj

    try:
        obj = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                PassiveSourceError("nonfinite JSON literal")),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise PassiveSourceError("invalid JSON frame") from exc
    if type(obj) is not dict:
        raise PassiveSourceError("JSON frame must be a dictionary")
    return obj


def _connect_unix(path: Path, timeout_s: float) -> socket.socket:
    """Reject symlinks/non-sockets before connecting; verify peer separately."""
    if not hasattr(socket, "AF_UNIX"):
        raise PassiveSourceError("Unix sockets not supported")
    try:
        mode = path.lstat().st_mode
        if not stat.S_ISSOCK(mode):
            raise PassiveSourceError("socket path is not a Unix socket")
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            conn.settimeout(timeout_s)
            conn.connect(str(path))
            return conn
        except (OSError, socket.timeout):
            conn.close()
            raise
    except (OSError, socket.timeout) as exc:
        raise PassiveSourceError("local source unavailable") from exc


def _recv_line(conn: socket.socket, timeout_s: float, *,
               max_bytes: int = MAX_WIRE_BYTES) -> bytes:
    # Timeouts cap total acquisition, not merely each recv() (slow-drip case).
    import select
    deadline = time.monotonic() + timeout_s
    buf = bytearray()
    while len(buf) <= max_bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PassiveSourceError("source deadline exceeded")
        readable, _, _ = select.select([conn], [], [], remaining)
        if not readable:
            raise PassiveSourceError("source deadline exceeded")
        try:
            chunk = conn.recv(min(1024, max_bytes + 1 - len(buf)))
        except (OSError, socket.timeout) as exc:
            raise PassiveSourceError("source disconnected") from exc
        if not chunk:
            raise PassiveSourceError("source disconnected")
        buf.extend(chunk)
        if b"\n" in chunk:
            line, _, tail = bytes(buf).partition(b"\n")
            if tail.strip():
                raise PassiveSourceError("unexpected trailing stream data")
            if len(line) > max_bytes:
                raise PassiveSourceError("source frame exceeds byte budget")
            return line
    raise PassiveSourceError("source frame exceeds byte budget")


def _read_fixture_frame(raw: dict, *, now: float,
                        max_age_s: float) -> tuple[int, PerceptionSnapshot]:
    """Strict synthetic protocol; never accept claimed robot/sensor provenance."""
    if set(raw) != {"schema_version", "sequence", "sample_monotonic_s", "events"}:
        raise PassiveSourceError("fixture frame schema mismatch")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise PassiveSourceError("unsupported fixture frame version")
    sequence = raw["sequence"]
    if type(sequence) is not int or not 0 <= sequence < 2**63:
        raise PassiveSourceError("invalid sequence")
    observed_at = raw["sample_monotonic_s"]
    if not _finite(observed_at) or observed_at < 0:
        raise PassiveSourceError("invalid monotonic timestamp")
    age = now - observed_at
    if not 0 <= age <= max_age_s:
        raise PassiveSourceError("future or stale source frame")
    events = raw["events"]
    if type(events) is not list or len(events) > MAX_EVENTS:
        raise PassiveSourceError("invalid event budget")
    parsed: list[PerceptionEvent] = []
    for item in events:
        if type(item) is not dict:
            raise PassiveSourceError("invalid event record")
        kind = item.get("kind")
        if kind == "object_label":
            if set(item) != {"kind", "category", "track_id", "confidence", "ttl_s"}:
                raise PassiveSourceError("object fixture schema mismatch")
            label = item["category"]
            if type(label) is not str or label not in OBJECT_CATEGORIES:
                raise PassiveSourceError("object category not allowed")
            track = item["track_id"]
            if (type(track) is not str or not 7 <= len(track) <= 48
                    or not track.startswith("track-")
                    or not all(c.isascii() and (c.isalnum() or c in "-_")
                               for c in track)):
                raise PassiveSourceError("invalid ephemeral track id")
        elif kind == "sound_label":
            if set(item) != {"kind", "category", "confidence", "ttl_s"}:
                raise PassiveSourceError("sound fixture schema mismatch")
            label, track = item["category"], None
        else:
            # Reject motor/health/safety grants and unknown event types.
            raise PassiveSourceError("non-passive fixture event")
        ttl_s = item["ttl_s"]
        if not _finite(ttl_s) or not 0 < ttl_s <= MAX_FRAME_AGE_S:
            raise PassiveSourceError("invalid fixture event TTL")
        try:
            parsed.append(PerceptionEvent(
                kind=kind, value=label, source="mock",
                observed_at=float(observed_at), ttl_s=float(ttl_s),
                confidence=item["confidence"], track_id=track,
            ))
        except (ValueError, TypeError, KeyError) as exc:
            raise PassiveSourceError("invalid passive fixture event") from exc
    return sequence, PerceptionSnapshot("mock", tuple(parsed), now)


class FixtureUnixReader:
    """A socket-backed test fixture reader. ALWAYS mock; no source promotion."""

    def __init__(self, path: str | Path, *, timeout_s: float = 1.,
                 max_age_s: float = 1., min_interval_s: float = .5,
                 clock: Callable[[], float] = time.monotonic) -> None:
        _check_timeouts(timeout_s, max_age_s)
        if not _finite(min_interval_s) or not MIN_POLL_INTERVAL_S <= min_interval_s <= 10:
            raise ValueError("min_interval_s must be in [0.5,10]")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("fixture source path must be absolute")
        self.timeout_s, self.max_age_s = float(timeout_s), float(max_age_s)
        self.min_interval_s, self.clock = float(min_interval_s), clock
        self._last_attempt: float | None = None
        self._last_sequence: int | None = None

    def read(self) -> PassiveRead:
        now = self.clock()
        if not _finite(now) or now < 0:
            raise ValueError("clock must return a nonnegative finite monotonic time")

        def no_events(status: str) -> PassiveRead:
            return PassiveRead(status, PerceptionSnapshot("mock", (), now))

        if self._last_attempt is not None:
            if now < self._last_attempt:
                self._last_attempt = now
                return no_events("clock_reset")
            if now - self._last_attempt < self.min_interval_s:
                return no_events("rate_limited")
        self._last_attempt = now
        try:
            with _connect_unix(self.path, self.timeout_s) as conn:
                frame = _strict_json(_recv_line(conn, self.timeout_s))
            received = self.clock()
            if not _finite(received) or received < now:
                return no_events("clock_reset")
            sequence, snap = _read_fixture_frame(
                frame, now=received, max_age_s=self.max_age_s)
            if self._last_sequence is not None and sequence <= self._last_sequence:
                return no_events("duplicate_or_out_of_order")
            self._last_sequence = sequence
            return PassiveRead("ok", snap, sequence)
        except (PassiveSourceError, OSError):
            return no_events("unavailable_or_invalid")


def probe_official_mediad(path: str | Path = OEM_SOCKET, *,
                          timeout_s: float = 1.) -> MediaProbe:
    """Check the OEM local media daemon via ONLY its documented hello request.

    The strict positive result additionally requires default path, expected
    daemon socket owner/peer uid, API 44 and exact pinned source revision.
    Custom paths (including fixture sockets) can NEVER claim official status.
    No "media.frame" request is issued and no camera data is handled.
    """
    _check_timeouts(timeout_s, 1.)
    p = Path(path)
    testing_path = str(p) != OEM_SOCKET
    try:
        with _connect_unix(p, timeout_s) as conn:
            uid = None
            if hasattr(socket, "SO_PEERCRED"):
                credentials = conn.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                _, uid, _ = struct.unpack("3i", credentials)
            msg = b'{"jsonrpc":"2.0","id":1,"method":"hello"}\n'
            conn.sendall(msg)
            frame = _strict_json(_recv_line(conn, timeout_s, max_bytes=2048))
        if (set(frame) != {"jsonrpc", "id", "result"}
                or frame.get("jsonrpc") != "2.0"
                or type(frame.get("id")) is not int or frame["id"] != 1):
            raise PassiveSourceError("unexpected hello response envelope")
        result = frame["result"]
        if (type(result) is not dict or
                set(result) != {"api_version", "daemon_version", "revision"}):
            raise PassiveSourceError("unexpected hello response schema")
        version = result["api_version"]
        revision = result["revision"]
        if type(version) is not int or type(revision) not in (str, type(None)):
            raise PassiveSourceError("invalid OEM identity values")
        # A semver from the OEM may legitimately be null.
        if result["daemon_version"] is not None and type(result["daemon_version"]) is not str:
            raise PassiveSourceError("invalid daemon version")
        actual_owner = p.lstat().st_uid
        if testing_path:
            expected_uid = None
        else:
            import pwd  # Unix-only: a Windows prototype may import this module.
            expected_uid = pwd.getpwnam(OEM_UID_NAME).pw_uid
        verified = (not testing_path and uid is not None
                    and uid == expected_uid and actual_owner == expected_uid
                    and version == OEM_API_VERSION
                    and revision == PINNED_OEM_REVISION)
        return MediaProbe(
            "verified_local_oem" if verified else "unverified_peer",
            version, uid, revision, verified,
        )
    except (PassiveSourceError, OSError, KeyError, struct.error) as exc:
        return MediaProbe("unavailable_or_invalid", None, None, None, False)
