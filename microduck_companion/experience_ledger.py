"""EX1: bounded, MOCK-ONLY lifecycle for F2 passive intentions.

This ledger reuses ExperienceMemory.conn, not another database or decision
loop. It records a proposed intention and an explicitly fictional resolution.
'mock_executed' is *never* physical execution proof. EX2 will separately
define observed consequences; EX1 never creates rewards or motor authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .episodic_memory import ExperienceMemory
from .passive_intentions import PassiveIntent

MAX_STORED = 256  # fixture limit, NOT a measured RK3566 budget
RETENTION_S = 14 * 24 * 3600
MAX_RESOLUTION_DELAY_S = 30.0
MAX_QUERY = 50
_SOURCE = "mock_fixture_only"
_RESOLUTIONS = frozenset({"mock_executed", "refused", "interrupted"})
_CORRECTIONS = frozenset({"fixture_annotation_error", "source_retracted"})
_SESSION = re.compile(r"s-[0-9a-f]{16}\Z")


def _epoch(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("expected finite, nonnegative fixture epoch")
    return float(value)


def _key(session: object, sequence: object) -> tuple[str, int]:
    if type(session) is not str or _SESSION.fullmatch(session) is None:
        raise ValueError("session must be an opaque s-<16 lowercase hex> identifier")
    if type(sequence) is not int or not (1 <= sequence <= 2_147_483_647):
        raise ValueError("invalid positive fixture sequence")
    return session, sequence


@dataclass(frozen=True)
class MockResolution:
    """An *explicit* scripted fixture outcome, NEVER a robotd acknowledgement."""

    session: str
    sequence: int
    status: str
    occurred_epoch_s: float
    source: str = _SOURCE

    def __post_init__(self) -> None:
        _key(self.session, self.sequence)
        if self.status not in _RESOLUTIONS or self.source != _SOURCE:
            raise ValueError("unsupported or non-fixture resolution")
        _epoch(self.occurred_epoch_s)


@dataclass(frozen=True)
class MockExperienceTrace:
    """Historical fixture lifecycle, without targets, media or rewards."""

    session: str
    sequence: int
    intention: str
    target_kind: str | None
    target_category: str | None
    proposed_at_epoch_s: float
    status: str
    resolved_at_epoch_s: float | None
    source: str = _SOURCE
    verified_on_robot: bool = False
    motor_commands_issued: int = 0


class MockExperienceLedger:
    """Keep mock F2 proposal/resolution in the SAME SQLite as ExperienceMemory.

    A mock resolution cannot be imported into F4-A BehavioralMemory as
    physical proof. There is deliberately NO motor, Qwen or reward API.
    P2a's previous mock-cycle tables are not written/read by this module;
    EX1 is an isolated lifecycle fixture, not a second production writer.
    """

    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("EX1 requires the existing ExperienceMemory")
        self._memory = memory
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS ex1_mock_experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK(sequence>0),
                    intention TEXT NOT NULL CHECK(intention IN (
                        'observe','inspect','listen','idle','rest')),
                    target_kind TEXT,
                    target_category TEXT,
                    proposed_at_epoch_s REAL NOT NULL CHECK(proposed_at_epoch_s>=0),
                    status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN (
                        'proposed','mock_executed','refused','interrupted')),
                    resolved_at_epoch_s REAL,
                    source TEXT NOT NULL CHECK(source='mock_fixture_only'),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    correction_reason TEXT CHECK(correction_reason IS NULL OR
                        correction_reason IN ('fixture_annotation_error',
                                              'source_retracted')),
                    UNIQUE(session,sequence)
                )
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS ex1_experiences_recent
                ON ex1_mock_experiences(proposed_at_epoch_s DESC,id DESC)
            """)

    def _prune(self, now: float) -> None:
        con = self._memory.conn
        con.execute(
            "DELETE FROM ex1_mock_experiences WHERE proposed_at_epoch_s < ?",
            (now - RETENTION_S,),
        )
        con.execute("""
            DELETE FROM ex1_mock_experiences WHERE id NOT IN (
                SELECT id FROM ex1_mock_experiences
                ORDER BY proposed_at_epoch_s DESC,id DESC LIMIT ?
            )
        """, (MAX_STORED,))

    def record_proposal(
        self, intent: PassiveIntent, *, session: str, sequence: int,
        proposed_at_epoch_s: float,
    ) -> bool:
        """Register a proposed F2 fixture intent; an intention is NOT execution.

        Returns False on an identical replay. Conflicting replays are refused.
        No free-text reason, track ID, voice, photo or personal name is stored.
        """
        if not isinstance(intent, PassiveIntent):
            raise TypeError("EX1 proposals must reuse an F2 PassiveIntent")
        if (intent.source != "mock" or intent.executed
                or intent.motor_commands_issued or intent.request_pc_analysis):
            raise ValueError("EX1 cannot import executed or motor intentions")
        session, sequence = _key(session, sequence)
        now = _epoch(proposed_at_epoch_s)
        values = (
            session, sequence, intent.intention,
            intent.target_kind, intent.target_category, now, _SOURCE,
        )
        with self._memory.conn:
            cur = self._memory.conn.execute("""
                INSERT OR IGNORE INTO ex1_mock_experiences(
                    session,sequence,intention,target_kind,target_category,
                    proposed_at_epoch_s,source
                ) VALUES (?,?,?,?,?,?,?)
            """, values)
            if cur.rowcount == 1:
                self._prune(now)
                return True
            row = self._memory.conn.execute("""
                SELECT intention,target_kind,target_category,
                       proposed_at_epoch_s,source
                FROM ex1_mock_experiences WHERE session=? AND sequence=?
            """, (session, sequence)).fetchone()
            if (row is not None
                    and tuple(row) == (
                        intent.intention, intent.target_kind,
                        intent.target_category, now, _SOURCE,
                    )):
                return False
            raise ValueError("conflicting fixture proposal replay")

    def resolve(self, evidence: MockResolution) -> bool:
        """Record a fictional resolution, never a physical execution fact.

        An identical replay is idempotent; different second resolutions fail.
        No reward or consequence is inferred from the resolution.
        """
        if not isinstance(evidence, MockResolution):
            raise TypeError("EX1 needs an explicit MockResolution fixture")
        session, sequence = _key(evidence.session, evidence.sequence)
        now = _epoch(evidence.occurred_epoch_s)
        with self._memory.conn:
            row = self._memory.conn.execute("""
                SELECT proposed_at_epoch_s,status,resolved_at_epoch_s,active
                FROM ex1_mock_experiences WHERE session=? AND sequence=?
            """, (session, sequence)).fetchone()
            if row is None or row["active"] != 1:
                raise ValueError("cannot resolve a missing or retracted proposal")
            start = float(row["proposed_at_epoch_s"])
            if not start <= now <= start + MAX_RESOLUTION_DELAY_S:
                raise ValueError("fixture resolution out of chronological bounds")
            if row["status"] != "proposed":
                if (row["status"] == evidence.status
                        and row["resolved_at_epoch_s"] == now):
                    return False
                raise ValueError("already resolved with different evidence")
            if evidence.status == "mock_executed":
                # Even attention and rest here are only *scripted* actions.
                # This is deliberately not a robotd/actuator receipt.
                pass
            updated = self._memory.conn.execute("""
                UPDATE ex1_mock_experiences
                SET status=?,resolved_at_epoch_s=?
                WHERE session=? AND sequence=? AND status='proposed' AND active=1
            """, (evidence.status, now, session, sequence))
            return updated.rowcount == 1

    def retract(self, *, session: str, sequence: int, reason: str) -> bool:
        """Revoke incorrect fixture evidence without any motor-side effect."""
        session, sequence = _key(session, sequence)
        if type(reason) is not str or reason not in _CORRECTIONS:
            raise ValueError("unsupported correction reason")
        with self._memory.conn:
            cur = self._memory.conn.execute("""
                UPDATE ex1_mock_experiences
                SET active=0,correction_reason=?
                WHERE session=? AND sequence=? AND active=1
            """, (reason, session, sequence))
            return cur.rowcount == 1

    def history(
        self, *, now_wall_epoch_s: float, limit: int = 20,
    ) -> tuple[MockExperienceTrace, ...]:
        """Bounded active fixture-only history; NOT a feed of actual trials."""
        now = _epoch(now_wall_epoch_s)
        if type(limit) is not int or not 1 <= limit <= MAX_QUERY:
            raise ValueError("invalid EX1 history limit")
        rows = self._memory.conn.execute("""
            SELECT session,sequence,intention,target_kind,target_category,
                   proposed_at_epoch_s,status,resolved_at_epoch_s
            FROM ex1_mock_experiences
            WHERE active=1 AND source='mock_fixture_only'
              AND proposed_at_epoch_s BETWEEN ? AND ?
            ORDER BY proposed_at_epoch_s DESC,id DESC LIMIT ?
        """, (now - RETENTION_S, now, limit)).fetchall()
        return tuple(MockExperienceTrace(
            session=r["session"],
            sequence=int(r["sequence"]),
            intention=r["intention"],
            target_kind=r["target_kind"],
            target_category=r["target_category"],
            proposed_at_epoch_s=float(r["proposed_at_epoch_s"]),
            status=r["status"],
            resolved_at_epoch_s=(
                float(r["resolved_at_epoch_s"])
                if r["resolved_at_epoch_s"] is not None else None
            ),
        ) for r in rows)
