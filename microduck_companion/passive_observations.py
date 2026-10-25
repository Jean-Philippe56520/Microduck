"""F1-A: deterministic, strictly passive category projection for v1 events.

Only a label and declared provenance leave this boundary; camera/audio bytes
and transcripts never enter it. A string "sensor" is a *claim*, not proof of
authenticated mediad access. No motor control, durable memory or ML inference.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .perception import (
    DETECTION_CONFIDENCE, PerceptionSnapshot, _TRUSTED,
)

MAX_EVENTS = 64
# Categories only. Personal names, arbitrary speech and model prose cannot be
# promoted to recognized identities by this first, synthetic-only contract.
OBJECT_CATEGORIES = frozenset({
    "unknown", "ball", "toy", "dog", "cat", "person", "microduck",
    "other_object",
})
PASSIVE_KINDS = frozenset({"object_label", "sound_label"})


@dataclass(frozen=True)
class PassiveObservation:
    """Describes a non-motor category, not a verified identity or physical act.

    status: identified | unknown | conflict | low_confidence | stale |
            future | untrusted. Only identified carries a non-unknown
    category. `claimed_source` has not been authenticated by this projector;
    later F1-B adapters must establish transport/source provenance.
    """

    kind: str
    category: str
    status: str
    claimed_source: str
    confidence: float
    observed_at: float
    track_id: str | None

    @property
    def usable_category(self) -> bool:
        """Sufficient for a *passive* note, never for authorizing motors."""
        return self.status == "identified"


def summarize_passive(snapshot: PerceptionSnapshot, *, now: float) -> tuple[PassiveObservation, ...]:
    """Project only object/sound categories, in stable first-seen order.

    Conflicting labels on the same ephemeral object track, low-confidence
    evidence, unknown categories and future frames never become identities.
    A sound event is one category per snapshot; competing categories are
    flagged as conflicts rather than treated as simultaneous verified sounds.
    Safety kinds such as floor_clear and safe_area are never projected here.

    The v1 safety Scene conversion is deliberately untouched: no new sensor
    fact becomes an implicit motion clearance.
    """
    if not isinstance(snapshot, PerceptionSnapshot):
        raise TypeError("snapshot must be PerceptionSnapshot")
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        raise ValueError("now must be a finite monotonic timestamp")
    if len(snapshot.events) > MAX_EVENTS:
        raise ValueError("passive event budget exceeded")

    groups: dict[tuple[str, str | None], list] = {}
    for event in snapshot.events:
        if event.kind not in PASSIVE_KINDS:
            continue
        key = (event.kind, event.track_id if event.kind == "object_label" else None)
        groups.setdefault(key, []).append(event)

    results: list[PassiveObservation] = []
    for (kind, track_id), events in groups.items():
        permitted = _TRUSTED[snapshot.environment][kind]
        candidates = [e for e in events if e.source in permitted]
        source_set = {e.source for e in (candidates or events)}
        declared_source = next(iter(source_set)) if len(source_set) == 1 else "mixed_claims"
        last = max(e.observed_at for e in events)
        category, status, confidence = "unknown", "untrusted", 0.0

        if candidates:
            if now < snapshot.observed_at or any(e.observed_at > now for e in candidates):
                status = "future"
            else:
                fresh = [e for e in candidates if e.fresh_at(now)]
                if not fresh:
                    status = "stale"
                else:
                    confidence = min(e.confidence for e in fresh)
                    labels = {e.value for e in fresh}
                    if len(labels) != 1:
                        status = "conflict"
                    elif confidence < DETECTION_CONFIDENCE:
                        status = "low_confidence"
                    else:
                        label = next(iter(labels))
                        if label == "unknown":
                            status = "unknown"
                        elif kind == "object_label" and label not in OBJECT_CATEGORIES:
                            # v1 accepts legacy freeform labels, but this new
                            # passive contract never promotes a name/transcript.
                            status = "unknown"
                        else:
                            category, status = label, "identified"
        results.append(PassiveObservation(
            kind=kind,
            category=category,
            status=status,
            claimed_source=declared_source,
            confidence=confidence,
            observed_at=last,
            track_id=track_id,
        ))
    return tuple(results)
