"""R1: metadata-only fixture bridge over EXISTING Microduck validators.

No sockets, decoder, image pixels, microphone PCM, camera capture, motors,
SQLite writes, model, WebRTC session or PC access.  Media notifications use
the OEM WebRTC *shape*, NOT the local mediad Unix socket. Audio cues are
synthetic only. The official ToF geometry cannot prove traversable floor.

This module intentionally does NOT create PerceptionEvent(sensor, ...).
Its output can be offered to the existing F2 brain only as a non-ok,
empty mock PassiveRead: OEM-looking data is not authenticated sensing.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .oem_frame_preflight import (
    FrameContractError, parse_mock_frame_header,
)
from .passive_media_router import (
    MockAudioCueRouter, PassiveMediaError, parse_oem_shape_notification,
)
from .passive_sources import MAX_FRAME_AGE_S, PassiveRead
from .perception import PerceptionSnapshot
from .sim_ipc import Notification, TelemetryError, parse_depth

LANES = frozenset({
    "webrtc_metadata_fixture",
    "media_frame_header_fixture",
    "tof_notification_fixture",
    "audio_cue_fixture",
})

# We never keep raw ToF samples, box coordinates, audio cues or image data.
_ALLOWED_TOF_FIELDS = frozenset({
    "seq", "rows", "cols", "distance_mm", "status", "t_ns",
})


def _clock(now: float) -> float:
    if type(now) not in (float, int) or not math.isfinite(now) or now < 0:
        raise ValueError("a finite nonnegative local monotonic time is required")
    return float(now)


@dataclass(frozen=True, slots=True)
class OEMFixtureMetadata:
    """Sanitized fixture receipt, not an OEM sensor identity/capability proof."""

    lane: str
    status: str
    received_monotonic_s: float
    timestamp_basis: str = "none"
    sample_age_s: float | None = None
    metadata_bytes: int = 0
    advertised_media_bytes: int | None = None
    duck_box_count: int = 0
    tof_zone_count: int = 0
    sequence: int | None = None
    detector_reported_ms: float | None = None
    category: str = "unknown"
    source_authenticated: bool = False
    motion_authorized: bool = False
    motor_commands_issued: int = 0
    raw_media_stored_bytes: int = 0
    pc_requests_issued: int = 0

    def __post_init__(self) -> None:
        # A direct caller must not forge a 'sensor verified' report by
        # constructing this dataclass with elevated flags.
        statuses = {
            "webrtc_metadata_fixture": {
                "unavailable", "invalid_fixture", "metadata_unverified",
                "duck_candidates_unverified", "no_candidate_boxes",
            },
            "media_frame_header_fixture": {
                "unavailable", "invalid_fixture", "header_unverified",
                "stale_or_future",
            },
            "tof_notification_fixture": {
                "unavailable", "invalid_fixture", "depth_shape_unverified",
                "stale_or_future", "duplicate_or_out_of_order", "clock_reset",
            },
            "audio_cue_fixture": {
                "unavailable", "invalid_fixture", "fixture_hypothesis_only",
                "stale_or_future", "duplicate_or_out_of_order",
                "clock_regression", "rate_limited",
            },
        }
        if self.lane not in LANES or self.status not in statuses[self.lane]:
            raise ValueError("unsupported OEM fixture state")
        _clock(self.received_monotonic_s)
        if (self.source_authenticated or self.motion_authorized
                or self.motor_commands_issued != 0
                or self.raw_media_stored_bytes != 0
                or self.pc_requests_issued != 0
                or self.category != "unknown"):
            raise ValueError("fixture cannot promote source, identity or actions")
        if (type(self.metadata_bytes) is not int
                or not 0 <= self.metadata_bytes <= 4096):
            raise ValueError("invalid metadata byte budget")
        if self.advertised_media_bytes is not None and (
                type(self.advertised_media_bytes) is not int
                or not 0 <= self.advertised_media_bytes <= 4*1024*1024):
            raise ValueError("invalid advertised byte count")
        if (type(self.duck_box_count) is not int
                or not 0 <= self.duck_box_count <= 32
                or type(self.tof_zone_count) is not int
                or self.tof_zone_count not in (0, 64)):
            raise ValueError("invalid fixture counts")
        if self.sequence is not None and (
                type(self.sequence) is not int
                or not 0 <= self.sequence < 2**63):
            raise ValueError("invalid fixture sequence")
        for val in (self.sample_age_s, self.detector_reported_ms):
            if val is not None and (
                    type(val) not in (int, float)
                    or not math.isfinite(val) or val < 0):
                raise ValueError("invalid fixture timing")
        if (self.sample_age_s is not None
                and self.sample_age_s > MAX_FRAME_AGE_S):
            raise ValueError("fixture age exceeds maximum")
        bases = {
            "none", "capture_time_unverified", "unverified_wall_clock",
            "local_fixture_receipt_monotonic", "synthetic_monotonic_checked",
        }
        if self.timestamp_basis not in bases:
            raise ValueError("unsupported timestamp provenance")
        if (self.lane != "webrtc_metadata_fixture"
                and (self.duck_box_count or self.detector_reported_ms is not None)):
            raise ValueError("duck detections only belong to WebRTC metadata")
        if self.lane != "tof_notification_fixture" and self.tof_zone_count:
            raise ValueError("ToF count belongs only to a ToF fixture")
        if (self.lane != "media_frame_header_fixture"
                and self.advertised_media_bytes is not None):
            raise ValueError("frame byte count belongs only to media.frame")

    def to_passive_read(self) -> PassiveRead:
        """Reuse F1/F2 boundaries; metadata can NEVER become an 'ok' sensor read.

        No persisted identity or historical category comes from this method.
        In particular, a duck detection is NOT a verified duck identity, a
        petting sound is NOT a cat/dog classification, and a depth grid is
        NOT safe_area/floor_clear.
        """
        status = ("unavailable_or_invalid" if self.status in {
            "unavailable", "invalid_fixture", "stale_or_future",
            "duplicate_or_out_of_order", "clock_reset", "rate_limited",
            "clock_regression",
        } else "metadata_only_unverified")
        return PassiveRead(
            status=status,
            snapshot=PerceptionSnapshot(
                environment="mock", events=(),
                observed_at=self.received_monotonic_s),
            sequence=None,
            channel="oem_fixture_metadata_only",
        )


class OEMFixtureInspector:
    """A small facade reusing F3-C, F3-E, F3-C audio and sim_ipc validators.

    Does not own a transport. The caller supplies **fictional** bytes or
    an in-memory Notification. No OEM source is 'verified' by this class.
    """

    def __init__(self) -> None:
        self._audio = MockAudioCueRouter()
        self._last_tof_seq: int | None = None
        self._last_tof_received_s: float | None = None

    @staticmethod
    def unavailable(lane: str, *, now_monotonic_s: float) -> OEMFixtureMetadata:
        now = _clock(now_monotonic_s)
        if lane not in LANES:
            raise ValueError("unknown fixture lane")
        return OEMFixtureMetadata(lane, "unavailable", now)

    @staticmethod
    def web_metadata(
        raw: bytes, *, now_monotonic_s: float,
    ) -> OEMFixtureMetadata:
        """OEM WebRTC *notification-shape*, never a mediad Unix subscription.

        Unlike media.frame's wall timestamp, the sanitized WebRTC parser
        doesn't export validated sample clocks. Arrival time is not capture
        time, so no freshness is implied by this method.
        """
        now = _clock(now_monotonic_s)
        lane = "webrtc_metadata_fixture"
        try:
            parsed = parse_oem_shape_notification(raw)
        except (PassiveMediaError, ValueError, TypeError):
            return OEMFixtureMetadata(lane, "invalid_fixture", now)
        return OEMFixtureMetadata(
            lane, parsed.status, now,
            timestamp_basis="capture_time_unverified",
            metadata_bytes=len(raw),
            duck_box_count=parsed.reported_boxes,
            detector_reported_ms=parsed.reported_inference_ms,
        )

    @staticmethod
    def frame_header(
        raw: bytes, *, now_unix_us: int, now_monotonic_s: float,
    ) -> OEMFixtureMetadata:
        """Only metadata from OEM media.frame, NEVER request or read the tail."""
        now = _clock(now_monotonic_s)
        lane = "media_frame_header_fixture"
        try:
            parsed = parse_mock_frame_header(raw, now_unix_us=now_unix_us)
        except (FrameContractError, ValueError, TypeError):
            return OEMFixtureMetadata(lane, "invalid_fixture", now)
        # The existing preflight tolerates 100ms of future wall-clock skew.
        # Do not describe a slightly future fixture as fresh.
        status = "header_unverified" if parsed.age_us >= 0 else "stale_or_future"
        return OEMFixtureMetadata(
            lane, status, now,
            timestamp_basis="unverified_wall_clock",
            sample_age_s=max(0., parsed.age_us / 1_000_000)
            if parsed.age_us >= 0 else None,
            metadata_bytes=len(raw),
            advertised_media_bytes=parsed.expected_bytes,
        )

    def depth(
        self, fixture: Notification, *, now_monotonic_s: float,
    ) -> OEMFixtureMetadata:
        """Reuse existing parse_depth, drop the 64 raw zones before returning.

        received_at is the fixture's LOCAL monotonic receipt time, not the
        sensor's independently authenticated timestamp. Only the 8x8 shape
        is checked. No step/floor/obstacle inference.
        """
        now = _clock(now_monotonic_s)
        lane = "tof_notification_fixture"
        if (type(fixture) is not Notification or
                type(fixture.params) is not dict or
                set(fixture.params) - _ALLOWED_TOF_FIELDS):
            return OEMFixtureMetadata(lane, "invalid_fixture", now)
        try:
            parsed = parse_depth(fixture)
        except (TelemetryError, ValueError, TypeError):
            return OEMFixtureMetadata(lane, "invalid_fixture", now)
        if (type(parsed.seq) is not int or parsed.seq >= 2**63
                or type(parsed.received_at) not in (float, int)
                or not math.isfinite(parsed.received_at)
                or parsed.received_at < 0):
            return OEMFixtureMetadata(lane, "invalid_fixture", now)
        age = now - parsed.received_at
        if (self._last_tof_received_s is not None
                and now < self._last_tof_received_s):
            # A clock jump invalidates the current observation. A new
            # frame may be considered on a *later* call.
            self._last_tof_seq = None
            self._last_tof_received_s = now
            return OEMFixtureMetadata(lane, "clock_reset", now)
        if self._last_tof_seq is not None and parsed.seq <= self._last_tof_seq:
            return OEMFixtureMetadata(lane, "duplicate_or_out_of_order", now)
        if not 0 <= age <= MAX_FRAME_AGE_S:
            return OEMFixtureMetadata(lane, "stale_or_future", now)
        self._last_tof_seq = parsed.seq
        self._last_tof_received_s = now
        return OEMFixtureMetadata(
            lane, "depth_shape_unverified", now,
            timestamp_basis="local_fixture_receipt_monotonic",
            sample_age_s=float(age),
            tof_zone_count=len(parsed.distance_mm),
            sequence=parsed.seq,
        )

    def audio(
        self, raw: bytes, *, now_monotonic_s: float,
    ) -> OEMFixtureMetadata:
        """A SYNTHETIC sound cue, never OEM microphone or keyword recognition."""
        now = _clock(now_monotonic_s)
        lane = "audio_cue_fixture"
        try:
            parsed = self._audio.route(raw, now_monotonic_s=now)
        except (PassiveMediaError, ValueError, TypeError):
            return OEMFixtureMetadata(lane, "invalid_fixture", now)
        return OEMFixtureMetadata(
            lane, parsed.status, now,
            timestamp_basis="synthetic_monotonic_checked"
            if parsed.status == "fixture_hypothesis_only" else "none",
            metadata_bytes=len(raw), sequence=parsed.sequence,
        )
