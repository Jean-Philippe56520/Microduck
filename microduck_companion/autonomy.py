"""Mostly-silent autonomous behavior planner. NO real motor commands.

A physical adapter must separately validate safety and supported robotd intents.
"""
from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import TYPE_CHECKING
from .episodic_memory import ExperienceMemory

if TYPE_CHECKING:
    from .perception import PerceptionSnapshot
    from .passive_sources import PassiveRead
    from .passive_memory import PassiveObservationJournal
    from .passive_intentions import PassiveIntent
    from .passive_rhythm import PassiveRhythmMetrics
    from .passive_learning import PassiveLearning
    from .behavioral_memory import BehavioralMemory
    from .experience_expectations import MockAttentionTrends


@dataclass(frozen=True)
class Scene:
    battery_pct: float = 100.0
    safe_area: bool = False
    floor_clear: bool = False
    obstacle_m: float | None = None
    person_visible: bool = False
    object_id: str | None = None
    object_label: str = "unknown"
    pc_connected: bool = False
    object_source: str = "sensor"
    environment: str = "legacy"  # Synthetic legacy path; never command motors.
    perception_valid: bool = True


@dataclass
class Motivations:
    curiosity: float = 0.75
    sociability: float = 0.55
    play: float = 0.60
    energy: float = 0.80
    caution: float = 0.35
    # DET-1: optional cognitive persistence; never physical permission.
    determination: float = 0.55

    def clamp(self) -> None:
        for key in ("curiosity", "sociability", "play", "energy",
                    "caution", "determination"):
            setattr(self, key, max(0.0, min(1.0, getattr(self, key))))


@dataclass(frozen=True)
class Plan:
    intention: str
    explanation: str
    target: str | None = None
    request_pc_analysis: bool = False


@dataclass(frozen=True)
class MockFocusHint:
    """One CURRENT fictional attention target, not a physical-object tracker.

    A track_id is an unverified, short-lived F1 fixture token; it is NEVER an
    identity, coordinate, pose, distance, motor intent or movement permission.
    No hint can certify a physical target or authorize an OEM action.
    """

    state: str
    current_track_id: str | None = None
    category: str | None = None
    reason: str = "no_current_focus"
    source: str = "mock_fixture_only"
    physical_identity_verified: bool = False
    location_verified: bool = False
    motor_commands_issued: int = 0

    def __post_init__(self) -> None:
        if (self.state not in {"new", "continued", "none"}
                or self.source != "mock_fixture_only"
                or self.physical_identity_verified is not False
                or self.location_verified is not False
                or type(self.motor_commands_issued) is not int
                or self.motor_commands_issued != 0
                or type(self.reason) is not str or not self.reason):
            raise ValueError("mock focus cannot certify identity, location or action")
        if self.state == "none":
            if self.current_track_id is not None or self.category is not None:
                raise ValueError("absent focus must not retain a track or category")
        elif (not isinstance(self.current_track_id, str)
              or not self.current_track_id.strip()
              or not isinstance(self.category, str) or not self.category.strip()):
            raise ValueError("current fixture focus requires a category and track")


def _check_det1_goal_memory(goals: object, memory: ExperienceMemory) -> None:
    """Check an already-instantiated optional MEM-1 object, without import.

    N5/N6's reviewed mock-free host probe deliberately excludes MEM-1.
    An optional user-supplied instance already has its defining module
    loaded. Read the class identity without importing/instantiating the
    fixture store during the default F2 path.
    """
    module = sys.modules.get("microduck_companion.mock_goal_memory")
    cls = getattr(module, "MockGoalMemory", None)
    if cls is None or type(goals) is not cls:
        raise TypeError("DET-1 requires a real MockGoalMemory instance")
    if goals._memory is not memory:
        raise ValueError("DET-1 goal memory must share ExperienceMemory")


