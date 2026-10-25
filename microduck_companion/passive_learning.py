"""F2-C: reversible, source-labelled learning from MOCK journalled categories.

Only F1-C rows already checked and persisted from the Unix fixture are evidence.
A recorded observation can change a small ATTENTION PRIORITY, not a motor
policy, a robot battery, a model weight or a real-world action preference.
An unexecuted proposal never creates an outcome. MuJoCo results use another
table and must never be imported here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3

from .episodic_memory import ExperienceMemory
from .passive_memory import PassiveObservationJournal, _check_wall

MAX_CONSEQUENCE_AGE_S = 2.0
NOVELTY_STEP = 0.02
REPETITION_STEP = -0.005
MAX_ATTENTION_BIAS = 0.12
_LEARNABLE = {"object_label": "observe", "sound_label": "listen"}
_CORRECTION_REASONS = frozenset({"fixture_annotation_error", "source_retracted"})


@dataclass(frozen=True)
class PassiveConsequence:
    """A MOCK observation outcome, never an observed effect of an action."""

    observation_id: int
    kind: str
    category: str
    outcome: str
    source: str
    active: bool


class PassiveLearning:
    """F2-C ledger and tiny biases in the SAME SQLite as F1-C.

    A consequence is computed from previously persisted F1-C evidence, never
    supplied as an unverified reward by a caller. Corrections withdraw an
    erroneous fixture row from learning and recompute all affected novelty and
    biases. The original historical journal remains untouched.
    """

    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("the existing ExperienceMemory instance is required")
        self._memory = memory
        with memory.conn:
            memory.conn.executescript("""
                CREATE TABLE IF NOT EXISTS passive_learning_events (
                    observation_id INTEGER PRIMARY KEY,
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    outcome TEXT NOT NULL DEFAULT 'pending'
                        CHECK(outcome IN ('pending','new_information',
                            'repeated_observation','duplicate_in_frame',
                            'unresolved','rejected','withdrawn')),
                    correction_reason TEXT CHECK(correction_reason IS NULL
                        OR correction_reason IN (
                            'fixture_annotation_error','source_retracted'))
                );
                CREATE TABLE IF NOT EXISTS passive_attention_preferences (
                    intention TEXT PRIMARY KEY
                        CHECK(intention IN ('observe','listen')),
                    source TEXT NOT NULL DEFAULT 'mock_fixture_journal'
                        CHECK(source='mock_fixture_journal'),
                    bias REAL NOT NULL DEFAULT 0 CHECK(bias BETWEEN -0.12 AND 0.12),
                    observations INTEGER NOT NULL DEFAULT 0
                        CHECK(observations>=0)
                );
            """)

    def _require_journal(self, journal: PassiveObservationJournal) -> None:
        if not isinstance(journal, PassiveObservationJournal):
            raise TypeError("requires an F1-C passive journal")
        if journal._memory is not self._memory:
            raise ValueError("learning and journal must share ExperienceMemory")

    def _recompute(self) -> None:
        """Rebuild from bounded F1-C history, including retractions.

        Unlearned but valid earlier journal entries count as familiar. Within
        one fixture frame, a category can only affect the bias once, even if
        several ephemeral tracks claim it.
        """
        conn = self._memory.conn
        conn.execute("""
            DELETE FROM passive_learning_events
            WHERE observation_id NOT IN (SELECT id FROM passive_observation_log)
        """)
        events = {
            int(row["observation_id"]): row
            for row in conn.execute(
                "SELECT observation_id,active FROM passive_learning_events"
            )
        }
        rows = conn.execute("""
            SELECT id,session_id,sequence,kind,category,status,source,channel
            FROM passive_observation_log ORDER BY id
        """).fetchall()
        previously_seen: set[tuple[str, str]] = set()
        seen_in_frame: set[tuple[str, int, str, str]] = set()
        deltas = {"observe": 0.0, "listen": 0.0}
        counts = {"observe": 0, "listen": 0}
        for row in rows:
            identifier = int(row["id"])
            tracked = events.get(identifier)
            if tracked is not None and not bool(tracked["active"]):
                conn.execute(
                    "UPDATE passive_learning_events SET outcome='withdrawn' "
                    "WHERE observation_id=?", (identifier,))
                continue
            status, kind, category = row["status"], row["kind"], row["category"]
            outcome = "rejected"
            if status == "identified" and category != "unknown":
                identity = (kind, category)  # a category, NOT a person/track
                frame = (row["session_id"], int(row["sequence"]), kind, category)
                if frame in seen_in_frame:
                    outcome = "duplicate_in_frame"
                else:
                    outcome = ("repeated_observation" if identity in previously_seen
                               else "new_information")
                    seen_in_frame.add(frame)
                    previously_seen.add(identity)
                    if tracked is not None:
                        intention = _LEARNABLE[kind]
                        deltas[intention] += (NOVELTY_STEP if
                                              outcome == "new_information"
                                              else REPETITION_STEP)
                        counts[intention] += 1
            elif status in {"unknown", "conflict"}:
                outcome = "unresolved"
            if tracked is not None:
                conn.execute(
                    "UPDATE passive_learning_events SET outcome=? "
                    "WHERE observation_id=?", (outcome, identifier))
        for intention, total in deltas.items():
            bias = max(-MAX_ATTENTION_BIAS, min(MAX_ATTENTION_BIAS, total))
            conn.execute("""
                INSERT INTO passive_attention_preferences(
                    intention,source,bias,observations)
                VALUES (?,'mock_fixture_journal',?,?)
                ON CONFLICT(intention) DO UPDATE SET
                    bias=excluded.bias,observations=excluded.observations
            """, (intention, bias, counts[intention]))

    def record(self, *, journal: PassiveObservationJournal,
               sequence: int, now_wall_epoch_s: float
               ) -> tuple[PassiveConsequence, ...]:
        """Evaluate ONE recently appended fixture sequence, idempotently.

        Call F1-C append() first. Never infer a consequence from a missing,
        stale, disconnected or unjournalled read. Only the current journal
        session can be evaluated: an old process's monotonic time is not reused.
        """
        self._require_journal(journal)
        if type(sequence) is not int or not 0 <= sequence < 2**63:
            raise ValueError("fixture sequence must be a nonnegative integer")
        wall = _check_wall(now_wall_epoch_s)
        journal.prune(now_wall_epoch_s=wall)
        with self._memory.conn:
            rows = self._memory.conn.execute("""
                SELECT id FROM passive_observation_log
                WHERE session_id=? AND sequence=?
                  AND source='mock' AND channel='mock_fixture_unix'
                  AND recorded_epoch_s BETWEEN ? AND ?
                ORDER BY id
            """, (journal.session_id, sequence,
                  wall - MAX_CONSEQUENCE_AGE_S, wall)).fetchall()
            for row in rows:
                self._memory.conn.execute("""
                    INSERT OR IGNORE INTO passive_learning_events(
                        observation_id,active,outcome)
                    VALUES (?,1,'pending')
                """, (int(row["id"]),))
            self._recompute()
            if not rows:
                return ()
            ids = tuple(int(row["id"]) for row in rows)
            result = self._memory.conn.execute(
                "SELECT l.observation_id,j.kind,j.category,l.outcome,l.active "
                "FROM passive_learning_events l "
                "JOIN passive_observation_log j ON j.id=l.observation_id "
                "WHERE l.observation_id IN (" +
                ",".join("?" for _ in ids) + ") ORDER BY l.observation_id",
                ids,
            ).fetchall()
        return tuple(PassiveConsequence(
            int(r["observation_id"]), r["kind"], r["category"],
            r["outcome"], "mock_fixture_journal", bool(r["active"])
        ) for r in result)

    def retract(self, observation_id: int, *, reason: str) -> bool:
        """Withdraw one faulty fixture annotation; never invent a new label."""
        if type(observation_id) is not int or observation_id <= 0:
            raise ValueError("observation_id must be a positive integer")
        if reason not in _CORRECTION_REASONS or type(reason) is not str:
            raise ValueError("correction requires a bounded reason")
        with self._memory.conn:
            changed = self._memory.conn.execute("""
                UPDATE passive_learning_events
                SET active=0,correction_reason=?,outcome='withdrawn'
                WHERE observation_id=? AND active=1
            """, (reason, observation_id))
            self._recompute()
            return changed.rowcount == 1

    def preference(self, intention: str) -> float:
        """Small synthetic attention bias only; never an action reward."""
        if intention not in _LEARNABLE.values():
            return 0.0
        row = self._memory.conn.execute(
            "SELECT bias FROM passive_attention_preferences WHERE intention=?",
            (intention,),
        ).fetchone()
        if row is None:
            return 0.0
        bias = float(row["bias"])
        if not math.isfinite(bias) or abs(bias) > MAX_ATTENTION_BIAS:
            raise ValueError("invalid persisted attention bias")
        return bias

    def history(self, *, limit: int = 50) -> tuple[PassiveConsequence, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        rows = self._memory.conn.execute("""
            SELECT l.observation_id,j.kind,j.category,l.outcome,l.active
            FROM passive_learning_events l JOIN passive_observation_log j
              ON j.id=l.observation_id
            ORDER BY l.observation_id DESC LIMIT ?
        """, (limit,)).fetchall()
        return tuple(PassiveConsequence(
            int(r["observation_id"]), r["kind"], r["category"],
            r["outcome"], "mock_fixture_journal", bool(r["active"])
        ) for r in rows)
