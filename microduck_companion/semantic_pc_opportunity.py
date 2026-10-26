"""PD3: decide whether a MOCK scene merits asking a PC, without asking it.

The *existing* F5-A advisory is produced after a local F2 decision and is
reused here; F2 must never be ticked a second time. Two distinct synthetic
F1-B reads may suggest a persistent unknown/contradiction, NOT a real object
identity or two independently authenticated camera observations.

F5-A/B currently transmit only synthetic 'unknown' category metadata.
Qwen's pinned prompt must answer 'unknown'. Consequently this PD3 gate can
identify INTEREST, but must NEVER reserve F5-C quota, launch the F5-B worker
or claim an informative Qwen request is currently possible.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .autonomy import Motivations
from .behavior_continuity import (
    MockBehaviorDisposition, MockBehaviorSituation,
)
from .behavior_personality import BehaviorPortrait
from .passive_intentions import _valid_motivations
from .passive_observations import (
    OBJECT_CATEGORIES, summarize_passive,
)
from .passive_sources import PassiveRead
from .pc_hypothesis_contract import OptionalPCAdvisory
from .perception import PerceptionSnapshot

MAX_MOCK_FRAME_AGE_S = 1.0
MIN_MOCK_SAMPLE_GAP_S = 0.5
MAX_MOCK_SAMPLE_GAP_S = 30.0
MAX_MOCK_EVENTS_PER_SAMPLE = 4
_SOURCE = "mock_pd3_semantic_opportunity_only"
_CANDIDATE_STATES = frozenset({
    "LookAround", "TurnInPlace", "Wander", "GroundPick",
})
_ALLOWED_CONTEXTS = frozenset({
    "none", "viewpoint_ambiguity", "new_space", "floor_object",
})
_DENIALS = frozenset({
    "no_semantic_behavior", "unsafe_mock_context",
    "insufficient_mock_interest", "no_f5_inspection_question",
    "invalid_or_private_mock_samples", "not_repeated_mock_uncertainty",
    "f5_request_mismatch", "expired_f5_request",
})
_CANDIDATE_REASONS = frozenset({
    "pc_opt_in_missing", "f5_has_no_discriminating_input",
})


def _clock(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class MockPCOpportunity:
    """Informational triage only: never a dispatch credential."""

    interesting: bool
    reason: str
    behavior_state: str
    local_intention: str
    trigger: str = "none"
    fixture_samples: int = 0
    source: str = _SOURCE
    eligible_for_transport: bool = False
    request_transmitted: bool = False
    real_scene_verified: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0
    pc_requests_issued: int = 0
    memories_written: int = 0

    def __post_init__(self) -> None:
        if (type(self.interesting) is not bool
                or self.behavior_state not in {
                    "Chill", "LookAround", "Wander", "TurnInPlace",
                    "Zoomies", "Startle", "Stretch", "Ruffle",
                    "Preen", "Sneeze", "Dance", "GroundPick",
                    "Nap", "BallPlay", "Petted", "Held"}
                or type(self.local_intention) is not str
                or self.local_intention not in {
                    "inspect", "observe", "listen", "idle", "rest"}
                or self.source != _SOURCE
                or type(self.eligible_for_transport) is not bool
                or self.eligible_for_transport
                or type(self.request_transmitted) is not bool
                or self.request_transmitted
                or type(self.real_scene_verified) is not bool
                or self.real_scene_verified
                or any(type(getattr(self, name)) is not int
                       or getattr(self, name) != 0 for name in (
                           "motor_commands_issued",
                           "speaker_commands_issued", "pc_requests_issued",
                           "memories_written"))):
            raise ValueError("PD3 cannot dispatch or authorize Qwen or actions")
        if self.interesting:
            if (self.reason not in _CANDIDATE_REASONS
                    or self.trigger not in {"unknown", "conflict"}
                    or self.fixture_samples != 2):
                raise ValueError("not a supported mock information opportunity")
        elif (self.reason not in _DENIALS or self.trigger != "none"
              or self.fixture_samples != 0):
            raise ValueError("PD3 denial must not carry a mock PC trigger")


def _single_unresolved_object(read: PassiveRead, *, at: float):
    """Return status/confidence/ephemeral track, not a name or media blob.

    All observations are synthetic and contain ONLY allowlisted object labels.
    Unrecognized free-form text is explicitly disallowed (F5-A can otherwise
    project it to unknown), as are people and all audio.
    """
    if (not isinstance(read, PassiveRead) or read.status != "ok"
            or read.channel != "mock_fixture_unix"
            or type(read.sequence) is not int
            or not 0 <= read.sequence < 2**63
            or not isinstance(read.snapshot, PerceptionSnapshot)
            or read.snapshot.environment != "mock"
            or not 1 <= len(read.snapshot.events) <= MAX_MOCK_EVENTS_PER_SAMPLE):
        return None
    for event in read.snapshot.events:
        if (event.kind != "object_label"
                or event.source != "mock"
                or type(event.value) is not str
                or event.value not in OBJECT_CATEGORIES
                or event.value == "person"):
            return None
    try:
        found = summarize_passive(read.snapshot, now=at)
    except (TypeError, ValueError, OverflowError):
        return None
    if (len(found) != 1 or found[0].kind != "object_label"
            or found[0].status not in {"unknown", "conflict"}
            or found[0].category != "unknown"
            or found[0].claimed_source != "mock"):
        return None
    return (found[0].status, found[0].confidence, found[0].track_id)


def assess_mock_pc_opportunity(
    advisory: OptionalPCAdvisory, *,
    portrait: BehaviorPortrait,
    disposition: MockBehaviorDisposition,
    previous_read: PassiveRead,
    current_read: PassiveRead,
    situation: MockBehaviorSituation,
    motivations: Motivations,
    now_monotonic_s: float,
    pc_opt_in: bool = False,
) -> MockPCOpportunity:
    """Pure post-F5-A triage. It never calls F5-C, Ollama or any scheduler.

    The two F1-B samples are separate *fictional frames*. Track equality is
    only a fixture consistency check, never a persisted biometric identity.
    Even with opt-in, the existing F5-A request lacks discriminating pixels
    or features, so no transport is permitted by this contract.
    """
    if not isinstance(advisory, OptionalPCAdvisory):
        raise TypeError("PD3 requires an existing F5-A advisory")
    if not isinstance(portrait, BehaviorPortrait):
        raise TypeError("PD3 requires an existing P-A/B portrait")
    if not isinstance(disposition, MockBehaviorDisposition):
        raise TypeError("PD3 requires an existing PD2 disposition")
    if not isinstance(situation, MockBehaviorSituation):
        raise TypeError("PD3 requires an existing PD2 mock situation")
    if not isinstance(motivations, Motivations) or not _valid_motivations(motivations):
        raise ValueError("PD3 requires valid existing F2 mock motivations")
    if type(pc_opt_in) is not bool:
        raise ValueError("PD3 PC consent flag must be a boolean")
    if not _clock(now_monotonic_s):
        raise ValueError("PD3 clock must be finite and monotonic")
    if not isinstance(previous_read, PassiveRead) or not isinstance(
            current_read, PassiveRead):
        raise TypeError("PD3 requires two F1-B read receipts")
    state = disposition.state
    local = advisory.local_intent.intention

    def denied(reason: str) -> MockPCOpportunity:
        return MockPCOpportunity(False, reason, state, local)

    if (situation.conditions.stop_requested
            or situation.conditions.fallen or situation.conditions.busy
            or disposition.reason in {
                "safety_or_stop", "clock_reset", "rest_preempts_expression"}):
        return denied("unsafe_mock_context")
    if (disposition.base_state != portrait.state
            or portrait.state != "LookAround"
            or portrait.affect != "curious"
            or portrait.reason != "passive_attention"
            or disposition.reason not in {
                "base_portrait", "contextual_mock_candidate"}
            or state not in _CANDIDATE_STATES
            or situation.cue not in _ALLOWED_CONTEXTS):
        return denied("no_semantic_behavior")
    if (portrait.inspection_habit in {
            "inspection_reserved", "unavailable"}
            or motivations.curiosity < .55 or motivations.energy < .35
            or motivations.caution > .70):
        return denied("insufficient_mock_interest")
    if (advisory.status != "pending_transport" or advisory.request is None
            or local != "inspect"
            or advisory.local_intent.target_kind != "object_label"
            or advisory.local_intent.target_category != "unknown"):
        return denied("no_f5_inspection_question")
    req = advisory.request
    now = float(now_monotonic_s)
    if not req.created_monotonic_s <= now < req.expires_monotonic_s:
        return denied("expired_f5_request")
    prev = previous_read.snapshot
    curr = current_read.snapshot
    if (previous_read.status != "ok" or current_read.status != "ok"
            or previous_read.channel != "mock_fixture_unix"
            or current_read.channel != "mock_fixture_unix"
            or type(previous_read.sequence) is not int
            or type(current_read.sequence) is not int
            or previous_read.sequence >= current_read.sequence
            or not _clock(prev.observed_at)
            or not _clock(curr.observed_at)
            or not MIN_MOCK_SAMPLE_GAP_S
                    <= curr.observed_at - prev.observed_at
                    <= MAX_MOCK_SAMPLE_GAP_S
            or curr.observed_at > now
            or now - curr.observed_at > MAX_MOCK_FRAME_AGE_S):
        return denied("invalid_or_private_mock_samples")
    first = _single_unresolved_object(
        previous_read, at=prev.observed_at,
    )
    second = _single_unresolved_object(current_read, at=now)
    if first is None or second is None:
        return denied("invalid_or_private_mock_samples")
    if (first[2] is None or first[2] != second[2]
            or first[0] not in {"unknown", "conflict"}
            or second[0] not in {"unknown", "conflict"}):
        return denied("not_repeated_mock_uncertainty")
    if (len(req.observations) != 1
            or req.observations[0].kind != "object_label"
            or req.observations[0].category != "unknown"
            or req.observations[0].status != second[0]
            or req.observations[0].claimed_confidence != second[1]):
        return denied("f5_request_mismatch")
    return MockPCOpportunity(
        True, "f5_has_no_discriminating_input" if pc_opt_in
        else "pc_opt_in_missing", state, local,
        trigger=second[0], fixture_samples=2,
    )
