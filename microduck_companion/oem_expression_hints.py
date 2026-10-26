"""P-C: read-only interpretation of *mock* OEM petting/ambient event shapes.

This is a companion to P-A/P-B's existing BehaviorPortrait, NOT a second
brain, sound player, wake-word detector, head controller or mic capture path.
The pinned OEM already handles PettingEvent::Start -> coo in robotd; it only
logs ambient SoundEvent::Noise/Voice. This module never subscribes to those
events on hardware, schedules outputs, or claims OEM effects occurred.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .behavior_personality import BehaviorPortrait
from .mock_social_cues import MockSocialContext

MAX_MOCK_CUE_AGE_S = 1.5
MOCK_OEM_KINDS = frozenset({
    "petting_start", "petting_end", "ambient_noise", "ambient_voice",
})
_HISTORICAL_HINTS = frozenset({"Petted", "Startle"})
_STATUSES = frozenset({"silent", "oem_owned", "hypothesis", "notice_only"})
_REASONS_BY_STATUS = {
    "silent": frozenset({
        "no_mock_cue", "mock_opt_in_missing", "mock_quiet_mode",
        "mock_safety_or_stop", "stale_future_mock_cue",
        "self_generated_noise_or_motion", "petting_ended",
        "sound_context_not_opted_in",
    }),
    "oem_owned": frozenset({"oem_petting_coo_already_owned"}),
    "hypothesis": frozenset({"ambient_noise_startle_unverified"}),
    "notice_only": frozenset({"voice_detected_not_understood"}),
}


def _finite_time(value: object) -> bool:
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class MockOemCue:
    """Name of an OEM event in a fictional scenario, never a captured event.

    These are *mapped* from the pinned OEM PettingEvent and SoundEvent enums.
    No confidence, microphone samples or signal IDs are manufactured.
    """
    kind: str
    observed_monotonic_s: float
    source: str = "mock_oem_event_only"

    def __post_init__(self) -> None:
        if (type(self.kind) is not str or self.kind not in MOCK_OEM_KINDS
                or not _finite_time(self.observed_monotonic_s)
                or self.source != "mock_oem_event_only"):
            raise ValueError("P-C needs one bounded fictional OEM event")


@dataclass(frozen=True)
class MockOemConditions:
    """Fixture safety/self-audio flags; never verified real-world clearances."""
    busy: bool = False
    fallen: bool = False
    self_audio: bool = False
    self_motion: bool = False
    stop_requested: bool = False

    def __post_init__(self) -> None:
        if any(type(getattr(self, name)) is not bool for name in (
                "busy", "fallen", "self_audio", "self_motion",
                "stop_requested")):
            raise ValueError("mock conditions must be booleans")


@dataclass(frozen=True)
class MockExpressionHint:
    """Pure description of a possible historical state, NEVER an instruction.

    status='oem_owned' means the upstream code *owns* the petting response,
    not that the toy fixture made any sound or that the robot was touched.
    """
    status: str
    reason: str
    historical_candidate: str | None
    base_state: str
    base_affect: str
    inspection_habit: str
    source: str = "mock_expression_read_only"
    executed: bool = False
    physical_execution_authorized: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0
    audio_bytes_stored: int = 0
    sensor_reads: int = 0
    pc_requests_issued: int = 0
    memories_written: int = 0
    wake_word_recognized: bool = False
    real_sensor_authenticated: bool = False

    def __post_init__(self) -> None:
        if (self.status not in _STATUSES
                or self.reason not in _REASONS_BY_STATUS.get(self.status, ())
                or self.historical_candidate not in (_HISTORICAL_HINTS | {None})
                or (self.status == "oem_owned"
                    and self.historical_candidate != "Petted")
                or (self.status == "hypothesis"
                    and self.historical_candidate != "Startle")
                or (self.status in {"silent", "notice_only"}
                    and self.historical_candidate is not None)
                or (self.status not in {"oem_owned", "hypothesis"}
                    and self.historical_candidate is not None)
                or type(self.base_state) is not str
                or type(self.base_affect) is not str
                or type(self.inspection_habit) is not str
                or self.source != "mock_expression_read_only"
                or self.executed or self.physical_execution_authorized
                or self.motor_commands_issued or self.speaker_commands_issued
                or self.audio_bytes_stored or self.sensor_reads
                or self.pc_requests_issued or self.memories_written
                or self.wake_word_recognized or self.real_sensor_authenticated):
            raise ValueError("expression hints cannot authorize or report hardware")


def describe_oem_expression(
    portrait: BehaviorPortrait, *,
    cue: MockOemCue | None,
    context: MockSocialContext,
    conditions: MockOemConditions,
    now_monotonic_s: float,
) -> MockExpressionHint:
    """Post-decision read-only interpretation with fail-silent gating.

    No call back into AutonomyBrain, MockSocialComposer, SQLite, OEM service or
    motor safety. Context consent and safety flags are ONLY fixture assertions.
    They never grant physical permission. The portrait itself already contains
    the existing F2/F4 decision, motivations and (optional) memory summary.
    """
    if not isinstance(portrait, BehaviorPortrait):
        raise TypeError("existing P-A/P-B BehaviorPortrait required")
    if not isinstance(context, MockSocialContext):
        raise TypeError("existing F4-C MockSocialContext required")
    if not isinstance(conditions, MockOemConditions):
        raise TypeError("mock OEM conditions required")
    if cue is not None and not isinstance(cue, MockOemCue):
        raise TypeError("one bounded mock OEM cue or None required")
    if not _finite_time(now_monotonic_s):
        raise ValueError("invalid mock monotonic clock")
    if (portrait.source != "mock_post_decision_only"
            or portrait.executed or portrait.physical_execution_authorized
            or portrait.motor_commands_issued or portrait.speaker_commands_issued
            or portrait.memories_written or portrait.pc_requests_issued):
        raise ValueError("cannot reuse a physically executing portrait")

    def hint(status: str, reason: str,
             candidate: str | None = None) -> MockExpressionHint:
        return MockExpressionHint(
            status, reason, candidate, portrait.state, portrait.affect,
            portrait.inspection_habit,
        )

    if cue is None:
        return hint("silent", "no_mock_cue")
    if not (context.operator_opt_in and context.supervised
            and context.privacy_reviewed):
        return hint("silent", "mock_opt_in_missing")
    if context.quiet_mode:
        return hint("silent", "mock_quiet_mode")
    if conditions.busy or conditions.fallen or conditions.stop_requested:
        return hint("silent", "mock_safety_or_stop")
    if (cue.observed_monotonic_s > now_monotonic_s
            or now_monotonic_s - cue.observed_monotonic_s
            > MAX_MOCK_CUE_AGE_S):
        return hint("silent", "stale_future_mock_cue")
    if cue.kind == "petting_end":
        return hint("silent", "petting_ended")
    if cue.kind == "petting_start":
        # OEM robotd already handles coo on PettingEvent::Start when calm.
        # Never replay it, add a second 'Petted' scheduler or learn reward.
        return hint("oem_owned", "oem_petting_coo_already_owned", "Petted")
    if conditions.self_audio or conditions.self_motion:
        return hint("silent", "self_generated_noise_or_motion")
    # This is consent for considering a sound-related *fictional* display,
    # NOT authorization to capture or emit any audio.
    if not context.brief_audio_opt_in:
        return hint("silent", "sound_context_not_opted_in")
    if cue.kind == "ambient_noise":
        # A short transient does not establish surprise or a threat.
        # OEM only LOGS SoundEvent::Noise; it does not issue Startle.
        return hint("hypothesis", "ambient_noise_startle_unverified", "Startle")
    # SoundEvent::Voice is NOT speech-to-text or 'He Kwipi!' recognition.
    return hint("notice_only", "voice_detected_not_understood")
