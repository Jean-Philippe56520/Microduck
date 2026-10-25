"""F1-C: bounded passive observations in the EXISTING ExperienceMemory SQLite.

This is a category-only *journal*, not a person/animal recognition database.
Monotonic time checks freshness within a process; wall time is only for
retention/querying across restarts. Never replay journal entries as live sensor
snapshots, motor permissions or verified physical facts. No media or track IDs
are written to disk.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3
import uuid

from .episodic_memory import ExperienceMemory
from .passive_observations import (
    OBJECT_CATEGORIES, PASSIVE_KINDS, summarize_passive,
)
from .passive_sources import PassiveRead
from .perception import PerceptionSnapshot, _SOUND_CATEGORIES

MAX_STORED_OBSERVATIONS = 512
RETENTION_SECONDS = 14 * 24 * 3600
MAX_QUERY = 100
MAX_WALL_CLOCK_SKEW_S = 60
_ALLOWED_STATUSES = frozenset({
    "identified", "unknown", "conflict", "low_confidence",
    "stale", "future", "untrusted",
})


@dataclass(frozen=True)
class PassiveMemoryEntry:
    """Historical MOCK category; not a live observation or proven identity."""

    id: int
    session_id: str
    sequence: int
    recorded_epoch_s: float
    observed_monotonic_s: float
    kind: str
    category: str
    status: str
    source: str
    confidence: float

    @property
    def is_historical(self) -> bool:
        return True


def _valid_time(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _check_wall(now_wall_epoch_s: float) -> float:
    if not _valid_time(now_wall_epoch_s):
        raise ValueError("wall clock must be a finite nonnegative Unix timestamp")
    return float(now_wall_epoch_s)


def _check_category(kind: str, category: str) -> None:
    if kind == "object_label":
        if type(category) is not str or category not in OBJECT_CATEGORIES:
            raise ValueError("invalid passive object category")
    elif kind == "sound_label":
        if type(category) is not str or category not in _SOUND_CATEGORIES:
            raise ValueError("invalid passive sound category")
    else:
        raise ValueError("only passive object/sound kinds are stored")


class PassiveObservationJournal:
    """Append/query passives through ExperienceMemory.conn; no second database.

    The session ID is process-local and randomly generated per journal
    instance. The same track_id in two processes never denotes the same
    individual. No track_id is persisted at all. This module intentionally
    supports ONLY F1-B mock fixture sources; a future authenticated adapter
    requires its own explicitly reviewed provenance contract.
    """

    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("requires the existing ExperienceMemory instance")
        self._memory = memory
        self.session_id = uuid.uuid4().hex
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS passive_observation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    ordinal INTEGER NOT NULL,
                    recorded_epoch_s REAL NOT NULL CHECK(recorded_epoch_s>=0),
                    observed_monotonic_s REAL NOT NULL
                        CHECK(observed_monotonic_s>=0),
                    kind TEXT NOT NULL
                        CHECK(kind IN ('object_label','sound_label')),
                    category TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK(status IN ('identified','unknown','conflict',
                                         'low_confidence','stale','future',
                                         'untrusted')),
                    source TEXT NOT NULL CHECK(source='mock'),
                    confidence REAL NOT NULL
                        CHECK(confidence>=0 AND confidence<=1),
                    channel TEXT NOT NULL CHECK(channel='mock_fixture_unix'),
                    UNIQUE(session_id,sequence,ordinal)
                )
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS passive_observation_by_time
                ON passive_observation_log(recorded_epoch_s DESC,id DESC)
            """)

    def append(self, reading: PassiveRead, *,
               now_monotonic_s: float, now_wall_epoch_s: float) -> int:
        """Record an F1-B fixture result; return new rows, not cached data.

        A non-ok read (disconnect, throttle, stale frame) yields zero rows.
        No caller can promote its own data to 'sensor' or save arbitrary labels.
        Projection may produce 'unknown' or 'conflict'; those states are
        recorded as such, never overwritten by an earlier positive result.
        """
        if not isinstance(reading, PassiveRead):
            raise TypeError("a PassiveRead from F1-B is required")
        if not _valid_time(now_monotonic_s):
            raise ValueError("now_monotonic_s must be finite and nonnegative")
        wall = _check_wall(now_wall_epoch_s)
        if reading.status != "ok":
            # A failed read must never reuse previously successful categories.
            return 0
        if reading.channel != "mock_fixture_unix":
            raise ValueError("unverified passive channel")
        if (type(reading.sequence) is not int
                or not 0 <= reading.sequence < 2**63):
            raise ValueError("invalid fixture sequence")
        snapshot = reading.snapshot
        if not isinstance(snapshot, PerceptionSnapshot):
            raise TypeError("reading must contain a PerceptionSnapshot")
        if snapshot.environment != "mock":
            raise ValueError("only mock snapshots may be journaled in F1-C")
        if any(event.kind not in PASSIVE_KINDS
               or event.source != "mock" for event in snapshot.events):
            raise ValueError("mock events must be passive and remain mock")
        projections = summarize_passive(snapshot, now=float(now_monotonic_s))
        for p in projections:
            if (p.status not in _ALLOWED_STATUSES
                    or p.claimed_source != "mock"
                    or not _valid_time(p.observed_at)
                    or not _valid_time(p.confidence)
                    or p.confidence > 1):
                raise ValueError("untrusted passive projection")
            _check_category(p.kind, p.category)
            if p.status != "identified" and p.category != "unknown":
                raise ValueError("uncertain category must be unknown")
        inserted = 0
        with self._memory.conn:
            self._prune(wall)
            # A sequence is one atomic F1-B receipt. Do not let a repeated
            # number append more categories by altering its event count.
            if self._memory.conn.execute("""
                SELECT 1 FROM passive_observation_log
                WHERE session_id=? AND sequence=? LIMIT 1
            """, (self.session_id, reading.sequence)).fetchone() is not None:
                return 0
            for ordinal, p in enumerate(projections):
                result = self._memory.conn.execute("""
                    INSERT OR IGNORE INTO passive_observation_log(
                        session_id,sequence,ordinal,recorded_epoch_s,
                        observed_monotonic_s,kind,category,status,
                        source,confidence,channel)
                    VALUES (?,?,?,?,?,?,?,?,?,?,'mock_fixture_unix')
                """, (
                    self.session_id, reading.sequence, ordinal, wall,
                    p.observed_at, p.kind, p.category, p.status,
                    "mock", p.confidence,
                ))
                inserted += result.rowcount
            self._prune(wall)
        # Do not count pruned rows or already-existing duplicate sequences.
        return inserted

    def _prune(self, wall: float) -> None:
        cutoff = wall - RETENTION_SECONDS
        self._memory.conn.execute(
            """DELETE FROM passive_observation_log
               WHERE recorded_epoch_s < ?
                  OR recorded_epoch_s > ?""",
            (cutoff, wall + MAX_WALL_CLOCK_SKEW_S),
        )
        self._memory.conn.execute("""
            DELETE FROM passive_observation_log
            WHERE id NOT IN (
                SELECT id FROM passive_observation_log
                ORDER BY recorded_epoch_s DESC,id DESC
                LIMIT ?
            )
        """, (MAX_STORED_OBSERVATIONS,))

    def prune(self, *, now_wall_epoch_s: float) -> int:
        wall = _check_wall(now_wall_epoch_s)
        with self._memory.conn:
            before = self._memory.conn.execute(
                "SELECT COUNT(*) FROM passive_observation_log").fetchone()[0]
            self._prune(wall)
            after = self._memory.conn.execute(
                "SELECT COUNT(*) FROM passive_observation_log").fetchone()[0]
        return before - after

    def recent(self, *, now_wall_epoch_s: float,
               limit: int = 20) -> tuple[PassiveMemoryEntry, ...]:
        """Return history only; never use these entries as live sensor input."""
        wall = _check_wall(now_wall_epoch_s)
        if type(limit) is not int or not 1 <= limit <= MAX_QUERY:
            raise ValueError("limit must be 1..100")
        rows = self._memory.conn.execute("""
            SELECT id,session_id,sequence,recorded_epoch_s,
                   observed_monotonic_s,kind,category,status,source,confidence
            FROM passive_observation_log
            WHERE recorded_epoch_s >= ?
              AND recorded_epoch_s <= ?
            ORDER BY recorded_epoch_s DESC,id DESC
            LIMIT ?
        """, (wall - RETENTION_SECONDS, wall, limit)).fetchall()
        return tuple(PassiveMemoryEntry(
            int(row["id"]), row["session_id"], int(row["sequence"]),
            float(row["recorded_epoch_s"]),
            float(row["observed_monotonic_s"]),
            row["kind"], row["category"], row["status"], row["source"],
            float(row["confidence"]),
        ) for row in rows)

    def category_count(self, kind: str, category: str, *,
                       now_wall_epoch_s: float) -> int:
        """How often this *category* was logged, never individual recognition.

        Unknown/conflicting/low-confidence rows are excluded. Count is not
        evidence a particular animal, object instance or person returned.
        """
        _check_category(kind, category)
        wall = _check_wall(now_wall_epoch_s)
        if category == "unknown":
            return 0
        return int(self._memory.conn.execute("""
            SELECT COUNT(*) FROM passive_observation_log
            WHERE kind=? AND category=? AND status='identified'
              AND source='mock'
              AND recorded_epoch_s >= ?
              AND recorded_epoch_s <= ?
        """, (kind, category, wall - RETENTION_SECONDS, wall)).fetchone()[0])
