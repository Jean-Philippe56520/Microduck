"""Category-first active *inspection hints* on fictive, partial visual cues.

Reuses F2-A/F2-B's already selected PassiveIntent("inspect") rather than
adding a second brain or motor policy. The output says which *type* of
evidence could clarify a category, never where to point the head.

No image/model inference, sensor authentication, physical motion, Qwen request,
SQLite writes, biometric identity or observation-to-fact promotion. A person
category or part does not identify a person. All cues here are MOCK fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .passive_intentions import PassiveIntent

MAX_CUES = 4
MAX_CUE_AGE_S = 2.0
MAX_FOLLOWUPS = 2
MIN_CUE_CONFIDENCE = 0.70

# Categories are *possible* interpretations of isolated visible details.
# Importantly, "shoe" alone does not imply a nearby person; "furniture_leg"
# alone is neither evidence of a full chair nor of safe navigable ground.
_POSSIBLE = {
    "hand": ("person",),
    "forearm": ("person",),
    "foot": ("person",),
    "leg": ("person",),
    "shoe": ("shoe",),
    "sole": ("shoe",),
    "fur": ("cat", "dog"),
    "paw": ("cat", "dog"),
    "whiskers": ("cat",),
    "muzzle": ("dog", "cat"),
    "furniture_leg": ("chair",),
    "seat": ("chair",),
    "round_edge": ("ball",),
    "round_outline": ("ball",),
}
# Semantic directions only. Actual camera geometry, head orientation and
# actuation are out of scope and must belong to validated OEM/robotd APIs.
_FOLLOW = {
    "hand": "forearm", "forearm": "body_outline",
    "foot": "leg", "leg": "body_outline",
    "shoe": "sole", "sole": "shoe_outline",
    "fur": "head_outline", "paw": "head_outline",
    "whiskers": "head_outline", "muzzle": "body_outline",
    "furniture_leg": "seat", "seat": "chair_back",
    "round_edge": "round_outline", "round_outline": "whole_object",
}
# These are new possible categories for a future detector, NOT additions to
# the sensor-verified object labels in the existing F1 v1 contract.


def _finite_nonnegative(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class PartialVisualCue:
    """Small non-personal mock descriptor; never a saved photograph or track."""

    part: str
    confidence: float
    observed_at_s: float
    source: str = "mock"

    def __post_init__(self) -> None:
        if type(self.part) is not str or self.part not in _POSSIBLE:
            raise ValueError("unsupported bounded visual part")
        if self.source != "mock":
            raise ValueError("only explicitly fictive part observations")
        if (not _finite_nonnegative(self.confidence)
                or self.confidence > 1
                or not _finite_nonnegative(self.observed_at_s)):
            raise ValueError("invalid cue confidence or timestamp")


@dataclass(frozen=True)
class CategoryInspectionHint:
    """An explanation, not an action, model classification or Qwen approval."""

    status: str  # keep_unknown | inspect_more | pc_review_candidate
    candidates_unverified: tuple[str, ...]
    look_for: str | None
    reason: str
    source: str = "mock"
    verified_category: bool = False
    physical_source_verified: bool = False
    sensor_reads: int = 0
    motor_commands_issued: int = 0
    pc_requests_issued: int = 0
    memories_written: int = 0

    def __post_init__(self) -> None:
        if (self.status not in {
                "keep_unknown", "inspect_more", "pc_review_candidate"
            } or self.source != "mock"
                or self.verified_category or self.physical_source_verified
                or self.sensor_reads or self.motor_commands_issued
                or self.pc_requests_issued or self.memories_written):
            raise ValueError("inspection hint cannot produce physical facts/actions")
        if self.status != "inspect_more" and self.look_for is not None:
            raise ValueError("only an inspection hint can name missing evidence")
        if self.status == "inspect_more" and not self.look_for:
            raise ValueError("inspection must identify evidence, not a movement")
        if (type(self.candidates_unverified) is not tuple
                or any(x not in {c for values in _POSSIBLE.values()
                                  for c in values}
                       for x in self.candidates_unverified)):
            raise ValueError("only bounded unverified categories")


def suggest_category_inspection(
    selected_intent: PassiveIntent,
    cues: tuple[PartialVisualCue, ...],
    *,
    now_monotonic_s: float,
    followups_used: int = 0,
    visual_continuity_supported: bool = False,
    optional_pc_consent: bool = False,
) -> CategoryInspectionHint:
    """Suggest missing evidence after the EXISTING passive F2 'inspect'.

    The caller is responsible for supplying F2's real current decision and
    counting previously authorized *observations*; this function itself
    cannot execute observations, override cooldowns or increase their budget.

    'visual_continuity_supported' is a fictive fixture annotation, not a
    connected-component/3D perception algorithm. Without it, cues are NOT
    fused into one physical object. Even with it, no verified class is made.
    """
    if not isinstance(selected_intent, PassiveIntent):
        raise TypeError("requires the existing F2 passive intention")
    if (type(cues) is not tuple or len(cues) > MAX_CUES
            or any(not isinstance(c, PartialVisualCue) for c in cues)):
        raise ValueError("bounded tuple of visual fixture cues required")
    if not _finite_nonnegative(now_monotonic_s):
        raise ValueError("invalid monotonic timestamp")
    if type(followups_used) is not int or not 0 <= followups_used <= MAX_FOLLOWUPS:
        raise ValueError("invalid inspection budget")
    if (type(visual_continuity_supported) is not bool
            or type(optional_pc_consent) is not bool):
        raise ValueError("explicit boolean continuity/consent required")

    def unknown(reason: str, possibilities: tuple[str, ...] = ()):
        return CategoryInspectionHint(
            "keep_unknown", possibilities, None, reason)

    if (selected_intent.intention != "inspect"
            or selected_intent.target_kind != "object_label"
            or selected_intent.target_category != "unknown"):
        return unknown("existing_f2_intent_does_not_request_inspection")
    if not cues:
        return unknown("no_current_partial_visual_evidence")
    if any(c.observed_at_s > now_monotonic_s
           or now_monotonic_s - c.observed_at_s > MAX_CUE_AGE_S
           or c.confidence < MIN_CUE_CONFIDENCE for c in cues):
        return unknown("stale_future_or_weak_visual_evidence")

    per_part = [set(_POSSIBLE[c.part]) for c in cues]
    # A torso/hand or fur/paw group is linked only with positive continuity
    # evidence. Two objects accidentally appearing in one frame don't merge.
    possibilities = (set.intersection(*per_part)
                     if visual_continuity_supported and len(per_part) > 1
                     else set.union(*per_part))
    if not possibilities:
        return unknown("contradictory_connected_parts")
    candidates = tuple(sorted(possibilities))

    if followups_used == MAX_FOLLOWUPS:
        if "person" in possibilities:
            return unknown("person_clues_cannot_trigger_pc_review", candidates)
        if optional_pc_consent:
            # This is NOT a reservation or call. Existing F5 SelectivePCPolicy
            # and sanitized opt-in transport must make the actual decision.
            return CategoryInspectionHint(
                "pc_review_candidate", candidates, None,
                "optional_f5_permission_and_quota_still_required")
        return unknown("observation_budget_exhausted_without_pc_consent",
                       candidates)

    seen = {c.part for c in cues}
    target = next(
        (_FOLLOW[c.part] for c in cues if _FOLLOW[c.part] not in seen),
        None)
    if target is None:
        return unknown("no_additional_known_nonmotor_clue", candidates)
    return CategoryInspectionHint(
        "inspect_more", candidates, target,
        "seek_visual_continuity_not_identity")
