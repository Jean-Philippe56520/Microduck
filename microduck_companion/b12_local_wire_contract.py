"""P15-B13: B12 OEM local detection wire format, HOST-ONLY pure fixture gate.

The packaged P15-B6 24-file DEV rootfs must stay byte-for-byte pinned.
This separate unshipped module only decodes a B12-shaped notification.
Not a mediad subscriber, real sensor authenticator, memory writer or motor
adapter. A Unix fixture can exercise it without creating a second pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from .passive_media_router import (
    MAX_NOTIFICATION_BYTES, PassiveMediaError, _parse,
    parse_oem_shape_notification,
)

@dataclass(frozen=True)
class B12LocalMetadata:
    """Strict B12 local wire shape; never proof of an authenticated sensor.

    A captured_at_* value is an OS/appsink clock claim, NOT actual exposure
    time. A raw one-class box is NOT a recognized object or confidence.
    """

    status: str
    reported_boxes: int
    look_seq: int
    captured_at_monotonic_ns: int
    captured_at_unix_us: int
    raw_score_max: float | None
    category: str = "unknown"
    provenance: str = "untrusted_b12_local_wire_fixture"
    verified_sensor: bool = False
    motor_commands_issued: int = 0
    media_bytes_stored: int = 0


# The P15-B12 producer adds exactly these three fields to the existing
# media.detections payload. The legacy WebRTC shape parser intentionally
# remains strict and does not accept them.
B12_CAPTURE_MAX_AGE_NS = 2_000_000_000
_B12_PARAMS = frozenset({
    "width", "height", "took_ms", "boxes",
    "captured_at_monotonic_ns", "captured_at_unix_us", "look_seq",
})


def parse_b12_local_shape_notification(
    raw: bytes, *, now_monotonic_ns: int,
) -> B12LocalMetadata:
    """Validate P15-B12 local shape, clocks and freshness, but NOT its sender.

    Only a future separately reviewed Unix/peer/ACL adapter can authenticate
    the producer. This parser must not emit PerceptionEvent or persist SQLite.
    """
    if (type(now_monotonic_ns) is not int
            or not 0 < now_monotonic_ns < 2**64):
        raise PassiveMediaError("invalid consumer monotonic clock")
    data = _parse(raw, MAX_NOTIFICATION_BYTES)
    if (set(data) != {"jsonrpc", "method", "params"}
            or data["jsonrpc"] != "2.0"
            or data["method"] != "media.detections"
            or type(data["params"]) is not dict):
        raise PassiveMediaError("not a B12 local detection notification")
    params = data["params"]
    if set(params) != _B12_PARAMS:
        raise PassiveMediaError("B12 local fields missing or unexpected")
    stamp = params["captured_at_monotonic_ns"]
    unix = params["captured_at_unix_us"]
    seq = params["look_seq"]
    if any(type(x) is not int or not 0 < x < 2**64
           for x in (stamp, unix, seq)):
        raise PassiveMediaError("invalid B12 capture clock or look sequence")
    if not 0 <= now_monotonic_ns - stamp <= B12_CAPTURE_MAX_AGE_NS:
        raise PassiveMediaError("B12 capture timestamp stale or future")

    # Reuse the existing *strict* OEM box/score/size/latency checks verbatim.
    # Never interpret raw scores as [0,1] probabilities, categories or safety.
    original = {
        "jsonrpc": "2.0", "method": "media.detections",
        "params": {key: params[key] for key in (
            "width", "height", "took_ms", "boxes"
        )},
    }
    shape = parse_oem_shape_notification(
        json.dumps(original, separators=(",", ":"), allow_nan=False).encode("utf-8")
    )
    return B12LocalMetadata(
        status="b12_shape_unverified" if shape.reported_boxes
               else "b12_empty_look_unverified",
        reported_boxes=shape.reported_boxes,
        look_seq=seq,
        captured_at_monotonic_ns=stamp,
        captured_at_unix_us=unix,
        raw_score_max=shape.raw_score_max,
    )



class B12LocalSequenceGate:
    """Bounded in-process duplicate/clock-regression filter for host fixtures.

    Only an authenticated live reader (separate review) may use a similar
    sequence guard to gate OEM observations. No sensor identity is inferred.
    """

    def __init__(self) -> None:
        self._last_seq: int | None = None
        self._last_capture_ns: int | None = None

    def accept(self, item: B12LocalMetadata) -> bool:
        if not isinstance(item, B12LocalMetadata):
            raise TypeError("expected B12LocalMetadata")
        if (self._last_seq is not None and item.look_seq <= self._last_seq
                or self._last_capture_ns is not None
                and item.captured_at_monotonic_ns < self._last_capture_ns):
            return False
        self._last_seq = item.look_seq
        self._last_capture_ns = item.captured_at_monotonic_ns
        return True
