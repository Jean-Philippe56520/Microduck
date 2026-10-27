"""Mostly-silent autonomous behavior planner. NO real motor commands.

A physical adapter must separately validate safety and supported robotd intents.
"""
from __future__ import annotations

from dataclasses import dataclass
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

    def clamp(self) -> None:
        for key in ("curiosity", "sociability", "play", "energy", "caution"):
            setattr(self, key, max(0.0, min(1.0, getattr(self, key))))


@dataclass(frozen=True)
class Plan:
    intention: str
    explanation: str
    target: str | None = None
    request_pc_analysis: bool = False


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
                                 expectations: MockAttentionTrends | None = None) -> PassiveIntent:
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
            behavioral=behavioral, expectations=expectations,
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
