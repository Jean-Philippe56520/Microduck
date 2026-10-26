"""Read-only personality portrait over the existing F2/F4 mock decisions.

The 16 names are an OEM *historical* catalogue, not 16 installed skills.
No scheduler, emotion database, new SQLite table, media, sound, motor or
robotd command is created here. This is a post-decision description only.
"""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import TYPE_CHECKING

from .passive_intentions import PassiveIntent, _valid_motivations
from .passive_memory import PassiveObservationJournal, _check_wall
from .passive_learning import PassiveLearning
from .behavioral_memory import (
    BehavioralMemory, MAX_STORED, MAX_BIAS, valid_mock_summary,
)
from .mock_social_cues import MockSocialPlan

if TYPE_CHECKING:
    from .autonomy import AutonomyBrain

# Exactly the names documented by the OEM historical autonomous prototype.
# Never silently reinterpret these labels as currently shipped capabilities.
HISTORICAL_OEM_STATES = (
    "Chill", "LookAround", "Wander", "TurnInPlace", "Zoomies",
    "Startle", "Stretch", "Ruffle", "Preen", "Sneeze", "Dance",
    "GroundPick", "Nap", "BallPlay", "Petted", "Held",
)
# Only these names can currently describe F2/F4 *fictional proposals*.
# Even these do not execute a gesture or mean an OEM skill is running.
DESCRIPTIVE_ONLY = frozenset({"Chill", "LookAround", "Nap", "BallPlay"})
REQUIRES_OEM_REVIEW = frozenset(HISTORICAL_OEM_STATES) - DESCRIPTIVE_ONLY
_FAMILIARITY = frozenset({"unknown", "new_category", "seen_once", "familiar_category", "unavailable"})
_AFFECTS = frozenset({"quiet", "calm", "curious", "attentive", "playful", "sociable", "resting", "watchful"})
_DRIVES = frozenset({"curiosity", "sociability", "play", "energy", "caution"})
_HABITS = frozenset({"neutral", "inspection_encouraged",
                     "inspection_reserved", "unavailable"})
# Two concordant mock outcomes are required before reporting a habit.
MIN_HABIT_EVIDENCE = 2
MIN_HABIT_BIAS = 0.08


@dataclass(frozen=True)
class BehaviorPortrait:
    """Bounded, inspectable *mock* expression, never a robot action.

    A category count means historical *category* occurrences, not the return
    of a familiar person, pet, toy instance or the success of an action.
    """

    state: str
    affect: str
    dominant_motivation: str
    familiarity: str
    category_observations: int
    attention_bias: float
    reason: str
    outcome_bias: float = 0.0
    mock_positive_outcomes: int = 0
    mock_negative_outcomes: int = 0
    inspection_habit: str = "neutral"
    source: str = "mock_post_decision_only"
    executed: bool = False
    physical_execution_authorized: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0
    pc_requests_issued: int = 0
    memories_written: int = 0
    identity_verified: bool = False

    def __post_init__(self) -> None:
        if (self.state not in DESCRIPTIVE_ONLY
                or self.affect not in _AFFECTS
                or self.dominant_motivation not in _DRIVES
                or self.familiarity not in _FAMILIARITY
                or type(self.category_observations) is not int
                or self.category_observations < 0
                or type(self.attention_bias) is not float
                or not -0.12 <= self.attention_bias <= 0.12
                or type(self.outcome_bias) is not float
                or not -MAX_BIAS <= self.outcome_bias <= MAX_BIAS
                or any(type(x) is not int or x < 0 or x > MAX_STORED
                       for x in (self.mock_positive_outcomes,
                                 self.mock_negative_outcomes))
                or self.mock_positive_outcomes + self.mock_negative_outcomes > MAX_STORED
                or self.inspection_habit not in _HABITS
                or self.reason not in {
                    "passive_attention", "passive_rest", "passive_idle",
                    "mock_social_glance", "mock_social_play",
                    "mock_social_chirp", "mock_social_rest", "mock_social_silence",
                    "history_unavailable",
                }
                or self.source != "mock_post_decision_only"
                or self.executed or self.physical_execution_authorized
                or self.motor_commands_issued or self.speaker_commands_issued
                or self.pc_requests_issued or self.memories_written
                or self.identity_verified):
            raise ValueError("behavior portrait cannot report execution or unbounded claims")


def behavior_catalog() -> tuple[tuple[str, str], ...]:
    """All 16 *names*, with honest present-vs-planned integration status."""
    return tuple((name, "mock_description_only" if name in DESCRIPTIVE_ONLY
                  else "requires_oem_m9_or_sensor_review")
                 for name in HISTORICAL_OEM_STATES)


