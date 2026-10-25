"""Versioned perception boundary for simulated and, later, physical sensors.

A perception record is *not* proof that a real-world area is safe. Trusted
sources must be authenticated by the future adapter; this module only enforces
source policy, confidence, freshness and conservative conflict resolution.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomy import Scene

SCHEMA_VERSION = 1
SAFETY_CONFIDENCE = 0.90
DETECTION_CONFIDENCE = 0.80

_KINDS = frozenset({
    "safe_area", "floor_clear", "obstacle_m", "battery_pct",
    "person_visible", "object_label", "sound_label",
})
# Additive v1 observation kind. Sound labels are *categories*, never a
# transcript, biometric voiceprint, acoustic raw data or an emergency stop.
# No official sound classifier has been integrated with mediad yet.
_SOUND_CATEGORIES = frozenset({
    "unknown", "ambient", "knock", "bark", "meow", "speech",
    "keyword_microduck", "keyword_stop", "keyword_viens",
})
_SOURCES = frozenset({
    "operator", "robotd", "sensor", "simulator", "mock", "llm_suggestion",
})
_TRUSTED = {
    "mock": {
        kind: frozenset({"mock"}) for kind in _KINDS
    },
    "simulator": {
        "safe_area": frozenset({"operator", "simulator"}),
        "floor_clear": frozenset({"simulator"}),
        "obstacle_m": frozenset({"simulator"}),
        "battery_pct": frozenset({"simulator", "robotd"}),
        "person_visible": frozenset({"simulator"}),
        "object_label": frozenset({"simulator"}),
        "sound_label": frozenset({"simulator"}),
    },
    "robot": {
        "safe_area": frozenset({"operator"}),
        "floor_clear": frozenset({"sensor"}),
        "obstacle_m": frozenset({"sensor"}),
        "battery_pct": frozenset({"robotd"}),
        "person_visible": frozenset({"sensor"}),
        "object_label": frozenset({"sensor"}),
        "sound_label": frozenset({"sensor"}),
    },
}


def _finite_number(value: object) -> bool:
    return (isinstance(value, (float, int))
            and not isinstance(value, bool) and math.isfinite(value))


@dataclass(frozen=True)
class PerceptionEvent:
    """One observation; timestamps are from time.monotonic(), not wall clock.

    track_id is required for object_label and is an ephemeral tracking ID,
    not a human identity. Values from a LLM are never trusted as sensor data.
    """

    kind: str
    value: bool | float | str
    source: str
    observed_at: float
    ttl_s: float
    confidence: float
    track_id: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported perception schema version")
        if self.kind not in _KINDS:
            raise ValueError("unsupported perception kind")
        if self.source not in _SOURCES:
            raise ValueError("unsupported perception source")
        if not _finite_number(self.observed_at) or self.observed_at < 0:
            raise ValueError("observed_at must be a finite monotonic timestamp")
        if not _finite_number(self.ttl_s) or self.ttl_s <= 0:
            raise ValueError("ttl_s must be a finite positive duration")
        # Limiting age is a software guard, not a claim of physical safety.
        max_ttl_s = 60.0 if self.kind == "safe_area" else 5.0
        if self.ttl_s > max_ttl_s:
            raise ValueError("perception TTL exceeds permitted limit")
        if not _finite_number(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be finite in [0, 1]")
        if self.kind in {"safe_area", "floor_clear", "person_visible"}:
            if type(self.value) is not bool:
                raise ValueError("expected a boolean observation")
        elif self.kind in {"obstacle_m", "battery_pct"}:
            if not _finite_number(self.value):
                raise ValueError("expected a finite numeric observation")
            if self.value < 0 or (self.kind == "battery_pct" and self.value > 100):
                raise ValueError("numeric observation out of range")
        elif self.kind == "object_label":
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValueError("object_label needs a nonempty label")
            if not isinstance(self.track_id, str) or not self.track_id.strip():
                raise ValueError("object_label needs a nonempty track_id")
        elif self.kind == "sound_label":
            if type(self.value) is not str or self.value not in _SOUND_CATEGORIES:
                raise ValueError("sound_label must be a non-transcript category")
        if self.kind != "object_label" and self.track_id is not None:
            raise ValueError("track_id belongs only to object_label")

    def fresh_at(self, now: float) -> bool:
        """Future observations are ignored, not treated as fresh."""
        age = now - self.observed_at
        return 0 <= age <= self.ttl_s


@dataclass(frozen=True)
class PerceptionSnapshot:
    """One collection of observations from a declared execution environment."""

    environment: str
    events: tuple[PerceptionEvent, ...]
    observed_at: float
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported snapshot schema version")
        if self.environment not in _TRUSTED:
            raise ValueError("unknown execution environment")
        if not _finite_number(self.observed_at) or self.observed_at < 0:
            raise ValueError("snapshot time must be finite and nonnegative")
        if not isinstance(self.events, tuple) or not all(
            isinstance(e, PerceptionEvent) for e in self.events
        ):
            raise TypeError("events must be a tuple of PerceptionEvent")
        if any(e.observed_at > self.observed_at for e in self.events):
            raise ValueError("event timestamp is later than snapshot")

    def to_scene(self, now: float | None = None) -> Scene:
        """Convert to legacy Scene; missing or untrusted safety data halts.

        Robot safety data from an LLM, mock source or simulator is discarded.
        Any conflicting or low-confidence trusted safety reading fails closed.
        """
        from .autonomy import Scene

        if now is None:
            now = time.monotonic()
        if not _finite_number(now) or now < 0:
            raise ValueError("now must be a finite monotonic timestamp")
        if now < self.observed_at:
            return Scene()

        def readings(kind: str) -> list[PerceptionEvent]:
            sources = _TRUSTED[self.environment][kind]
            return [
                e for e in self.events
                if e.kind == kind and e.source in sources and e.fresh_at(now)
            ]

        def sure_true(kind: str) -> bool:
            data = readings(kind)
            return bool(data) and all(
                e.value is True and e.confidence >= SAFETY_CONFIDENCE
                for e in data
            )

        distances = readings("obstacle_m")
        batteries = readings("battery_pct")
        # Unknown distance/battery always prevents movement. Requiring every
        # trusted reading to meet confidence also resolves contradictions safely.
        obstacle_ok = bool(distances) and all(
            e.confidence >= SAFETY_CONFIDENCE for e in distances
        )
        battery_ok = bool(batteries) and all(
            e.confidence >= SAFETY_CONFIDENCE for e in batteries
        )
        area_ok = sure_true("safe_area")
        floor_ok = sure_true("floor_clear")

        persons = readings("person_visible")
        person_visible = bool(persons) and all(
            e.value is True and e.confidence >= DETECTION_CONFIDENCE
            for e in persons
        )
        objects = [
            e for e in readings("object_label")
            if e.confidence >= DETECTION_CONFIDENCE
        ]
        # Only one tracked object currently fits the legacy Scene contract.
        obj = max(objects, key=lambda e: e.observed_at) if objects else None
        # Disagreeing labels on the same track must not promote one guess to
        # an established category or authorize a play action.
        object_label = "unknown"
        if obj is not None:
            labels = {e.value for e in objects if e.track_id == obj.track_id}
            if len(labels) == 1:
                object_label = obj.value
        return Scene(
            safe_area=area_ok,
            floor_clear=floor_ok,
            perception_valid=obstacle_ok and battery_ok,
            battery_pct=min(e.value for e in batteries) if battery_ok else 100.0,
            obstacle_m=min(e.value for e in distances) if obstacle_ok else None,
            person_visible=person_visible,
            object_id=obj.track_id if obj else None,
            object_label=object_label,
            object_source=obj.source if obj else "sensor",
            environment=self.environment,
            pc_connected=False,  # PC connectivity is never inferred from vision.
        )
