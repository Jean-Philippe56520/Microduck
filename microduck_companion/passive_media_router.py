"""F3-C: conservative, metadata-only parsing of pinned OEM-shaped notifications.

This is NOT a live mediad subscription or verified robot sensor. In the
pinned 942e58e source, `media.video` and `media.detections` are WebRTC
control-channel notifications. The LOCAL /run/mediad/media.sock provides
only hello and media.frame, the latter a binary camera capture. Do not
pretend the local socket publishes detection events, or read raw frames.

One-class duck boxes are NOT cat/dog/person detections. Raw OEM detector
scores may exceed 1, so they are NOT treated as calibrated confidences.
No actuator calls, source promotion, images, audio, identities or network.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .passive_sources import PassiveSourceError, _strict_json

MAX_NOTIFICATION_BYTES = 4096
MAX_SOUND_FIXTURE_BYTES = 1024
MAX_BOXES = 32
MAX_SIDE = 4096
MAX_LATENCY_MS = 5000.
MAX_SOUND_AGE_S = 2.
MIN_SOUND_INTERVAL_S = .5
OEM_REVISION_REVIEWED = "942e58e3aa6dbb28e7037203fff11866122c7567"
OEM_NOTIFICATION_METHODS = frozenset({"media.video", "media.detections"})
# These are *fixture names*, not a working microphone classifier.
MOCK_AUDIO_CUES = frozenset({
    "petting_start", "petting_end", "ambient_change",
    "keyword_microduck", "keyword_stop", "keyword_viens",
})


class PassiveMediaError(ValueError):
    """Malformed, unsupported or over-budget metadata; never upgrade trust."""


@dataclass(frozen=True)
class MediaMetadata:
    """What a fixture claims; an OEM-looking JSON is NOT authenticated."""

    status: str
    method: str
    width: int
    height: int
    rotate: int | None
    reported_boxes: int
    raw_score_max: float | None
    reported_inference_ms: float | None
    intrinsics_source: str | None
    category: str = "unknown"
    channel: str = "oem_notification_shape_unverified"
    verified_sensor: bool = False
    motor_commands_issued: int = 0
    media_bytes_stored: int = 0


@dataclass(frozen=True)
class MockAudioCue:
    """Only a synthetic label, never genuine speech/petting recognition."""

    status: str
    cue: str | None
    sequence: int | None
    category: str = "unknown"
    channel: str = "mock_audio_fixture_only"
    verified_microphone: bool = False
    stops_robot: bool = False
    motor_commands_issued: int = 0
    audio_bytes_stored: int = 0


def _parse(raw: bytes, limit: int) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > limit or b"\n" in raw:
        raise PassiveMediaError("invalid/bulk notification payload")
    try:
        data = _strict_json(raw)
    except (PassiveSourceError, ValueError, TypeError) as exc:
        raise PassiveMediaError("malformed JSON metadata") from exc
    if not isinstance(data, dict):
        raise PassiveMediaError("notification must be an object")
    return data


def _number(value: object, *, low: float = 0., high: float = MAX_LATENCY_MS) -> float:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not low <= value <= high):
        raise PassiveMediaError("invalid or out-of-bounds numeric metadata")
    return float(value)


def _size(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_SIDE:
        raise PassiveMediaError("invalid image dimensions")
    return value


def _intrinsics(value: object, width: int, height: int) -> str:
    if type(value) is not dict:
        raise PassiveMediaError("camera intrinsics must be an object")
    required = {"fx", "fy", "cx", "cy", "calibrated", "source"}
    if not required <= set(value) or set(value) - required - {"distortion"}:
        raise PassiveMediaError("unsupported intrinsics fields")
    for name in ("fx", "fy"):
        _number(value[name], low=.001, high=100000.)
    for name, bound in (("cx", width), ("cy", height)):
        _number(value[name], high=float(bound))
    if type(value["calibrated"]) is not bool:
        raise PassiveMediaError("invalid calibrated claim")
    if type(value["source"]) is not str or value["source"] not in (
        "robot", "family", "nominal", "sim"
    ):
        raise PassiveMediaError("unknown calibration source")
    distortion = value.get("distortion", [])
    if (type(distortion) is not list or len(distortion) not in (0, 5)):
        raise PassiveMediaError("invalid distortion shape")
    for coeff in distortion:
        _number(coeff, low=-100., high=100.)
    return value["source"]


def parse_oem_shape_notification(raw: bytes) -> MediaMetadata:
    """Parse ONLY pinned OEM-shaped untrusted WebRTC notification *fixtures*.

    The caller MUST NOT label the result as authentic mediad input; neither
    a JSON string nor an independent hello probe proves WebRTC origin.
    """
    data = _parse(raw, MAX_NOTIFICATION_BYTES)
    if (set(data) != {"jsonrpc", "method", "params"}
            or data["jsonrpc"] != "2.0"
            or type(data["method"]) is not str
            or data["method"] not in OEM_NOTIFICATION_METHODS
            or type(data["params"]) is not dict):
        raise PassiveMediaError("unsupported notification/method/envelope")
    method = data["method"]
    p = data["params"]
    if method == "media.video":
        required = {"width", "height", "rotate", "mono_ns", "real_ns"}
        if not required <= set(p) or set(p) - required - {"intrinsics"}:
            raise PassiveMediaError("unexpected media.video metadata")
        w, h = _size(p["width"]), _size(p["height"])
        if type(p["rotate"]) is not int or p["rotate"] not in (0,90,180,270):
            raise PassiveMediaError("invalid rotation")
        for k in ("mono_ns", "real_ns"):
            if type(p[k]) is not int or not 0 <= p[k] < 2**64:
                raise PassiveMediaError("invalid OEM clock field")
        source = _intrinsics(p["intrinsics"], w, h) if "intrinsics" in p else None
        return MediaMetadata(
            "metadata_unverified", method, w, h, p["rotate"], 0, None,
            None, source)
    if set(p) != {"width", "height", "took_ms", "boxes"}:
        raise PassiveMediaError("unexpected media.detections metadata")
    w, h = _size(p["width"]), _size(p["height"])
    took_ms = _number(p["took_ms"])
    boxes = p["boxes"]
    if type(boxes) is not list or len(boxes) > MAX_BOXES:
        raise PassiveMediaError("too many/invalid duck boxes")
    max_score: float | None = None
    for box in boxes:
        if type(box) is not dict or set(box) != {
            "x0", "y0", "x1", "y1", "score"
        }:
            raise PassiveMediaError("unknown detection fields")
        x0 = _number(box["x0"], high=float(w))
        x1 = _number(box["x1"], high=float(w))
        y0 = _number(box["y0"], high=float(h))
        y1 = _number(box["y1"], high=float(h))
        if not x0 < x1 or not y0 < y1:
            raise PassiveMediaError("invalid detection rectangle")
        # OEM's example has score=1.38. It is NOT a [0,1] confidence.
        score = _number(box["score"], high=100.)
        max_score = max(score, max_score if max_score is not None else score)
    return MediaMetadata(
        "duck_candidates_unverified" if boxes else "no_candidate_boxes",
        method, w, h, None, len(boxes), max_score, took_ms, None)


class MockAudioCueRouter:
    """Only fixture metadata. No mic, no KWS model and NO emergency stop.

    Sequence and monotonic freshness are scoped to this process, not proof
    of sensor provenance or durable clock continuity after reboot.
    """

    def __init__(self) -> None:
        self._previous_sequence: int | None = None
        self._previous_sample_s: float | None = None

    def route(self, raw: bytes, *, now_monotonic_s: float) -> MockAudioCue:
        if (type(now_monotonic_s) not in (int, float)
                or not math.isfinite(now_monotonic_s)
                or now_monotonic_s < 0):
            raise ValueError("invalid monotonic clock")
        data = _parse(raw, MAX_SOUND_FIXTURE_BYTES)
        if set(data) != {"schema_version", "sequence", "sample_monotonic_s", "cue"}:
            raise PassiveMediaError("unsupported audio mock schema")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise PassiveMediaError("unsupported audio mock version")
        seq = data["sequence"]
        sample = data["sample_monotonic_s"]
        cue = data["cue"]
        if type(seq) is not int or not 0 <= seq < 2**63:
            raise PassiveMediaError("invalid audio sequence")
        if type(cue) is not str or cue not in MOCK_AUDIO_CUES:
            raise PassiveMediaError("unsupported/untrained audio cue")
        if (type(sample) not in (int, float) or not math.isfinite(sample)
                or sample < 0):
            raise PassiveMediaError("invalid sample time")
        if (self._previous_sequence is not None
                and seq <= self._previous_sequence):
            return MockAudioCue("duplicate_or_out_of_order", None, None)
        if self._previous_sample_s is not None and sample < self._previous_sample_s:
            return MockAudioCue("clock_regression", None, None)
        if not 0 <= now_monotonic_s - sample <= MAX_SOUND_AGE_S:
            return MockAudioCue("stale_or_future", None, None)
        if (self._previous_sample_s is not None
                and sample - self._previous_sample_s < MIN_SOUND_INTERVAL_S):
            return MockAudioCue("rate_limited", None, None)
        self._previous_sequence = seq
        self._previous_sample_s = float(sample)
        return MockAudioCue("fixture_hypothesis_only", cue, seq)
