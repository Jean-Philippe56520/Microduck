"""F4-A: bounded behavioral outcomes ONLY from P2a explicit MOCK feedback.

This table is separate from the existing ExperienceMemory simulator motion
preferences, actual model weights and robotd motor safety. A chosen intention
is NEVER evidence it executed. Only a P2a cycle's explicitly corroborated
mock followup may yield a small fictional attention preference.

No target, track ID, household individual or image/audio is copied.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .episodic_memory import ExperienceMemory
from .mock_cycles import MockCycleRunner
from .passive_memory import _check_wall

MAX_STORED = 256
RETENTION_S = 14 * 24 * 3600
MAX_QUERY = 50
STEP = .04
MAX_BIAS = .12
CORRECTION_REASONS = frozenset({"fixture_annotation_error","source_retracted"})


@dataclass(frozen=True)
class BehavioralSummary:
    """Entirely fictional preference, NOT a policy or real-world reward."""

    positive: int
    negative: int
    bias: float
    source: str = "explicit_mock_followup_only"
    verified_on_robot: bool = False
    executed_actions: int = 0
    motor_commands_issued: int = 0


@dataclass(frozen=True)
class BehavioralTrace:
    mock_cycle_id: int
    result: str
    source: str = "explicit_mock_followup_only"
    historical_only: bool = True
    executed_actions: int = 0


class BehavioralMemory:
    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("requires existing ExperienceMemory")
        self._memory=memory
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS f4a_mock_behavior_outcomes (
                    mock_cycle_id INTEGER PRIMARY KEY,
                    outcome TEXT NOT NULL CHECK(outcome IN ('positive','negative')),
                    source TEXT NOT NULL CHECK(source='explicit_mock_followup_only'),
                    recorded_epoch_s REAL NOT NULL CHECK(recorded_epoch_s>=0),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    correction_reason TEXT CHECK(
                        correction_reason IS NULL OR correction_reason IN (
                            'fixture_annotation_error','source_retracted'))
                )
            """)

    def record(self, *, runner: MockCycleRunner, sequence: int,
               now_wall_epoch_s: float) -> bool:
        """Cross-check one existing P2a cycle before storing a result.

        Motion, stale/unverified followups, absent cycles, duplicate cycles,
        and simulator/LLM evidence never qualify. Does not call .step().
        """
        if not isinstance(runner, MockCycleRunner):
            raise TypeError("requires existing P2a mock runner")
        if runner.memory is not self._memory:
            raise ValueError("P2a and F4-A must share SQLite")
        if type(sequence) is not int or sequence<=0:
            raise ValueError("invalid cycle sequence")
        now=_check_wall(now_wall_epoch_s)
        row=self._memory.conn.execute("""
            SELECT id,intention,disposition,outcome,reward,source
            FROM mock_cognitive_cycles WHERE session=? AND sequence=?
        """,(runner.session,sequence)).fetchone()
        if row is None:
            return False
        outcomes={"explicit_mock_positive":("positive",.4),
                  "explicit_mock_negative":("negative",-.4)}
        expected=outcomes.get(row["outcome"])
        reward=row["reward"]
        if (row["source"]!="mock" or row["intention"]!="inspect_object"
                or row["disposition"]!="mock_feedback" or expected is None
                or type(reward) not in (int,float)
                or not math.isfinite(reward)
                or abs(float(reward)-expected[1])>1e-12):
            return False
        with self._memory.conn:
            changed=self._memory.conn.execute("""
                INSERT OR IGNORE INTO f4a_mock_behavior_outcomes(
                    mock_cycle_id,outcome,source,recorded_epoch_s)
                VALUES (?,?,'explicit_mock_followup_only',?)
            """,(int(row["id"]),expected[0],now))
            self._prune(now)
            return changed.rowcount==1

    def _prune(self, now: float) -> None:
        con=self._memory.conn
        con.execute("""
            DELETE FROM f4a_mock_behavior_outcomes
            WHERE recorded_epoch_s < ? OR recorded_epoch_s > ?
        """,(now-RETENTION_S,now+60))
        con.execute("""
            DELETE FROM f4a_mock_behavior_outcomes WHERE mock_cycle_id NOT IN (
                SELECT mock_cycle_id FROM f4a_mock_behavior_outcomes
                ORDER BY recorded_epoch_s DESC,mock_cycle_id DESC LIMIT ?
            )
        """,(MAX_STORED,))

    def prune(self, *, now_wall_epoch_s: float) -> None:
        with self._memory.conn:
            self._prune(_check_wall(now_wall_epoch_s))

    def summary(self, *, now_wall_epoch_s: float) -> BehavioralSummary:
        """Small bounded deterministic tendency: not passed to robotd."""
        now=_check_wall(now_wall_epoch_s)
        rows=self._memory.conn.execute("""
            SELECT b.outcome,COUNT(*) AS n
            FROM f4a_mock_behavior_outcomes b
            JOIN mock_cognitive_cycles c ON c.id=b.mock_cycle_id
            WHERE b.active=1 AND b.source='explicit_mock_followup_only'
              AND b.recorded_epoch_s BETWEEN ? AND ?
              AND c.source='mock' AND c.intention='inspect_object'
              AND c.disposition='mock_feedback'
              AND ((b.outcome='positive' AND
                    c.outcome='explicit_mock_positive' AND c.reward=0.4)
                OR (b.outcome='negative' AND
                    c.outcome='explicit_mock_negative' AND c.reward=-0.4))
            GROUP BY b.outcome
        """,(now-RETENTION_S,now)).fetchall()
        counts={row["outcome"]:int(row["n"]) for row in rows}
        pos,neg=counts.get("positive",0),counts.get("negative",0)
        return BehavioralSummary(
            pos,neg,max(-MAX_BIAS,min(MAX_BIAS,STEP*(pos-neg))))

    def history(self, *, now_wall_epoch_s: float,
                limit: int = 20) -> tuple[BehavioralTrace,...]:
        now=_check_wall(now_wall_epoch_s)
        if type(limit) is not int or not 1<=limit<=MAX_QUERY:
            raise ValueError("invalid history limit")
        rows=self._memory.conn.execute("""
            SELECT b.mock_cycle_id,b.outcome FROM f4a_mock_behavior_outcomes b
            JOIN mock_cognitive_cycles c ON c.id=b.mock_cycle_id
            WHERE b.active=1 AND b.recorded_epoch_s BETWEEN ? AND ?
              AND c.source='mock' AND c.disposition='mock_feedback'
              AND c.intention='inspect_object'
              AND ((b.outcome='positive' AND
                    c.outcome='explicit_mock_positive' AND c.reward=0.4)
                OR (b.outcome='negative' AND
                    c.outcome='explicit_mock_negative' AND c.reward=-0.4))
            ORDER BY b.recorded_epoch_s DESC,b.mock_cycle_id DESC
            LIMIT ?
        """,(now-RETENTION_S,now,limit)).fetchall()
        return tuple(BehavioralTrace(int(row["mock_cycle_id"]),
                                     row["outcome"]) for row in rows)

    def retract(self, mock_cycle_id: int, *, reason: str) -> bool:
        """Reversible correction removes evidence from the aggregate."""
        if (type(mock_cycle_id) is not int or mock_cycle_id<=0
                or type(reason) is not str or reason not in CORRECTION_REASONS):
            raise ValueError("invalid behavior correction")
        with self._memory.conn:
            row=self._memory.conn.execute("""
                UPDATE f4a_mock_behavior_outcomes SET active=0,
                    correction_reason=? WHERE mock_cycle_id=? AND active=1
            """,(reason,mock_cycle_id))
            return row.rowcount==1