class AutonomyBrain:
    def __init__(self, memory: ExperienceMemory,
                 motivations: Motivations | None = None) -> None:
        self.memory = memory
        self.motives = motivations or Motivations()
        self.motives.clamp()
        self.previous_intention: str | None = None
        # F2-B state is process-local, lazy and strictly cognitive. It never
        # replaces the existing robot safety path or SQLite memory.
        self._passive_rhythm = None
        # PD2 only remembers post-decision MOCK descriptive inertia locally.
        # It is not a second brain, a daemon, or durable mood history.
        self._behavior_continuity = None
        # VIS-FOCUS-A1: one RAM-only fixture interest; no matcher, position,
        # persistence, additional decision loop or OEM permission.
        self._mock_focus: tuple[str, str] | None = None
        self._mock_focus_sequence: int | None = None
        self._mock_focus_time: float | None = None

    def propose_passive(self, reading: PassiveRead, *,
                        journal: PassiveObservationJournal,
                        now_monotonic_s: float,
                        now_wall_epoch_s: float) -> PassiveIntent:
        """F2-A: propose attention without acting, speaking or requesting PC.

        This is deliberately independent of the existing motion safety gate
        in choose_from_snapshot(). The *same* local SQLite must be used for
        the brain and category journal. A proposal is NOT an executed action
        or a robotd command; callers must never treat it as motor permission.
        """
        from .passive_intentions import propose_passive_intention
        from .passive_memory import PassiveObservationJournal

        if not isinstance(journal, PassiveObservationJournal):
            raise TypeError("a passive journal is required")
        if journal._memory is not self.memory:
            raise ValueError("brain and passive journal must share SQLite")
        return propose_passive_intention(
            reading, journal=journal, motivations=self.motives,
            now_monotonic_s=now_monotonic_s,
            now_wall_epoch_s=now_wall_epoch_s,
        )

    def propose_balanced_passive(self, reading: PassiveRead, *,
                                 journal: PassiveObservationJournal,
                                 now_monotonic_s: float,
                                 now_wall_epoch_s: float,
                                 learning: PassiveLearning | None = None,
                                 behavioral: BehavioralMemory | None = None,
                                 expectations: MockAttentionTrends | None = None,
                                 goals: object | None = None,
                                 guard_attempted_goals: bool = False,
                                 personality_pacing: bool = False) -> PassiveIntent:
        """F2-B/F2-C: pace non-motor proposals; optional mock-only bias.

        Reuses F2-A provenance checking and the same ExperienceMemory journal.
        Only the simulated motivation-energy variable is advanced per valid
        passive cycle; neither battery nor verified physical outcomes exist.
        """
        from .passive_rhythm import PassiveRhythm
        from .passive_memory import PassiveObservationJournal
        from .passive_learning import PassiveLearning
        from .behavioral_memory import BehavioralMemory
        from .experience_expectations import MockAttentionTrends

        if type(guard_attempted_goals) is not bool or type(personality_pacing) is not bool:
            raise TypeError("DET-2 / PER-1 options must be explicit booleans")
        if guard_attempted_goals and goals is None:
            raise ValueError("DET-2 requires the existing mock goal memory")
        if goals is not None:
            _check_det1_goal_memory(goals, self.memory)

        if not isinstance(journal, PassiveObservationJournal):
            raise TypeError("a passive journal is required")
        if journal._memory is not self.memory:
            raise ValueError("brain and passive journal must share SQLite")
        if learning is not None:
            if not isinstance(learning, PassiveLearning):
                raise TypeError("F2-C learning must be PassiveLearning")
            if learning._memory is not self.memory:
                raise ValueError("F2-C learning must share the brain SQLite")
        if behavioral is not None:
            if not isinstance(behavioral, BehavioralMemory):
                raise TypeError("F4-A behavioral memory must be BehavioralMemory")
            if behavioral._memory is not self.memory:
                raise ValueError("F4-A must share the same ExperienceMemory")
        if expectations is not None:
            if not isinstance(expectations, MockAttentionTrends):
                raise TypeError("EX3 hints require existing MockAttentionTrends")
            if expectations._memory is not self.memory:
                raise ValueError("EX3 must share the brain ExperienceMemory")
        if self._passive_rhythm is None:
            self._passive_rhythm = PassiveRhythm()
        return self._passive_rhythm.tick(
            reading, journal=journal, motivations=self.motives,
            now_monotonic_s=now_monotonic_s,
            now_wall_epoch_s=now_wall_epoch_s, learning=learning,
            behavioral=behavioral, expectations=expectations, goals=goals,
            guard_attempted_goals=guard_attempted_goals,
            personality_pacing=personality_pacing,
        )

    def describe_mock_visual_focus(self, reading: PassiveRead, selected,
                                   *, now_monotonic_s: float) -> MockFocusHint:
        """Describe at most one F1 fixture token AFTER the existing F2 choice.

        F2 alone chooses whether the category merits attention, considering
        its existing motivations and optional ONE-SQLite hints. This method
        only disambiguates current mock tokens of that chosen category. It
        never estimates geometry, associates different IDs or retries actions.
        No last-known target is returned when its current observation is lost.
        Reuse after cooldown is a description, not a repeated F2 proposal.
        """
        import math
        from .passive_intentions import PassiveIntent
        from .passive_observations import PASSIVE_KINDS, summarize_passive
        from .passive_sources import PassiveRead
        from .perception import PerceptionSnapshot

        if not isinstance(reading, PassiveRead) or not isinstance(selected, PassiveIntent):
            raise TypeError("mock focus requires F1 PassiveRead and F2 PassiveIntent")
        if (type(now_monotonic_s) not in (float, int)
                or not math.isfinite(now_monotonic_s) or now_monotonic_s < 0):
            raise ValueError("mock focus time must be monotonic and finite")
        now = float(now_monotonic_s)

        def clear(reason: str) -> MockFocusHint:
            self._mock_focus = None
            return MockFocusHint("none", reason=reason)

        if self._mock_focus_time is not None and now < self._mock_focus_time:
            # An old monotonic epoch cannot inherit a previous fixture token.
            self._mock_focus_sequence = None
            self._mock_focus_time = now
            return clear("clock_reset_requires_new_observation")
        if (reading.status != "ok" or reading.channel != "mock_fixture_unix"
                or type(reading.sequence) is not int
                or not 0 <= reading.sequence < 2**63
                or not isinstance(reading.snapshot, PerceptionSnapshot)
                or reading.snapshot.environment != "mock"):
            return clear("unavailable_or_untrusted_fixture")
        if (self._mock_focus_sequence is not None
                and reading.sequence <= self._mock_focus_sequence):
            return clear("duplicate_or_out_of_order_fixture")
        self._mock_focus_sequence = reading.sequence
        self._mock_focus_time = now
        if any(event.kind not in PASSIVE_KINDS or event.source != "mock"
               for event in reading.snapshot.events):
            return clear("untrusted_or_nonpassive_event")
        try:
            observations = summarize_passive(reading.snapshot, now=now)
        except (TypeError, ValueError):
            return clear("invalid_observation_batch")
        if any(obs.claimed_source != "mock" or obs.status in {
                "future", "stale", "untrusted"} for obs in observations):
            return clear("untrusted_or_expired_observation")
        if selected.intention == "idle":
            # Continue only an explicitly CURRENT identical fixture token.
            # F2's cooldown is not a command to turn or an identity proof.
            if (selected.reason not in {
                    "no_high_scoring_passive_attention",
                    "no_new_safe_passive_attention"}
                    or self._mock_focus is None):
                return clear("no_admissible_current_interest")
            matches = [obs for obs in observations
                       if obs.kind == "object_label" and obs.usable_category
                       and (obs.track_id, obs.category) == self._mock_focus]
            if len(matches) != 1:
                return clear("original_current_track_missing_or_uncertain")
            return MockFocusHint("continued", self._mock_focus[0],
                                 self._mock_focus[1],
                                 "same_fresh_fixture_track_during_f2_idle")
        if (selected.intention not in {"observe", "inspect"}
                or selected.target_kind != "object_label"):
            return clear("f2_did_not_select_an_object")
        candidates = [obs for obs in observations
                      if obs.kind == "object_label" and obs.track_id is not None
                      and obs.category == selected.target_category
                      and (obs.usable_category or
                           (selected.intention == "inspect"
                            and obs.status == "unknown"))]
        if not candidates:
            # In particular: a conflicting class cannot become a target.
            return clear("selected_category_not_currently_resolved")
        previous = self._mock_focus
        # Prefer the exact token still present. Never equate two distinct
        # tokens just because both say "ball", "person" or "unknown".
        same = [obs for obs in candidates
                if (obs.track_id, obs.category) == previous]
        chosen = same[0] if same else min(
            candidates, key=lambda obs:
            (-obs.confidence, -obs.observed_at, obs.track_id))
        self._mock_focus = (chosen.track_id, chosen.category)
        continuity = previous == self._mock_focus
        return MockFocusHint(
            "continued" if continuity else "new",
            chosen.track_id, chosen.category,
            "same_fresh_fixture_track" if continuity else "fresh_fixture_interest",
        )

    def passive_rhythm_metrics(self) -> PassiveRhythmMetrics:
        """F2-B: counted proposals only, not executed actions or power use."""
        from .passive_rhythm import PassiveRhythm

        if self._passive_rhythm is None:
            self._passive_rhythm = PassiveRhythm()
        return self._passive_rhythm.metrics(self.motives)

    def describe_behavior(self, selected, *, journal: PassiveObservationJournal,
                          now_wall_epoch_s: float,
                          learning: PassiveLearning | None = None,
                          behavioral: BehavioralMemory | None = None):
        """Read-only 16-state OEM-inspired personality PORTRAIT after F2/F4.

        Does not re-run arbitration, update motivation, write SQLite, or
        issue actions. Only a few historical states have mock descriptions;
        no 16-state physical skill engine is claimed or installed.
        """
        from .behavior_personality import describe_behavior
        return describe_behavior(
            selected, brain=self, journal=journal,
            now_wall_epoch_s=now_wall_epoch_s, learning=learning,
            behavioral=behavioral,
        )

    def describe_behavior_continuity(self, portrait, *, situation,
                                     now_monotonic_s: float, hint=None,
                                     hint_evaluated_monotonic_s=None):
        """PD2: describe fictional OEM state continuity AFTER the F2 decision.

        Existing brain owns one tiny process-local continuity object. P-A/B
        portrait and P-C cue are reused. No second action scheduler, SQLite
        writing, robotd call, camera/speaker or Qwen.
        """
        from .behavior_continuity import MockBehaviorContinuity

        if self._behavior_continuity is None:
            self._behavior_continuity = MockBehaviorContinuity()
        return self._behavior_continuity.describe(
            portrait, motivations=self.motives,
            situation=situation, now_monotonic_s=now_monotonic_s, hint=hint,
            hint_evaluated_monotonic_s=hint_evaluated_monotonic_s,
        )

    def describe_oem_expression(self, portrait, *, cue, context, conditions,
                                now_monotonic_s: float):
        """P-C: read-only contextual OEM hint after an existing P-A/B portrait.

        This does not tick a second scheduler, read a microphone, issue a
        sound/motor action, change motivations or write into ExperienceMemory.
        """
        from .oem_expression_hints import describe_oem_expression
        return describe_oem_expression(
            portrait, cue=cue, context=context, conditions=conditions,
            now_monotonic_s=now_monotonic_s,
        )

    def consider_simulator_status(self, *, quality: str,
                                  battery_pct: float | None,
                                  prior_battery_low: bool | None,
                                  comparable_memory: bool) -> str:
        """Non-motor attention hint for P2b/X2-B, not an action proposal.

        Accepts only the simulator's *current* validated battery and a coarse
        historical band. No other state is inferred from ToF or remembered
        data. All return values describe attention, not OEM RPCs, a completed
        rest, energy recovery, a perception category or causal learning.
        This pure method deliberately does not modify the five motivations.
        """
        if quality != "coherent" or battery_pct is None:
            return "abstain"
        if (type(battery_pct) not in (int, float)
                or not 0 <= battery_pct <= 100):
            return "abstain"
        if battery_pct <= 15:
            return "rest"
        if (comparable_memory and prior_battery_low is True
                and self.motives.curiosity > self.motives.caution
                and self.motives.energy >= 0.3):
            return "observe_status"
        return "idle"

    def choose_from_snapshot(self, snapshot: PerceptionSnapshot,
                             now: float | None = None) -> Plan:
        """Production-facing input boundary; stale/untrusted safety data halts.

        This is still a prototype and never authorizes physical motor actions.
        choose(Scene(...)) remains available for existing synthetic tests.
        """
        return self.choose(snapshot.to_scene(now=now))

    def choose(self, scene: Scene) -> Plan:
        if not 0 <= scene.battery_pct <= 100:
            raise ValueError("battery_pct must be in [0, 100]")
        if scene.obstacle_m is not None and scene.obstacle_m < 0:
            raise ValueError("obstacle distance cannot be negative")
        if scene.battery_pct <= 15:
            return self._record(Plan("rest", "Battery low: do not explore"))
        if not scene.perception_valid:
            return self._record(Plan("halt", "Required perception data is missing or uncertain"))
        if not scene.safe_area or not scene.floor_clear:
            return self._record(Plan("halt", "Safe area or floor not verified"))
        if scene.obstacle_m is not None and scene.obstacle_m < 0.35:
            return self._record(Plan("halt", "Obstacle in safety margin"))

        obj = None
        if scene.object_id:
            obj = self.memory.observe(
                scene.object_id, scene.object_label, source=scene.object_source
            )
        scores = {
            "idle": 0.12,
            "rest": (1 - self.motives.energy) * 1.35,
            "explore": self.motives.curiosity * self.motives.energy * 0.72
                       - self.motives.caution * 0.28,
        }
        # Only verified MuJoCo consequences can bias the simulator's choice.
        # The physical robot and the synthetic legacy demo are unaffected.
        # The adjustment is gradual and can eventually favor idle over
        # repeated unsuccessful exploratory attempts.
        if scene.environment == "simulator":
            scores["explore"] += 0.60 * self.memory.intent_preference(
                "simulator", "explore"
            )
        if scene.person_visible:
            scores["look_at_person"] = self.motives.sociability * 0.94 + 0.20
        if obj is not None:
            novelty = 1 / (1 + 0.65 * (obj.sightings - 1))
            scores["inspect_object"] = (
                self.motives.curiosity * (0.35 + 0.72 * novelty)
                - self.motives.caution * 0.12
            )
            # A model guess cannot authorize a physical play action.
            valid_sources = {
                "legacy": {"sensor"}, "robot": {"sensor"},
                "simulator": {"simulator"}, "mock": {"mock"},
            }
            if (obj.label in {"ball", "toy"}
                    and scene.object_label == obj.label
                    and obj.label_source in (
                        valid_sources.get(scene.environment, set())
                    )):
                scores["play_with_object"] = (
                    self.motives.play * 0.75 + obj.preference * 0.55
                    + min(obj.sightings, 4) * 0.055
                )
        if self.previous_intention in scores:
            scores[self.previous_intention] -= 0.08
        intent = max(scores, key=scores.get)
        request = bool(
            intent == "inspect_object" and obj is not None
            and obj.label == "unknown" and scene.pc_connected
            and self.memory.ask_analysis_once(obj.identifier)
        )
        reasons = {
            "idle": "Observe quietly",
            "rest": "Recover simulated activity energy",
            "explore": "Curiosity outweighs familiarity",
            "look_at_person": "Attend to a person without speaking",
            "inspect_object": "Novel object deserves closer observation",
            "play_with_object": "Known safe toy with learned preference",
        }
        return self._record(Plan(intent, reasons[intent],
                                 obj.identifier if obj else None, request))

    def feedback(self, object_id: str, action: str, reward: float) -> float:
        """Legacy entry point: an intention without execution proof is NOT learned.

        ExperienceMemory rejects all unverified positive or negative feedback.
        Do not change motivations on this rejected path. The separate P2a
        mock and MuJoCo trials retain their own explicit provenance.
        """
        return self.memory.learn_from_outcome(object_id, action, reward)

    def _record(self, plan: Plan) -> Plan:
        # This legacy selector has NO authenticated execution receipt. Keep
        # the proposal process-local; a chosen action must never be persisted
        # as if it was an experience. P2a and MuJoCo have separate, explicitly
        # sourced recorders that are NOT physical robot execution evidence.
        self.previous_intention = plan.intention
        # A proposed rest did not recharge a battery or restore energy; a
        # proposed exploration did not expend energy. Only proven, executed
        # outcomes may update motivations in a future audited path.
        return plan
