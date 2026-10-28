"""C1: read-only, conservative recall across F4-A MOCK fixture sessions.

Reuse the SAME ExperienceMemory SQLite. Only the F4-A categories backed by
*still-active* F1-C/F2-C rows are aggregated; repeated observations in one
fixture session do not become claims about independent scenes or individuals.
LLM-like property hypotheses remain separate, unverified and reversible.

No schema, writer, model, camera, robotd, motor or belief/reward updates.
No signatures from M1-B are promoted to object identities.
"""
from __future__ import annotations

from dataclasses import dataclass

from .category_semantics import (
    CategorySemantics, HYPOTHESIS_CATEGORIES, MAX_SEMANTIC_ROWS,
    PropertyHypothesis, RETENTION_S, _confidence,
)
from .passive_memory import _check_wall
from .passive_observations import OBJECT_CATEGORIES
from .perception import _SOUND_CATEGORIES

# Contradictions are disagreements between *unverified hypotheses*, not facts.
_OPPOSITES = {
    "texture": frozenset({"soft", "hard"}),
    "movement": frozenset({"moving", "stationary"}),
    "affordance": frozenset({"playable", "not_playable"}),
}


@dataclass(frozen=True)
class MockEvidenceSummary:
    modality: str
    observation_count: int
    fixture_session_count: int
    most_recent_epoch_s: float
    minimum_reported_confidence: float
    maximum_reported_confidence: float
    provenance: str = "mock_fixture_journal"
    independent_scenes_verified: int = 0
    real_sensor_verified: bool = False


@dataclass(frozen=True)
class ConservativeCategoryRecall:
    """Descriptive history, NEVER a safe-action or semantic-truth certificate."""

    category: str
    evidence: tuple[MockEvidenceSummary, ...]
    property_hypotheses: tuple[PropertyHypothesis, ...]
    conflicting_hypothesis_properties: tuple[str, ...]
    status: str  # historical_mock_only / hypotheses_only / unknown
    historical_only: bool = True
    verified_real_observations: int = 0
    causal_effects_verified: int = 0
    physical_actions_authorized: bool = False
    motor_commands_issued: int = 0
    memory_writes: int = 0


def recall_category(
    semantics: CategorySemantics, *, category: str,
    now_wall_epoch_s: float,
) -> ConservativeCategoryRecall:
    """Aggregate a bounded history without creating a persistent summary.

    A session identifier is merely a journal instance. It is NOT an
    independently captured scene, a physical track, or an object identity.
    Any correction, source retraction, source deletion, or TTL expiry removes
    a historic row from the very next query. A category may have hypotheses
    *without* any observed category at all.
    """
    if not isinstance(semantics, CategorySemantics):
        raise TypeError("existing F4-A CategorySemantics required")
    if type(category) is not str or category not in OBJECT_CATEGORIES | _SOUND_CATEGORIES:
        raise ValueError("category outside the OEM-aligned passive vocabulary")
    now = _check_wall(now_wall_epoch_s)
    c = semantics._memory.conn
    # Use the same provenance and correction joins as CategorySemantics.recall.
    # Unlike its ordinary recent(<=50) recall, this summary scans the whole
    # bounded F4-A cap (256 rows) so repeated historic entries cannot be
    # silently left out of the denominator.
    rows = c.execute("""
        SELECT s.kind,s.reported_confidence,s.recorded_epoch_s,
               j.session_id,j.sequence
        FROM f4a_semantic_categories s
        JOIN passive_observation_log j ON j.id=s.observation_id
        JOIN passive_learning_events l ON l.observation_id=s.observation_id
        WHERE s.active=1 AND l.active=1
          AND s.source='mock_fixture_journal'
          AND j.source='mock' AND j.channel='mock_fixture_unix'
          AND j.status='identified'
          AND s.category=j.category AND s.kind=j.kind
          AND s.reported_confidence=j.confidence
          AND s.recorded_epoch_s=j.recorded_epoch_s
          AND l.outcome IN ('new_information','repeated_observation')
          AND s.category=? AND s.recorded_epoch_s BETWEEN ? AND ?
        ORDER BY s.recorded_epoch_s DESC,s.observation_id DESC
        LIMIT ?
    """, (category, now-RETENTION_S, now, MAX_SEMANTIC_ROWS+1)).fetchall()
    if len(rows) > MAX_SEMANTIC_ROWS:
        raise ValueError("semantic row cap exceeded; refuse incomplete recall")

    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        modality = ("visual_label" if row["kind"] == "object_label"
                    else "sound_label" if row["kind"] == "sound_label"
                    else None)
        if modality is None:
            raise ValueError("unsupported persisted observation kind")
        confidence = _confidence(row["reported_confidence"])
        if type(row["session_id"]) is not str or not row["session_id"]:
            raise ValueError("invalid historical fixture session")
        item = grouped.get(modality)
        if item is None:
            item = {"count": 0, "sessions": set(),
                    "recent": float(row["recorded_epoch_s"]),
                    "lo": confidence, "hi": confidence}
            grouped[modality] = item
        item["count"] += 1
        item["sessions"].add(row["session_id"])
        item["lo"] = min(item["lo"], confidence)
        item["hi"] = max(item["hi"], confidence)

    evidence = tuple(
        MockEvidenceSummary(
            modality=modality, observation_count=int(item["count"]),
            fixture_session_count=len(item["sessions"]),
            most_recent_epoch_s=float(item["recent"]),
            minimum_reported_confidence=float(item["lo"]),
            maximum_reported_confidence=float(item["hi"]),
        )
        for modality, item in sorted(grouped.items())
    )

    # Query the EXISTING property-hypothesis table; do not join with the
    # historic count or promote confidence to verified sensory meaning.
    hypotheses = (semantics.hypotheses(
        category=category, now_wall_epoch_s=now)
        if category in HYPOTHESIS_CATEGORIES else ())
    by_property: dict[str, set[str]] = {}
    for hyp in hypotheses:
        by_property.setdefault(hyp.property, set()).add(hyp.value)
    conflicts = tuple(sorted(
        prop for prop, opposite in _OPPOSITES.items()
        if opposite.issubset(by_property.get(prop, set()))
    ))
    status = ("historical_mock_only" if evidence else
              "hypotheses_only" if hypotheses else "unknown")
    return ConservativeCategoryRecall(
        category=category, evidence=evidence,
        property_hypotheses=hypotheses,
        conflicting_hypothesis_properties=conflicts,
        status=status,
    )
