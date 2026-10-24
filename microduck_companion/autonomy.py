"""Mostly-silent autonomous behavior planner. NO real motor commands.

A physical adapter must separately validate safety and supported robotd intents.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from .episodic_memory import ExperienceMemory

if TYPE_CHECKING:
    from .perception import PerceptionSnapshot


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
        preference = self.memory.learn_from_outcome(object_id, action, reward)
        self.motives.play = max(0.0, min(1.0, self.motives.play + 0.04 * reward))
        return preference

    def _record(self, plan: Plan) -> Plan:
        self.memory.record_action(plan.intention, plan.target, plan.explanation)
        self.previous_intention = plan.intention
        if plan.intention == "rest":
            self.motives.energy = min(1.0, self.motives.energy + 0.025)
        elif plan.intention not in {"halt", "idle"}:
            self.motives.energy = max(0.0, self.motives.energy - 0.008)
        return plan
