"""F4-A: persistent mock-category semantics, separate from hypotheses.

The existing ExperienceMemory SQLite and F1-C/F2-C observation ledger are
the ONLY inputs for recorded categories. A journalled label is a historical
MOCK claim, not a real object, an individual, a sensor authentication, or
a physical affordance. F2-C retractions and F1-C pruning invalidate recall.

Property hypotheses are fictional, restricted to public category vocabulary,
and NEVER promoted to observations. No image/audio, private name, position,
track ID, motor action, LLM call, or real person identity is stored here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3

from .episodic_memory import ExperienceMemory
from .passive_learning import PassiveLearning, MAX_CONSEQUENCE_AGE_S
from .passive_memory import PassiveObservationJournal, _check_wall
from .passive_observations import OBJECT_CATEGORIES
from .perception import _SOUND_CATEGORIES

RETENTION_S = 14 * 24 * 3600
MAX_SEMANTIC_ROWS = 256
MAX_HYPOTHESES = 64
# A finite, public vocabulary makes existing F4-A hypothesis rows sufficient
# as durable correction markers. Six categories * nine property/value pairs
# currently fit within the existing 64-row cap. Do not expand the vocabulary
# beyond the cap without a separate migration and retention audit.
MAX_QUERY = 50
PROPERTIES = {
    "texture": frozenset({"soft", "hard", "unknown"}),
    "movement": frozenset({"moving", "stationary", "unknown"}),
    "affordance": frozenset({"playable", "not_playable", "unknown"}),
}
# 'person' is deliberately excluded: no identity or biometrics in this phase.
HYPOTHESIS_CATEGORIES = frozenset(
    c for c in OBJECT_CATEGORIES if c not in {"person", "unknown"}
)
CORRECTION_REASONS = frozenset({"fixture_annotation_error", "source_retracted"})
MAX_HYPOTHESIS_KEYS = len(HYPOTHESIS_CATEGORIES) * sum(
    len(values) for values in PROPERTIES.values()
)


@dataclass(frozen=True)
class HistoricalCategory:
    category: str
    modality: str
    reported_confidence: float
    observation_id: int
    recorded_epoch_s: float
    source: str = "mock_fixture_journal"
    historical_only: bool = True
    real_sensor_verified: bool = False
    motor_commands_issued: int = 0


@dataclass(frozen=True)
class PropertyHypothesis:
    id: int
    category: str
    property: str
    value: str
    proposed_confidence: float
    source: str = "fictional_llm_hypothesis_only"
    confirmed: bool = False
    can_authorize_actions: bool = False


def _confidence(value: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("reported confidence must be finite in [0,1]")
    return float(value)


class CategorySemantics:
    """Two separate F4-A tables in the existing database, never another DB."""

    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("requires existing ExperienceMemory")
        self._memory = memory
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS f4a_semantic_categories (
                    observation_id INTEGER PRIMARY KEY,
                    category TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('object_label','sound_label')),
                    reported_confidence REAL NOT NULL
                        CHECK(reported_confidence BETWEEN 0 AND 1),
                    recorded_epoch_s REAL NOT NULL CHECK(recorded_epoch_s>=0),
                    source TEXT NOT NULL CHECK(source='mock_fixture_journal'),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    correction_reason TEXT
                        CHECK(correction_reason IS NULL OR correction_reason IN (
                            'fixture_annotation_error','source_retracted'))
                )
            """)
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS f4a_property_hypotheses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    property TEXT NOT NULL,
                    value TEXT NOT NULL,
                    proposed_confidence REAL NOT NULL
                        CHECK(proposed_confidence BETWEEN 0 AND 1),
                    proposed_epoch_s REAL NOT NULL CHECK(proposed_epoch_s>=0),
                    source TEXT NOT NULL
                        CHECK(source='fictional_llm_hypothesis_only'),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    correction_reason TEXT
                        CHECK(correction_reason IS NULL OR correction_reason IN (
                            'fixture_annotation_error','source_retracted')),
                    UNIQUE(category,property,value)
                )
            """)

    def remember(
        self, *, journal: PassiveObservationJournal, learning: PassiveLearning,
        observation_id: int, now_wall_epoch_s: float,
    ) -> bool:
        """Only an *already persisted and learned* F1-C/F2-C mock observation.

        No arbitrary caller-supplied observation, reward, label or provenance.
        Expired, unknown, low-confidence, duplicate/retracted or old-session
        evidence is never upgraded. Repeated calls cannot add counts.
        """
        if not isinstance(journal, PassiveObservationJournal) or not isinstance(learning, PassiveLearning):
            raise TypeError("F1-C journal and F2-C learning required")
        if journal._memory is not self._memory or learning._memory is not self._memory:
            raise ValueError("all ledgers must use the same ExperienceMemory")
        if type(observation_id) is not int or observation_id <= 0:
            raise ValueError("invalid observation ID")
        now = _check_wall(now_wall_epoch_s)
        row = self._memory.conn.execute("""
            SELECT j.id,j.category,j.kind,j.confidence,j.recorded_epoch_s
            FROM passive_observation_log j
            JOIN passive_learning_events l ON l.observation_id=j.id
            WHERE j.id=? AND j.session_id=? AND j.status='identified'
              AND j.category!='unknown' AND j.source='mock'
              AND j.channel='mock_fixture_unix' AND l.active=1
              AND l.outcome IN ('new_information','repeated_observation')
              AND j.recorded_epoch_s BETWEEN ? AND ?
        """, (observation_id,journal.session_id,
              now-MAX_CONSEQUENCE_AGE_S,now)).fetchone()
        if row is None:
            return False
        kind, category = row["kind"], row["category"]
        if (kind=="object_label" and category not in OBJECT_CATEGORIES or
            kind=="sound_label" and category not in _SOUND_CATEGORIES or
            kind not in ("object_label","sound_label")):
            raise ValueError("invalid journal category")
        confidence=_confidence(row["confidence"])
        with self._memory.conn:
            changed=self._memory.conn.execute("""
                INSERT OR IGNORE INTO f4a_semantic_categories(
                    observation_id,category,kind,reported_confidence,
                    recorded_epoch_s,source
                ) VALUES (?,?,?,?,?,'mock_fixture_journal')
            """,(observation_id,category,kind,confidence,float(row["recorded_epoch_s"])))
            self._prune(now)
            return changed.rowcount==1

    def _prune(self, now: float) -> None:
        con=self._memory.conn
        con.execute("""
            DELETE FROM f4a_semantic_categories
            WHERE recorded_epoch_s < ? OR recorded_epoch_s > ?
        """,(now-RETENTION_S,now+60))
        con.execute("""
            DELETE FROM f4a_semantic_categories
            WHERE observation_id NOT IN (
                SELECT observation_id FROM f4a_semantic_categories
                ORDER BY recorded_epoch_s DESC,observation_id DESC LIMIT ?
            )
        """,(MAX_SEMANTIC_ROWS,))
        # C2: preserve explicitly retracted hypotheses as durable markers in
        # the SAME unique-key table. Only active, unverified proposals expire.
        # Deleting an inactive row would silently allow a known bad proposal
        # to be reinserted after the 14-day TTL.
        if MAX_HYPOTHESIS_KEYS > MAX_HYPOTHESES:
            raise ValueError(
                "closed F4-A hypothesis vocabulary exceeds retention cap; "
                "a reviewed migration is required"
            )
        con.execute("""
            DELETE FROM f4a_property_hypotheses
            WHERE active=1 AND
                  (proposed_epoch_s < ? OR proposed_epoch_s > ?)
        """,(now-RETENTION_S,now+60))
        # Corrupt or future-expanded stores must fail closed, NEVER evict a
        # retraction in order to satisfy a row-count quota. The full table is
        # at most 54 keys in the current controlled vocabulary.
        rows=con.execute("""
            SELECT category,property,value,active,correction_reason
            FROM f4a_property_hypotheses LIMIT ?
        """,(MAX_HYPOTHESES+1,)).fetchall()
        if len(rows)>MAX_HYPOTHESES:
            raise ValueError("hypothesis retention cap exceeded; corrections protected")
        for row in rows:
            prop=row["property"]
            if (row["category"] not in HYPOTHESIS_CATEGORIES
                    or prop not in PROPERTIES
                    or row["value"] not in PROPERTIES[prop]):
                raise ValueError("unsupported persisted hypothesis key")
            if (row["active"]==0 and row["correction_reason"] not in CORRECTION_REASONS
                    or row["active"]==1 and row["correction_reason"] is not None):
                raise ValueError("inconsistent persisted hypothesis correction")

    def prune(self, *, now_wall_epoch_s: float) -> None:
        with self._memory.conn:
            self._prune(_check_wall(now_wall_epoch_s))

    def recall(self, *, now_wall_epoch_s: float,
               category: str | None = None, limit: int = 20
               ) -> tuple[HistoricalCategory,...]:
        """Read ONLY still-active, nonexpired F1-C + F2-C mock evidence."""
        now = _check_wall(now_wall_epoch_s)
        if type(limit) is not int or not 1 <= limit <= MAX_QUERY:
            raise ValueError("invalid recall limit")
        if category is not None and (type(category) is not str
                                     or category not in OBJECT_CATEGORIES | _SOUND_CATEGORIES):
            raise ValueError("category outside controlled vocabulary")
        rows=self._memory.conn.execute("""
            SELECT s.observation_id,s.category,s.kind,s.reported_confidence,
                   s.recorded_epoch_s
            FROM f4a_semantic_categories s
            JOIN passive_observation_log j ON j.id=s.observation_id
            JOIN passive_learning_events l ON l.observation_id=s.observation_id
            WHERE s.active=1 AND l.active=1 AND j.status='identified'
              AND j.source='mock' AND j.channel='mock_fixture_unix'
              AND s.source='mock_fixture_journal'
              AND s.category=j.category AND s.kind=j.kind
              AND s.reported_confidence=j.confidence
              AND l.outcome IN ('new_information','repeated_observation')
              AND s.recorded_epoch_s BETWEEN ? AND ?
              AND (? IS NULL OR s.category=?)
            ORDER BY s.recorded_epoch_s DESC,s.observation_id DESC LIMIT ?
        """,(now-RETENTION_S,now,category,category,limit)).fetchall()
        return tuple(HistoricalCategory(
            row["category"],"visual_label" if row["kind"]=="object_label"
            else "sound_label",_confidence(row["reported_confidence"]),
            int(row["observation_id"]),float(row["recorded_epoch_s"])
        ) for row in rows)

    def forget_observation(self, observation_id: int, *,
                           reason: str) -> bool:
        if type(observation_id) is not int or observation_id<=0 or reason not in CORRECTION_REASONS:
            raise ValueError("invalid correction")
        with self._memory.conn:
            result=self._memory.conn.execute("""
                UPDATE f4a_semantic_categories SET active=0,correction_reason=?
                WHERE observation_id=? AND active=1
            """,(reason,observation_id))
            return result.rowcount==1

    def hypothesize(self, *, category: str, property: str, value: str,
                    confidence: float, now_wall_epoch_s: float) -> int | None:
        """Manually inject a *fictional* LLM-like hypothesis, never a fact."""
        if (type(category) is not str or category not in HYPOTHESIS_CATEGORIES
                or type(property) is not str or property not in PROPERTIES
                or type(value) is not str or value not in PROPERTIES[property]):
            raise ValueError("no free text/identity or unsupported property")
        prob=_confidence(confidence)
        now=_check_wall(now_wall_epoch_s)
        with self._memory.conn:
            # Expire old ACTIVE entries before INSERT. Retained inactive
            # markers still occupy their unique (category,property,value)
            # key and make retries idempotently refuse without resurrection.
            self._prune(now)
            result=self._memory.conn.execute("""
                INSERT OR IGNORE INTO f4a_property_hypotheses(
                    category,property,value,proposed_confidence,
                    proposed_epoch_s,source)
                VALUES (?,?,?,?,?,'fictional_llm_hypothesis_only')
            """,(category,property,value,prob,now))
            return result.lastrowid if result.rowcount==1 else None

    def hypotheses(self, *, category: str, now_wall_epoch_s: float,
                   limit: int = 20) -> tuple[PropertyHypothesis,...]:
        if type(category) is not str or category not in HYPOTHESIS_CATEGORIES:
            raise ValueError("invalid hypothesis category")
        now=_check_wall(now_wall_epoch_s)
        if type(limit) is not int or not 1<=limit<=MAX_QUERY:
            raise ValueError("invalid hypothesis limit")
        rows=self._memory.conn.execute("""
            SELECT id,category,property,value,proposed_confidence
            FROM f4a_property_hypotheses
            WHERE active=1 AND category=?
              AND proposed_epoch_s BETWEEN ? AND ?
            ORDER BY proposed_epoch_s DESC,id DESC LIMIT ?
        """,(category,now-RETENTION_S,now,limit)).fetchall()
        return tuple(PropertyHypothesis(
            int(row["id"]),row["category"],row["property"],
            row["value"],_confidence(row["proposed_confidence"])
        ) for row in rows)

    def retract_hypothesis(self, hypothesis_id: int, *,
                           reason: str) -> bool:
        if type(hypothesis_id) is not int or hypothesis_id<=0 or reason not in CORRECTION_REASONS:
            raise ValueError("invalid hypothesis correction")
        with self._memory.conn:
            result=self._memory.conn.execute("""
                UPDATE f4a_property_hypotheses
                SET active=0,correction_reason=?,proposed_confidence=0
                WHERE id=? AND active=1
            """,(reason,hypothesis_id))
            return result.rowcount==1
