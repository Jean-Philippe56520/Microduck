"""F2-A: strictly *proposed*, non-motor attention from F1 passive categories.

This is a deterministic decision layer on the EXISTING AutonomyBrain and
ExperienceMemory journal, not a second autonomous controller. It NEVER
executes looking, listening, resting, speaking, Qwen, or any robotd command.
An old SQLite entry informs *category familiarity*, never current sensing,
safe floor, identity, location, reward, or proven robot energy.

The only supported current source is the explicitly synthetic F1-B fixture.
F2-B will later address motivation arbitration, cooldowns, and repetition.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3
from typing import TYPE_CHECKING

from .autonomy import Motivations
from .passive_memory import PassiveObservationJournal
from .passive_observations import summarize_passive, PASSIVE_KINDS, OBJECT_CATEGORIES
from .passive_sources import PassiveRead
from .perception import PerceptionSnapshot, _SOUND_CATEGORIES

if TYPE_CHECKING:
    from .passive_observations import PassiveObservation

_INTENTIONS = frozenset({"observe", "inspect", "listen", "idle", "rest"})
_NO_SOURCE = frozenset({
    "unavailable_or_invalid", "rate_limited", "clock_reset",
    "duplicate_or_out_of_order",
})
_ENERGY_REST_THRESHOLD = 0.20
_CURIOSITY_OBSERVE_THRESHOLD = 0.30
_CURIOSITY_INSPECT_THRESHOLD = 0.45
_SOCIAL_LISTEN_THRESHOLD = 0.30


@dataclass(frozen=True)
class PassiveIntent:
    """An explainable *proposal*, not an executed action or an identity.

    target_category is a *fictional category*, never an individual or
    ephemeral track. Even a 'listen' or 'inspect' proposal has no motor/audio
    side effects. source describes fixture provenance, not authenticated
    hardware.
    """

    intention: str
    reason: str
    target_kind: str | None = None
    target_category: str | None = None
    source: str = "mock"
    executed: bool = False
    motor_commands_issued: int = 0
    request_pc_analysis: bool = False

    def __post_init__(self) -> None:
        if self.intention not in _INTENTIONS:
            raise ValueError("only non-motor passive intentions are supported")
        if self.source != "mock" or self.executed or self.motor_commands_issued:
            raise ValueError("passive intentions cannot be executed as motors")
        if self.request_pc_analysis:
            raise ValueError("Qwen requests are outside F2-A")
        if self.target_kind not in (None, "object_label", "sound_label"):
            raise ValueError("unsupported passive attention kind")
        if self.intention in {"idle", "rest"}:
            if self.target_kind is not None or self.target_category is not None:
                raise ValueError("idle/rest cannot name a target")
        elif self.intention in {"observe", "inspect"}:
            if (self.target_kind != "object_label"
                    or self.target_category not in OBJECT_CATEGORIES):
                raise ValueError("object attention requires a bounded category")
        elif self.intention == "listen":
            if (self.target_kind != "sound_label"
                    or self.target_category not in _SOUND_CATEGORIES):
                raise ValueError("sound attention requires a bounded category")


def _still(reason: str) -> PassiveIntent:
    return PassiveIntent("idle", reason)


def _valid_scalar(value: object, *, minimum: float = 0) -> bool:
    return type(value) in (float, int) and math.isfinite(value) and value >= minimum


def _valid_motivations(motives: Motivations) -> bool:
    return all(
        _valid_scalar(getattr(motives, name))
        and getattr(motives, name) <= 1.0
        for name in ("curiosity", "sociability", "play", "energy",
                 "caution", "determination")
    )


def propose_passive_intention(
    reading: PassiveRead,
    *,
    journal: PassiveObservationJournal,
    motivations: Motivations,
    now_monotonic_s: float,
    now_wall_epoch_s: float,
) -> PassiveIntent:
    """Propose passive attention using *only current F1 mock observations*.

    Fail-closed (idle) on missing/unauthorized/expired sources, unsafe kinds,
    malformed motivational state, or uncertain evidence. A low *simulated*
    motivational-energy variable can propose 'rest' on a valid fixture; this
    is NOT a reading of the robot battery.

    This function reads the historical SQLite journal without changing it.
    The caller may separately journal a valid read via F1-C, AFTER proposing.
    It never calls AutonomyBrain.choose(), .feedback(), or robotd; the
    independent OEM motion safety path is unchanged.
    """
    if not isinstance(reading, PassiveRead):
        raise TypeError("F2-A requires F1-B PassiveRead")
    if not isinstance(journal, PassiveObservationJournal):
        raise TypeError("F2-A requires the existing passive SQLite journal")
    if not isinstance(motivations, Motivations):
        raise TypeError("F2-A requires the existing Motivations values")
    if not _valid_scalar(now_monotonic_s) or not _valid_scalar(now_wall_epoch_s):
        raise ValueError("both clocks must be finite nonnegative numbers")
    if not _valid_motivations(motivations):
        return _still("invalid_motivations")
    if reading.status != "ok":
        return _still(
            "source_unavailable" if reading.status in _NO_SOURCE
            else "unrecognized_read_status"
        )
    if reading.channel != "mock_fixture_unix":
        return _still("untrusted_channel")
    if type(reading.sequence) is not int or not 0 <= reading.sequence < 2**63:
        return _still("invalid_sequence")
    snapshot = reading.snapshot
    if not isinstance(snapshot, PerceptionSnapshot):
        return _still("invalid_snapshot")
    if snapshot.environment != "mock":
        return _still("untrusted_environment")
    if any(event.kind not in PASSIVE_KINDS or event.source != "mock"
           for event in snapshot.events):
        return _still("untrusted_or_nonpassive_event")

    try:
        observations = summarize_passive(snapshot, now=now_monotonic_s)
    except (ValueError, TypeError):
        return _still("invalid_observation_batch")
    if any(obs.claimed_source != "mock" for obs in observations):
        return _still("untrusted_observation")
    if any(obs.status in {"future", "stale", "untrusted"}
           for obs in observations):
        return _still("observation_not_fresh_or_trusted")
    if motivations.energy <= _ENERGY_REST_THRESHOLD:
        return PassiveIntent("rest", "low_simulated_motivational_energy")
    if not observations:
        return _still("no_current_observation")

    # Unresolved objects can motivate *cognitive inspection* (not a camera
    # motion or physical approach). Other low-confidence evidence is ignored.
    if motivations.curiosity >= _CURIOSITY_INSPECT_THRESHOLD:
        for obs in observations:
            if obs.kind == "object_label" and obs.status in {
                "unknown", "conflict",
            }:
                return PassiveIntent(
                    "inspect", "unresolved_fictional_object_category",
                    "object_label", "unknown",
                )

    if motivations.sociability >= _SOCIAL_LISTEN_THRESHOLD:
        for obs in observations:
            if obs.kind == "sound_label" and obs.status in {
                "identified", "unknown", "conflict",
            }:
                return PassiveIntent(
                    "listen", "fictional_sound_attends_without_audio_capture",
                    "sound_label", obs.category,
                )

    if motivations.curiosity >= _CURIOSITY_OBSERVE_THRESHOLD:
        for obs in observations:
            if obs.kind != "object_label" or not obs.usable_category:
                continue
            try:
                count = journal.category_count(
                    obs.kind, obs.category, now_wall_epoch_s=now_wall_epoch_s,
                )
            except sqlite3.Error:
                return _still("history_unavailable")
            if count == 0:
                return PassiveIntent(
                    "observe", "new_fictional_category_in_local_history",
                    "object_label", obs.category,
                )
    return _still("no_new_safe_passive_attention")
