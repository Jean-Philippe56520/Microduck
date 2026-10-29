"""MEM-2: bounded read-only recall from the ONE ExperienceMemory SQLite.

This is an interpretive view over F0, C1/C2 and optional MEM-1 mock goals,
not a second writer, instance recognizer, live sensor or Qwen bridge.
The F0 object counter and F4 category history have NO verified join key;
return them separately rather than treating them as the same physical object.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import TYPE_CHECKING

from .category_semantics import CategorySemantics
from .episodic_memory import ExperienceMemory
from .memory_consolidation import ConservativeCategoryRecall, recall_category
from .passive_memory import _check_wall
from .passive_observations import OBJECT_CATEGORIES

if TYPE_CHECKING:
    from .mock_goal_memory import MockGoalMemory
    from .multiview_pattern_memory import MultiviewPatternMemory, MultiviewEncounter

_OBJECT_KEY = re.compile(r"o-[0-9a-f]{16}\Z")
MAX_RECALLED_GOALS = 8
GOAL_MAX_AGE_S = 14 * 24 * 3600  # fixture-only study gate


@dataclass(frozen=True)
class LegacyObjectCounter:
    """Calls to F0.observe, NOT independent encounters or verified identity."""

    sightings: int
    label_claim: str
    label_source: str
    last_seen_epoch_s: float
    identity_verified: bool = False
    independent_encounters_verified: int = 0


@dataclass(frozen=True)
class MockGoalReminder:
    """A category-level mock objective; never linked to the F0 object."""

    goal_ref: str
    kind: str
    state: str
    resume_when: str
    linked_attempts: int
    unavailable_attempts: int
    provenance: str = "mock_fixture_only"
    physical_completion_verified: bool = False


@dataclass(frozen=True)
class MemoryRecall:
    """Historical and explicitly uncertain context, not a Qwen request."""

    category: str
    category_history: ConservativeCategoryRecall
    object_counter: LegacyObjectCounter | None
    category_goals: tuple[MockGoalReminder, ...]
    goals_truncated: bool
    multiview_hint: MultiviewEncounter | None = None
    unverified_context_only: bool = True
    same_physical_object_verified: bool = False
    independent_encounters_verified: int = 0
    physical_effects_verified: int = 0
    qwen_requests: int = 0
    motor_commands_issued: int = 0
    memory_writes: int = 0


def recall_memory(
    memory: ExperienceMemory, semantics: CategorySemantics, *,
    category: str, now_wall_epoch_s: float,
    object_key: str | None = None, goals: MockGoalMemory | None = None,
    multiview: MultiviewPatternMemory | None = None, gray8: bytes | None = None,
) -> MemoryRecall:
    """Return existing evidence, with corrections applied by C1/C2.

    Category history is intentionally NOT attached to an F0 object key.
    The optional object key is opaque and used only in a parameterized read.
    M1-B appearance similarity is deliberately not accepted as identity.
    Existing goal/EX1 rows are referred to, never duplicated or rewarded.
    A missing optional schema fails closed instead of creating it here.
    """
    if not isinstance(memory, ExperienceMemory):
        raise TypeError("existing ExperienceMemory required")
    if not isinstance(semantics, CategorySemantics) or semantics._memory is not memory:
        raise ValueError("F4-A must share the same ExperienceMemory")
    if type(category) is not str or category not in OBJECT_CATEGORIES:
        raise ValueError("unsupported public object category")
    now = _check_wall(now_wall_epoch_s)
    if object_key is not None and (
        type(object_key) is not str or _OBJECT_KEY.fullmatch(object_key) is None
    ):
        raise ValueError("only an opaque fixture object key is accepted")
    if (multiview is None) != (gray8 is None):
        raise ValueError("paired M1-B store and fixture image required")
    hint = None
    if multiview is not None:
        from .multiview_pattern_memory import MultiviewPatternMemory
        if (not isinstance(multiview, MultiviewPatternMemory)
                or multiview.memory is not memory):
            raise ValueError("M1-B must share the single ExperienceMemory")
        # Category vocabularies differ; do not promote an 'object' pattern
        # into a ball/ chair category or fingerprint people.
        if category not in ("unknown", "cat", "dog"):
            raise ValueError("no proven common image category for MEM-2B")
        hint = multiview.probe_image(
            gray8, category=category, now_wall_epoch_s=now)
    if goals is not None:
        # The optional mock goal module is intentionally not imported unless
        # needed; host production closures must not acquire mock components.
        from .mock_goal_memory import MockGoalMemory
        if not isinstance(goals, MockGoalMemory) or goals._memory is not memory:
            raise ValueError("MEM-1 must share the same ExperienceMemory")

    history = recall_category(
        semantics, category=category, now_wall_epoch_s=now,
    )
    counter = None
    if object_key is not None:
        row = memory.conn.execute("""
            SELECT label,label_source,sightings,last_seen
            FROM objects WHERE identifier=?
        """, (object_key,)).fetchone()
        if row is not None:
            seen, last_seen = row["sightings"], row["last_seen"]
            if (type(seen) is not int or seen < 1
                    or type(last_seen) not in (int, float)
                    or not math.isfinite(last_seen)
                    or not 0 <= last_seen <= now):
                raise ValueError("untrusted legacy object counter")
            source = row["label_source"]
            if source not in {"unknown", "sensor", "simulator", "mock", "llm_suggestion"}:
                raise ValueError("untrusted legacy label provenance")
            claim = row["label"]
            counter = LegacyObjectCounter(
                sightings=seen,
                label_claim=claim if claim in OBJECT_CATEGORIES else "unknown",
                label_source=source,
                last_seen_epoch_s=float(last_seen),
            )

    reminders: list[MockGoalReminder] = []
    truncated = False
    if goals is not None:
        from .mock_goal_memory import MAX_GOALS
        # MEM-1 caps the entire table, not per category. Scan the full cap.
        for goal in goals.recent(limit=MAX_GOALS):
            if (goal.category != category or goal.corrected or
                    goal.state not in {"candidate", "active", "suspended"}):
                continue
            if (not 0 <= goal.created_at_epoch_s <= goal.updated_at_epoch_s <= now
                    or now - goal.updated_at_epoch_s > GOAL_MAX_AGE_S):
                continue
            if len(reminders) == MAX_RECALLED_GOALS:
                truncated = True
                break
            attempts = goals.attempts(goal.goal_id)
            reminders.append(MockGoalReminder(
                goal_ref=goal.goal_id, kind=goal.kind, state=goal.state,
                resume_when=goal.resume_when,
                linked_attempts=len(attempts),
                unavailable_attempts=sum(
                    a.evidence_state != "active_mock_ex1" for a in attempts
                ),
            ))

    return MemoryRecall(
        category=category, category_history=history,
        object_counter=counter, category_goals=tuple(reminders),
        goals_truncated=truncated, multiview_hint=hint,
    )