# PD1: static evidence from the OEM pinned at 942e58e3. These are existing
# *partial* background effects, NOT exposed 16-state commands. In particular,
# the idle head never aims at a detected object, a yawn is not Nap, and a coo
# from robotd's petting handler is not an independently dispatched Petted.
_PINNED_OEM_EXPRESSION_EVIDENCE = {
    "Chill": ("background_idle_glance", "robotd/src/idle_head.rs"),
    "LookAround": ("background_idle_glance", "robotd/src/idle_head.rs"),
    "Nap": ("background_idle_yawn", "robotd/src/idle_head.rs"),
    "Petted": ("conditional_oem_petting_coo", "robotd/src/main.rs"),
}
_PD1_SOURCE = "pinned_oem_942e58e3_static_review"
_PD1_SOURCES = frozenset({
    "historical_catalog", "mock_behavior_portrait", "mock_oem_expression_hint",
})


@dataclass(frozen=True)
class BehaviorExpressionCapability:
    """Read-only PD1 capability evidence; never a dispatch request or receipt.

    'background_*' and 'conditional_*' are verified in OEM *source* only.
    Physical execution and the named historical 16-state skill are unverified.
    """

    state: str
    companion_status: str
    oem_expression_evidence: str
    oem_evidence_path: str | None
    selected_from: str = "historical_catalog"
    source: str = _PD1_SOURCE
    named_state_command_available: bool = False
    expression_executed: bool = False
    hardware_verified: bool = False
    physical_execution_authorized: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0
    pc_requests_issued: int = 0
    memories_written: int = 0

    def __post_init__(self) -> None:
        expected = _PINNED_OEM_EXPRESSION_EVIDENCE.get(self.state, ("none", None))
        status = ("mock_description_only" if self.state in DESCRIPTIVE_ONLY
                  else "requires_oem_m9_or_sensor_review")
        if (self.state not in HISTORICAL_OEM_STATES
                or self.companion_status != status
                or (self.oem_expression_evidence, self.oem_evidence_path) != expected
                or self.selected_from not in _PD1_SOURCES
                or self.source != _PD1_SOURCE
                or any(type(getattr(self, name)) is not bool
                       or getattr(self, name) for name in (
                           "named_state_command_available", "expression_executed",
                           "hardware_verified", "physical_execution_authorized"))
                or any(type(getattr(self, name)) is not int
                       or getattr(self, name) != 0 for name in (
                           "motor_commands_issued", "speaker_commands_issued",
                           "pc_requests_issued", "memories_written"))):
            raise ValueError("PD1 inventory cannot forge a verified command or action")


def expression_capability_for(
    state: str, *, selected_from: str = "historical_catalog",
) -> BehaviorExpressionCapability:
    """Inspect a historical state, never enable or select a robotd action."""
    if type(state) is not str or state not in HISTORICAL_OEM_STATES:
        raise ValueError("unknown historical OEM behavior")
    if type(selected_from) is not str or selected_from not in _PD1_SOURCES:
        raise ValueError("unsupported evidence provenance")
    evidence, path = _PINNED_OEM_EXPRESSION_EVIDENCE.get(state, ("none", None))
    return BehaviorExpressionCapability(
        state=state,
        companion_status=("mock_description_only" if state in DESCRIPTIVE_ONLY
                          else "requires_oem_m9_or_sensor_review"),
        oem_expression_evidence=evidence,
        oem_evidence_path=path,
        selected_from=selected_from,
    )


def expression_capability_catalog() -> tuple[BehaviorExpressionCapability, ...]:
    """Inventory EXACTLY P-A's existing sixteen names, without another FSM."""
    return tuple(expression_capability_for(name) for name in HISTORICAL_OEM_STATES)


def inspect_expression_capability(
    portrait: BehaviorPortrait, *, hint: "MockExpressionHint | None" = None,
) -> BehaviorExpressionCapability:
    """Interpret a P-A/P-B portrait and optional existing P-C mock hint.

    P-C's OEM-owned Petting label references the *upstream handler*, not a
    measured coo. An ambient-noise Startle hypothesis is NOT an OEM skill.
    Silent/notice-only cues preserve P-A's selection. No new state arbitration.
    """
    from .oem_expression_hints import MockExpressionHint

    if not isinstance(portrait, BehaviorPortrait):
        raise TypeError("existing P-A/P-B BehaviorPortrait required")
    if hint is None:
        return expression_capability_for(
            portrait.state, selected_from="mock_behavior_portrait",
        )
    if not isinstance(hint, MockExpressionHint):
        raise TypeError("existing P-C MockExpressionHint required")
    if (hint.base_state != portrait.state
            or hint.base_affect != portrait.affect
            or hint.inspection_habit != portrait.inspection_habit):
        raise ValueError("P-C cue must belong to the given P-A portrait")
    state = (hint.historical_candidate if hint.status in {"oem_owned", "hypothesis"}
             else portrait.state)
    return expression_capability_for(
        state, selected_from="mock_oem_expression_hint",
    )


