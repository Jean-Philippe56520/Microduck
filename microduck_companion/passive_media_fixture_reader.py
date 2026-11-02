"""P15-B5: one bounded read of P15-B4-shaped Unix metadata, FIXTURE ONLY.

This is a sidecar diagnostic of the existing Kwipi P15-B1 mock lifecycle,
not a second cognition/perception pipeline. Never requests media.frame,
sends an RPC, reads the camera, touches SQLite or grants motor permission.

An OEM-looking JSON object from a temporary Unix server is never proof of
mediad, a physical sensor, image freshness, identity or a real-world class.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time
from typing import Callable

from .passive_media_router import (
    MAX_NOTIFICATION_BYTES,
    PassiveMediaError,
    parse_oem_shape_notification, parse_b12_local_shape_notification,
)
from .passive_sources import PassiveSourceError, _connect_unix, _recv_line

MAX_READ_S = 0.4
MIN_INTERVAL_S = 0.5
_FORBIDDEN = tuple(Path(name) for name in ("/run", "/dev", "/proc", "/sys"))


@dataclass(frozen=True)
class MediaFixtureRead:
    """Only a diagnostic receipt, no cognitive, physical or motor authority."""

    status: str
    reported_boxes: int = 0
    category: str = "unknown"
    provenance: str = "untrusted_oem_shape_unix_fixture_only"
    physical_sensor_verified: bool = False
    fresh_capture_verified: bool = False
    motor_commands_issued: int = 0
    memory_writes: int = 0
    camera_frames_requested: int = 0

    @property
    def notification_valid_shape_only(self) -> bool:
        return self.status in {"shape_only_untrusted", "empty_look_untrusted"}


def validate_media_fixture_path(path: Path) -> None:
    """Refuse OEM/kernel paths and symlinked components BEFORE any connection.

    No actual /run/mediad source is supported here, even with a valid JSON.
    A separate P15 OEM authorization/revision/ACL review is still required.
    """
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("media fixture path must be absolute")
    resolved = path.resolve(strict=False)
    if any(resolved == root or root in resolved.parents for root in _FORBIDDEN):
        raise ValueError("OEM/kernel media endpoint forbidden in fixture mode")
    if any(candidate.is_symlink() for candidate in (path, *path.parents)):
        raise ValueError("media fixture path must have no symlink component")


class MediaFixtureReader:
    """One connection and one bounded OEM-shaped notification per attempt.

    0.5 s min interval prevents a second media poll within the same budget.
    A new connection never replays the previous look. The legacy OEM-shaped
    fixture has no sequence or capture time. The explicitly opted-in P15-B12
    fixture tests those fields without authenticating a physical sensor.
    """

    def __init__(
        self,
        path: Path,
        *,
        timeout_s: float = MAX_READ_S,
        clock: Callable[[], float] = time.monotonic,
        b12_local_shape: bool = False,
    ) -> None:
        validate_media_fixture_path(path)
        if type(b12_local_shape) is not bool:
            raise TypeError("b12_local_shape must be an explicit boolean")
        if (type(timeout_s) not in (int, float)
                or not math.isfinite(timeout_s)
                or not .05 <= timeout_s <= MAX_READ_S):
            raise ValueError("media fixture timeout outside bounded budget")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.path = path
        self.timeout_s = float(timeout_s)
        self._clock = clock
        self._last_attempt: float | None = None
        self._last_b12_sequence: int | None = None
        self._b12_local_shape = b12_local_shape

    def read(self) -> MediaFixtureRead:
        try:
            now = self._clock()
        except Exception:
            return MediaFixtureRead("clock_unavailable")
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            return MediaFixtureRead("clock_unavailable")
        if self._last_attempt is not None:
            if now < self._last_attempt:
                self._last_attempt = float(now)
                return MediaFixtureRead("clock_reset")
            if now - self._last_attempt < MIN_INTERVAL_S:
                return MediaFixtureRead("rate_limited")
        self._last_attempt = float(now)
        try:
            # Check each time: no late switch to a symlinked OEM endpoint.
            validate_media_fixture_path(self.path)
            deadline = time.monotonic() + self.timeout_s
            with _connect_unix(self.path, self.timeout_s) as conn:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return MediaFixtureRead("unavailable_or_invalid")
                raw = _recv_line(
                    conn, remaining, max_bytes=MAX_NOTIFICATION_BYTES,
                )
            if self._b12_local_shape:
                received = self._clock()
                if (type(received) not in (int, float)
                        or not math.isfinite(received) or received < now):
                    return MediaFixtureRead("clock_reset")
                decoded = parse_b12_local_shape_notification(
                    raw, now_monotonic_ns=int(received * 1_000_000_000))
                if (self._last_b12_sequence is not None
                        and decoded.look_seq <= self._last_b12_sequence):
                    return MediaFixtureRead("duplicate_or_out_of_order")
                self._last_b12_sequence = decoded.look_seq
            else:
                decoded = parse_oem_shape_notification(raw)
                if decoded.method != "media.detections":
                    return MediaFixtureRead("unavailable_or_invalid")
            if decoded.category != "unknown" or decoded.verified_sensor:
                return MediaFixtureRead("unavailable_or_invalid")
            if decoded.reported_boxes:
                return MediaFixtureRead("shape_only_untrusted", decoded.reported_boxes)
            return MediaFixtureRead("empty_look_untrusted")
        except (OSError, PassiveMediaError, PassiveSourceError, ValueError):
            return MediaFixtureRead("unavailable_or_invalid")
