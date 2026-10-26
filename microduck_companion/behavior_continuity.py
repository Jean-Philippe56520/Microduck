"""PD2: stable, MOCK-ONLY portrayal of historical OEM behaviors.

This is a post-F2/F4 expression *description*, not a behavior selector that
commands the robot. P-A's existing portrait remains the only base state and
PD1's catalogue remains the authority on available OEM expressions. An
explicit, fictional situation may nominate a historical label; an unported
label is never a motor command, sound, sensor fact or PC/Qwen request.

PD2 is process-local. The existing corrected SQLite memory can influence the
P-A portrait, but short-lived mood/cooldown state is NOT persisted across boots.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

from .autonomy import Motivations
from .behavior_personality import (
    BehaviorPortrait, DESCRIPTIVE_ONLY, HISTORICAL_OEM_STATES,
    expression_capability_for, inspect_expression_capability,
)
from .oem_expression_hints import MockExpressionHint, MockOemConditions
from .passive_intentions import _valid_motivations

MAX_FIXTURE_CUE_AGE_S = 1.5
MIN_MOCK_EXPRESSION_DWELL_S = 2.0
REENTRY_COOLDOWN_S = 8.0
_SOURCE = "mock_post_decision_continuity_only"
_CUE_SOURCE = "mock_expression_situation_only"

# These cues are declared scene labels for tests, NOT sensors. In particular,
# nobody has proved a new-space map, rhythmic music classification, a held
# event, a sneeze detector, a safe floor or a way to pick up objects.
_CUE_STATES = {
    "new_space": "Wander",
    "viewpoint_ambiguity": "TurnInPlace",
    "play_burst": "Zoomies",
    "after_rest": "Stretch",
    "social_settle": "Ruffle",
    "quiet_grooming": "Preen",
    "sneeze_like": "Sneeze",
    "rhythm_pattern": "Dance",
    "floor_object": "GroundPick",
    "held_like": "Held",
}
_CUES = frozenset({"none", *_CUE_STATES})
_REASONS = frozenset({
    "base_portrait", "contextual_mock_candidate",
    "ineligible_mock_context", "history_discourages_inspection",
    "minimum_dwell", "reentry_cooldown",
    "stale_or_future_mock_cue", "safety_or_stop",
    "clock_reset", "duplicate_cycle", "oem_owned_mock_hint",
    "unverified_mock_startle", "rest_preempts_expression",
})


def _finite_epoch(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class MockBehaviorSituation:
    """Optional, explicitly synthetic post-decision environmental context.

    Does not represent a fresh physical sensor receipt, safety clearance or
    permission for any gesture. 'none' has no timestamp. All other cues must
    be explicitly timestamped and are rejected when stale or in the future.
    """

    cue: str = "none"
    observed_monotonic_s: float | None = None
    conditions: MockOemConditions = field(default_factory=MockOemConditions)
    source: str = _CUE_SOURCE

    def __post_init__(self) -> None:
        if type(self.cue) is not str or self.cue not in _CUES:
            raise ValueError("unsupported synthetic behavior cue")
        if self.source != _CUE_SOURCE:
            raise ValueError("only fictional behavior situations are accepted")
        if not isinstance(self.conditions, MockOemConditions):
            raise TypeError("use the existing P-C mock safety conditions")
        if self.cue == "none":
            if self.observed_monotonic_s is not None:
                raise ValueError("a missing mock cue cannot claim a timestamp")
        elif not _finite_epoch(self.observed_monotonic_s):
            raise ValueError("a mock cue requires a finite monotonic time")


@dataclass(frozen=True)
class MockBehaviorDisposition:
    """A descriptive intention, never proof of the historical OEM state."""

    state: str
    base_state: str
    reason: str
    oem_expression_evidence: str
    companion_status: str
    source: str = _SOURCE
    executed: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0
    pc_requests_issued: int = 0
    memories_written: int = 0
    hardware_verified: bool = False
    physical_execution_authorized: bool = False

    def __post_init__(self) -> None:
        if (self.state not in HISTORICAL_OEM_STATES
                or self.base_state not in DESCRIPTIVE_ONLY
                or self.reason not in _REASONS
                or self.source != _SOURCE
                or type(self.executed) is not bool or self.executed
                or type(self.hardware_verified) is not bool or self.hardware_verified
                or type(self.physical_execution_authorized) is not bool
                or self.physical_execution_authorized
                or any(type(getattr(self, key)) is not int
                       or getattr(self, key) != 0 for key in (
                           "motor_commands_issued", "speaker_commands_issued",
                           "pc_requests_issued", "memories_written"))):
            raise ValueError("PD2 cannot authorize or pretend a real action")
        cap = expression_capability_for(self.state)
        if (self.oem_expression_evidence != cap.oem_expression_evidence
                or self.companion_status != cap.companion_status):
            raise ValueError("PD2 must reuse the exact PD1 capability evidence")


class MockBehaviorContinuity:
    """Small per-brain description inertia; NO second rhythm or actuator.

    update() must be called AFTER F2/F4 has proposed an intention and P-A/B
    has described it. F2's rest/idle priorities are never overridden to
    produce an executable action. There is no event loop, timer, I/O or SQLite.
    """

    def __init__(self) -> None:
        self._last_now: float | None = None
        self._last_base: str | None = None
        self._state: str | None = None
        self._since: float | None = None
        self._reentry_until: dict[str, float] = {}

    @staticmethod
    def _eligible(state: str, portrait: BehaviorPortrait,
                  motives: Motivations, previous: str | None) -> tuple[bool, str]:
        base = portrait.state
        if state in {"Wander", "TurnInPlace", "GroundPick"}:
            if portrait.inspection_habit == "inspection_reserved":
                return False, "history_discourages_inspection"
            if base != "LookAround" or portrait.reason != "passive_attention":
                return False, "ineligible_mock_context"
            if state == "Wander":
                allowed = (motives.curiosity >= .65 and motives.energy >= .5
                           and motives.caution <= .35)
            elif state == "TurnInPlace":
                allowed = (motives.curiosity >= .5 and motives.energy >= .35
                           and motives.caution <= .6)
            else:
                allowed = (portrait.familiarity in {
                    "new_category", "seen_once"}
                    and motives.curiosity >= .6 and motives.energy >= .5
                    and motives.caution <= .4)
            return allowed, ("contextual_mock_candidate" if allowed
                             else "ineligible_mock_context")
        if state in {"Zoomies", "Dance"}:
            if base != "BallPlay":
                return False, "ineligible_mock_context"
            if state == "Zoomies":
                allowed = (motives.play >= .85 and motives.energy >= .75
                           and motives.caution <= .25)
            else:
                allowed = (motives.play >= .7 and motives.energy >= .55
                           and motives.caution <= .45)
            return allowed, ("contextual_mock_candidate" if allowed
                             else "ineligible_mock_context")
        if base != "Chill":
            return False, "ineligible_mock_context"
        if state == "Stretch":
            allowed = previous == "Nap" and motives.energy >= .25
        elif state == "Ruffle":
            allowed = portrait.affect == "sociable" and motives.caution < .65
        elif state == "Preen":
            allowed = motives.energy >= .3 and motives.caution < .75
        elif state == "Sneeze":
            # Only an explicit *fictional label*, never a sneeze detector.
            allowed = True
        elif state == "Held":
            # Held was deprecated upstream: label only, not motor clearance.
            allowed = True
        else:
            raise ValueError("unmapped mock state")
        return allowed, ("contextual_mock_candidate" if allowed
                         else "ineligible_mock_context")

    @staticmethod
    def _result(state: str, base: str, reason: str) -> MockBehaviorDisposition:
        cap = expression_capability_for(state)
        return MockBehaviorDisposition(
            state=state, base_state=base, reason=reason,
            oem_expression_evidence=cap.oem_expression_evidence,
            companion_status=cap.companion_status,
        )

    def _apply(self, state: str, base: str, reason: str,
               now: float) -> MockBehaviorDisposition:
        if self._state is not None and state != self._state:
            if self._state not in DESCRIPTIVE_ONLY:
                self._reentry_until[self._state] = now + REENTRY_COOLDOWN_S
        if self._state != state or self._since is None:
            self._since = now
        self._state = state
        self._last_base = base
        self._last_now = now
        self._reentry_until = {
            key: end for key, end in self._reentry_until.items() if end > now
        }
        return self._result(state, base, reason)

    def describe(
        self, portrait: BehaviorPortrait, *, motivations: Motivations,
        situation: MockBehaviorSituation, now_monotonic_s: float,
        hint: MockExpressionHint | None = None,
    ) -> MockBehaviorDisposition:
        """Describe a previously chosen F2/F4 proposal with bounded inertia.

        A cue may nominate all ten otherwise unavailable names; P-C already
        supplies fictional Petted/Startle. None of the sixteen is dispatched.
        """
        if not isinstance(portrait, BehaviorPortrait):
            raise TypeError("PD2 requires a validated existing P-A portrait")
        if not isinstance(motivations, Motivations) or not _valid_motivations(motivations):
            raise ValueError("PD2 requires valid existing F2 motivations")
        if not isinstance(situation, MockBehaviorSituation):
            raise TypeError("PD2 needs a typed fictional context")
        if not _finite_epoch(now_monotonic_s):
            raise ValueError("PD2 needs a finite nonnegative monotonic clock")
        # Also reject a hint forged for an unrelated or modified portrait.
        cap = inspect_expression_capability(portrait, hint=hint)
        now = float(now_monotonic_s)
        base = portrait.state

        if self._last_now is not None and now < self._last_now:
            self._reentry_until.clear()
            self._state = None
            self._since = None
            return self._apply("Chill", base, "clock_reset", now)
        if self._last_now is not None and now == self._last_now:
            return self._result(
                self._state if self._state is not None else "Chill",
                self._last_base if self._last_base is not None else base,
                "duplicate_cycle",
            )

        if (situation.conditions.stop_requested or situation.conditions.fallen
                or situation.conditions.busy):
            self._reentry_until.clear()
            return self._apply("Chill", base, "safety_or_stop", now)

        # Rest is already decided by F2. A PD2 expression cannot replace it
        # with a playful state, petting or a motor-like historical label.
        if base == "Nap":
            return self._apply("Nap", base, "rest_preempts_expression", now)

        state = cap.state if hint is not None and hint.status in {
            "oem_owned", "hypothesis"} else base
        reason = (
            "oem_owned_mock_hint" if hint is not None and hint.status == "oem_owned"
            else "unverified_mock_startle" if (
                hint is not None and hint.status == "hypothesis")
            else "base_portrait"
        )
        urgent_hint = state in {"Petted", "Startle"}

        # OEM event interpretations take priority over arbitrary declared
        # cue labels, but even these are not proof of an executed expression.
        if not urgent_hint and situation.cue != "none":
            age = now - float(situation.observed_monotonic_s)
            if age < 0 or age > MAX_FIXTURE_CUE_AGE_S:
                reason = "stale_or_future_mock_cue"
            else:
                nominated = _CUE_STATES[situation.cue]
                eligible, reason = self._eligible(
                    nominated, portrait, motivations, self._state)
                if eligible:
                    state = nominated
        # Never hold a pending motor-like expression across a new F2 choice.
        # Ordinary descriptive transitions can be sticky *within the same*
        # already chosen F2/F4 base, not across a rest or attention switch.
        same_base = self._last_base == base
        if (self._state is not None and state != self._state and same_base
                and not urgent_hint and reason != "stale_or_future_mock_cue"
                and self._since is not None
                and now - self._since < MIN_MOCK_EXPRESSION_DWELL_S):
            state = self._state
            reason = "minimum_dwell"
        elif (state != self._state and state in self._reentry_until
              and self._reentry_until[state] > now and not urgent_hint):
            state = base
            reason = "reentry_cooldown"

        return self._apply(state, base, reason, now)