def _interpret(selected: PassiveIntent | MockSocialPlan) -> tuple[str, str, str, str | None, str | None, str]:
    """Interpret an already selected proposal. Never select an action."""
    if isinstance(selected, PassiveIntent):
        if selected.intention == "rest":
            return "Nap", "resting", "passive_rest", None, None, selected.intention
        if selected.intention == "idle":
            return "Chill", "calm", "passive_idle", None, None, selected.intention
        if selected.intention == "listen":
            affect = "attentive"
        else:
            affect = "curious"
        return ("LookAround", affect, "passive_attention",
                selected.target_kind, selected.target_category, selected.intention)
    if isinstance(selected, MockSocialPlan):
        plans = {
            "silence": ("Chill", "quiet", "mock_social_silence"),
            "rest": ("Nap", "resting", "mock_social_rest"),
            "glance": ("LookAround", "curious", "mock_social_glance"),
            "chirp": ("Chill", "sociable", "mock_social_chirp"),
            "play_cue": ("BallPlay", "playful", "mock_social_play"),
        }
        state, affect, reason = plans[selected.kind]
        kind = "sound_label" if selected.kind == "chirp" else "object_label"
        return state, affect, reason, kind if selected.category else None, selected.category, selected.kind
    raise TypeError("use an existing F2 PassiveIntent or F4-C MockSocialPlan")


def describe_behavior(
    selected: PassiveIntent | MockSocialPlan, *,
    brain: AutonomyBrain,
    journal: PassiveObservationJournal,
    now_wall_epoch_s: float,
    learning: PassiveLearning | None = None,
    behavioral: BehavioralMemory | None = None,
) -> BehaviorPortrait:
    """Describe F2/F4's decision using ONLY the existing motivations and SQLite.

    The selected proposal is an input: this function never calls the F2
    arbitration a second time or appends a social cue. No extra writer or
    second cadence loop is permitted. Historical counts are mock-only.
    """
    from .autonomy import AutonomyBrain

    if not isinstance(brain, AutonomyBrain):
        raise TypeError("existing AutonomyBrain required")
    if not isinstance(journal, PassiveObservationJournal):
        raise TypeError("existing PassiveObservationJournal required")
    if brain.memory is not journal._memory:
        raise ValueError("brain and journal must share the same ExperienceMemory")
    if learning is not None:
        if not isinstance(learning, PassiveLearning):
            raise TypeError("existing PassiveLearning required")
        if learning._memory is not brain.memory:
            raise ValueError("learning must use the same ExperienceMemory")
    if behavioral is not None:
        if not isinstance(behavioral, BehavioralMemory):
            raise TypeError("existing F4-A BehavioralMemory required")
        if behavioral._memory is not brain.memory:
            raise ValueError("behavioral history must share the one ExperienceMemory")
    wall = _check_wall(now_wall_epoch_s)
    if not _valid_motivations(brain.motives):
        raise ValueError("invalid simulated motivation values")
    state, affect, reason, kind, category, intention = _interpret(selected)

    # Rest is F2's simulated motivation bookkeeping, not battery level.
    # Preserve the selected non-motor decision rather than re-arbitrate.
    motives = brain.motives
    drives = {
        "curiosity": motives.curiosity, "sociability": motives.sociability,
        "play": motives.play, "energy": 1.0 - motives.energy,
        "caution": motives.caution,
    }
    dominant = max(drives, key=drives.get)
    if state == "Chill" and affect == "calm" and motives.caution >= 0.75:
        affect = "watchful"

    familiarity, count, bias = "unknown", 0, 0.0
    result_bias, positive, negative, habit = 0.0, 0, 0, "neutral"
    try:
        if kind is not None and category is not None and category != "unknown":
            count = journal.category_count(kind, category, now_wall_epoch_s=wall)
            familiarity = ("new_category" if count == 0 else
                           "seen_once" if count == 1 else "familiar_category")
        if learning is not None:
            bias = float(learning.preference(intention))
        if behavioral is not None:
            # F4-A joins the original P2a mock evidence. Reopen/retract/prune
            # change this report without a duplicate personality ledger.
            summary = behavioral.summary(now_wall_epoch_s=wall)
            if not valid_mock_summary(summary):
                raise ValueError("not a historical, non-motor mock summary")
            result_bias = float(summary.bias)
            positive, negative = summary.positive, summary.negative
            if positive + negative >= MIN_HABIT_EVIDENCE:
                if result_bias >= MIN_HABIT_BIAS - 1e-12:
                    habit = "inspection_encouraged"
                elif result_bias <= -MIN_HABIT_BIAS + 1e-12:
                    habit = "inspection_reserved"
    except (sqlite3.Error, ValueError, OverflowError):
        # Missing or corrupted memory cannot manufacture familiarity or a
        # learned preference. Downgrade to a quiet, uninformative portrait.
        return BehaviorPortrait("Chill", "quiet", dominant,
                                "unavailable", 0, 0.0, "history_unavailable",
                                inspection_habit="unavailable")
    return BehaviorPortrait(state, affect, dominant, familiarity, count, bias,
                            reason, result_bias, positive, negative, habit)
