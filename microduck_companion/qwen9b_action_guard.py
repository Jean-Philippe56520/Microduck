"""F5 v3: bounded, fail-closed candidate screening; NOT a robot motor controller.

This module consumes a strict machine hypothesis and *independent* fixture
facts. The existing Qwen v2 text-only preview is never parsed into authority.
No network, robotd, actuators, memory, sensors or Qwen imports.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any

MAX_WIRE_BYTES = 2048
MAX_PREVIEW_CHARS = 1200
SCHEMA_VERSION = 1
SCENE_SOURCE = "independent_mock_fixture"
_CATEGORIES = frozenset({"ball", "cushion", "chair", "other_object", "cat", "dog", "person", "unknown"})
_LIVING = frozenset({"cat", "dog", "person"})
_PRESENCE = frozenset({"real", "depicted", "unknown"})
_ALLOWED_OEM = frozenset({"kick_left", "kick_right", "ground_pick", "walk", "sit_toggle", "sitstand", "roulade"})
# Narrow, documented *hypothesis* compatibility, never validated execution.
_COMPATIBLE_EXPERIMENTS = frozenset({
    ("ball", "kick_left", "target_displaced", "independent_position_change"),
    ("ball", "kick_right", "target_displaced", "independent_position_change"),
})
_SCENE_ID = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)
_TARGET_REF = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z", re.ASCII)
_MOTOR_WORD = re.compile(r"\b(?:ground_pick|kick_left|kick_right|walk|sit_toggle|sitstand|roulade)\b", re.I)
_LIVING_WORD = re.compile(r"\b(?:chat|chats|chaton|chien|chiens|animal|animaux|personne|humain|enfant|enfants|cat|dog|person)\b", re.I)
# Human-review-only hints, intentionally not a semantic action or safety detector.
# Words may occur in negations/quotes: a flag asks for a closer human reading.
_APPROACH_WORD = re.compile(
    r"\b(?:s['’]approcher|se rapprocher|approcher|s['’]avancer|avancer|se d[eé]placer)\b",
    re.I,
)
_GENERIC_MOTOR_WORD = re.compile(
    r"\b(?:geste(?:s)?\s+moteur(?:s)?|mouvement(?:s)?\s+moteur(?:s)?)\b",
    re.I,
)


class CandidateError(ValueError):
    """Malformed or untrusted hypothesis; do not expose raw input in errors."""


def _finite_nonnegative(value: object) -> bool:
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class IndependentScene:
    """Explicitly synthetic facts, never derived from an advisor's free text.

    A future real-sensor provenance adapter requires a separate audit. This
    fixture type cannot attest safety or authorize an actual robot action.
    """

    scene_id: str
    target_ref: str
    category: str
    presence: str
    clear_zone: bool
    verified_floor: bool
    loaded_oem: frozenset[str]
    observed_monotonic_s: float
    expires_monotonic_s: float
    source: str = SCENE_SOURCE

    def __post_init__(self) -> None:
        if (type(self.scene_id) is not str or not _SCENE_ID.fullmatch(self.scene_id)
                or type(self.target_ref) is not str or not _TARGET_REF.fullmatch(self.target_ref)
                or type(self.category) is not str or self.category not in _CATEGORIES
                or type(self.presence) is not str or self.presence not in _PRESENCE
                or type(self.clear_zone) is not bool or type(self.verified_floor) is not bool
                or type(self.loaded_oem) is not frozenset
                or any(type(s) is not str or s not in _ALLOWED_OEM for s in self.loaded_oem)
                or not _finite_nonnegative(self.observed_monotonic_s)
                or not _finite_nonnegative(self.expires_monotonic_s)
                or not 0 < self.expires_monotonic_s - self.observed_monotonic_s <= 5.0
                or self.source != SCENE_SOURCE):
            raise ValueError("invalid independent synthetic scene")


@dataclass(frozen=True)
class GuardVerdict:
    status: str
    reason: str
    robot_authorized: bool = False
    motor_commands_issued: int = 0
    memory_writes: int = 0

    def __post_init__(self) -> None:
        if (self.status not in {"rejected", "passive_only", "hypothesis_for_review"}
                or type(self.reason) is not str
                or self.robot_authorized is not False
                or self.motor_commands_issued != 0 or self.memory_writes != 0):
            raise ValueError("guard verdict may not grant physical authority")


def _strict_dict(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in pairs:
        if key in out:
            raise CandidateError("duplicate field")
        out[key] = val
    return out


def _reject_nonfinite(_value: str) -> None:
    raise CandidateError("nonfinite number")


def parse_candidate(wire: bytes) -> dict[str, Any]:
    """Accept a *future* strictly constrained proposal, never a free-text reply."""
    if type(wire) is not bytes or not 0 < len(wire) <= MAX_WIRE_BYTES:
        raise CandidateError("invalid candidate size")
    try:
        raw = json.loads(wire.decode("utf-8"), object_pairs_hook=_strict_dict,
                         parse_constant=_reject_nonfinite)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CandidateError("invalid candidate JSON") from exc
    keys = {"schema_version", "scene_id", "target_ref", "kind", "oem_candidate", "expected_effect", "verification"}
    if type(raw) is not dict or set(raw) != keys:
        raise CandidateError("unexpected candidate fields")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != SCHEMA_VERSION:
        raise CandidateError("invalid schema version")
    if type(raw["scene_id"]) is not str or not _SCENE_ID.fullmatch(raw["scene_id"]):
        raise CandidateError("invalid scene id")
    if type(raw["target_ref"]) is not str or not _TARGET_REF.fullmatch(raw["target_ref"]):
        raise CandidateError("invalid target reference")
    if raw["kind"] not in ("observation", "inaction", "motor_experiment") or type(raw["kind"]) is not str:
        raise CandidateError("invalid candidate kind")
    for key in ("oem_candidate", "expected_effect", "verification"):
        if raw[key] is not None and type(raw[key]) is not str:
            raise CandidateError("invalid candidate value")
    # Exact, bounded enums prevent free text from becoming a movement or claim.
    if raw["kind"] == "observation":
        expected = (None, "new_view", "independent_new_view")
    elif raw["kind"] == "inaction":
        expected = (None, "no_change_claimed", "none")
    else:
        expected = ("kick_left", "target_displaced", "independent_position_change")
        if raw["oem_candidate"] not in _ALLOWED_OEM:
            raise CandidateError("unrecognized OEM candidate")
        if raw["expected_effect"] != expected[1] or raw["verification"] != expected[2]:
            raise CandidateError("unverifiable or unsupported motor effect")
        return raw
    if (raw["oem_candidate"], raw["expected_effect"], raw["verification"]) != expected:
        raise CandidateError("passive candidate cannot contain a motor proposal")
    return raw


def assess_candidate(wire: bytes, *, scene: IndependentScene | None,
                     now_monotonic_s: float) -> GuardVerdict:
    """Report only eligibility for *human review*, never motor authorization.

    The independent scene object is a mock. If context is absent/stale, even a
    syntactically valid motor proposal is denied. No calls to robotd exist.
    """
    if not _finite_nonnegative(now_monotonic_s):
        return GuardVerdict("rejected", "invalid_local_time")
    try:
        raw = parse_candidate(wire)
    except CandidateError:
        return GuardVerdict("rejected", "malformed_or_untrusted_candidate")
    if not isinstance(scene, IndependentScene):
        return GuardVerdict("rejected", "independent_scene_missing")
    if (raw["scene_id"] != scene.scene_id or raw["target_ref"] != scene.target_ref
            or not scene.observed_monotonic_s <= now_monotonic_s < scene.expires_monotonic_s):
        return GuardVerdict("rejected", "scene_mismatch_or_expired")
    if raw["kind"] in {"observation", "inaction"}:
        return GuardVerdict("passive_only", "no_motor_hypothesis")
    # Critical: Qwen cannot mark a target inert, the floor safe, or an OEM skill
    # loaded. These must originate from the *independent* scene fixture.
    if scene.category in _LIVING or scene.presence != "real":
        return GuardVerdict("rejected", "living_depicted_or_presence_uncertain")
    if scene.category in {"unknown"}:
        return GuardVerdict("rejected", "target_unknown")
    if not scene.clear_zone or not scene.verified_floor:
        return GuardVerdict("rejected", "floor_or_zone_unverified")
    if raw["oem_candidate"] not in scene.loaded_oem:
        return GuardVerdict("rejected", "oem_skill_not_confirmed_in_fixture")
    if (scene.category, raw["oem_candidate"], raw["expected_effect"],
            raw["verification"]) not in _COMPATIBLE_EXPERIMENTS:
        return GuardVerdict("rejected", "incoherent_target_action_effect")
    return GuardVerdict("hypothesis_for_review", "fixture_compatible_not_robot_authorized")


def screen_preview_text(advisor_text: str) -> dict[str, Any]:
    """Human-only warning for native v2 prose, NOT a safety classifier.

    A keyword scan can miss synonyms and context. Every free-text reply is
    blocked from machine/action use, even if no suspicious words are found.
    """
    if type(advisor_text) is not str or not 0 < len(advisor_text) <= MAX_PREVIEW_CHARS:
        raise ValueError("invalid bounded advisor text")
    motor = bool(_MOTOR_WORD.search(advisor_text))
    living = bool(_LIVING_WORD.search(advisor_text))
    flags = []
    if motor:
        flags.append("untrusted_motor_reference")
    if living and motor:
        flags.append("possible_living_motor_risk")
    # The real QW-QUAL-1A scene_b test suggested "s'approcher" and
    # "geste moteur" without naming an OEM skill. These are weak review cues,
    # never evidence of unsafe intent or a validated physical action.
    if _APPROACH_WORD.search(advisor_text):
        flags.append("physical_approach_mention")
    if _GENERIC_MOTOR_WORD.search(advisor_text):
        flags.append("unspecified_motor_mention")
    return {"machine_use": "blocked", "review_flags": flags,
            "physical_actions_authorized": False}
