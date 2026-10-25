"""Microduck Companion: experimental local autonomy, not a motor controller."""
from .autonomy import AutonomyBrain, Motivations, Plan, Scene
from .episodic_memory import ExperienceMemory
from .perception import PerceptionEvent, PerceptionSnapshot
from .passive_observations import PassiveObservation, summarize_passive
from .passive_memory import PassiveMemoryEntry, PassiveObservationJournal

__all__ = [
    "AutonomyBrain", "Motivations", "Plan", "Scene", "ExperienceMemory",
    "PerceptionEvent", "PerceptionSnapshot",
    "PassiveObservation", "summarize_passive",
    "PassiveMemoryEntry", "PassiveObservationJournal",
]
