"""EX2: fictional before/after effects, not evidence of physical causation.

The sole input is a scripted MOCK pair tied to EX1's recorded, scripted
resolution. No camera, microphone, movement, PC model, motor receipt, reward,
behavioral preference or second SQLite connection is involved.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .experience_ledger import (
    MockExperienceLedger, _key, _epoch, MAX_STORED, RETENTION_S,
)

_SOURCE = "mock_fixture_only"
_MAX_PRE_S = 2.0
_MAX_POST_S = 2.0
_MIN_CONFIDENCE = .75  # arbitrary fixture threshold; not sensor calibration
_MAX_HISTORY = 50
_RETRACTION_REASONS = frozenset({
    "fixture_annotation_error", "source_retracted",
})
_CUES = {
    "motion": frozenset({"still", "moving", "unknown"}),
    "distance": frozenset({"near", "far", "unknown"}),
    "social": frozenset({
        "no_signal", "friendly_signal", "unfriendly_signal", "unknown",
    }),
    "sound": frozenset({"quiet", "heard", "unknown"}),
}


@dataclass(frozen=True)
class MockCue:
    """A declared synthetic cue, never an authenticated sensor observation."""

    kind: str
    value: str
    observed_at_epoch_s: float
    confidence: float
    source: str = _SOURCE

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind not in _CUES:
            raise ValueError("unsupported mock cue kind")
        if type(self.value) is not str or self.value not in _CUES[self.kind]:
            raise ValueError("unsupported mock cue value")
        _epoch(self.observed_at_epoch_s)
        if (type(self.confidence) not in (int, float)
                or not math.isfinite(self.confidence)
                or not 0 <= self.confidence <= 1):
            raise ValueError("confidence must be a finite mock scalar in [0,1]")
        if self.source != _SOURCE:
            raise ValueError("only explicitly fictional cues are admitted")


@dataclass(frozen=True)
class MockEffectPair:
    """A before/after mock comparison belonging to one EX1 fixture cycle."""

    session: str
    sequence: int
    before: MockCue
    after: MockCue
    same_scene: bool
    competing_event: bool
    source: str = _SOURCE

    def __post_init__(self) -> None:
        _key(self.session, self.sequence)
        if not isinstance(self.before, MockCue) or not isinstance(self.after, MockCue):
            raise TypeError("before and after must be mock cues")
        if self.before.kind != self.after.kind:
            raise ValueError("cannot compare different cue kinds")
        if self.before.observed_at_epoch_s >= self.after.observed_at_epoch_s:
            raise ValueError("before must strictly precede after")
        if (type(self.same_scene) is not bool
                or type(self.competing_event) is not bool
                or self.source != _SOURCE):
            raise ValueError("scene flags and source must be explicit fixtures")


@dataclass(frozen=True)
class MockEffectTrace:
    """Historical MOCK effect with temporal association, not a causal verdict."""

    session: str
    sequence: int
    category: str
    cue_kind: str
    before: str
    after: str
    effect_status: str
    association_status: str
    reason_code: str
    source: str = _SOURCE
    causality_established: bool = False
    verified_on_robot: bool = False
    motor_commands_issued: int = 0


def _assess(pair: MockEffectPair, *, unknown_target: bool) -> tuple[str, str, str]:
    """Never produces a causal probability, reward or verified conclusion."""
    if (unknown_target or pair.before.value == "unknown"
            or pair.after.value == "unknown"):
        return "indeterminate", "indeterminate", "unknown_cue_or_category"
    if (pair.before.confidence < _MIN_CONFIDENCE
            or pair.after.confidence < _MIN_CONFIDENCE):
        return "indeterminate", "indeterminate", "low_mock_confidence"
    if not pair.same_scene:
        return "indeterminate", "indeterminate", "scene_not_correlated"
    if pair.before.value == pair.after.value:
        return "unchanged", "none", "no_observed_change"
    if pair.competing_event:
        return "changed", "confounded", "competing_event"
    # A temporal link is NOT an action-caused consequence, even in mock data.
    return "changed", "temporal_only", "after_mock_resolution"


class MockEffectJournal:
    """EX2's optional effect table in the EXISTING EX1 ExperienceMemory.conn.

    No EX1 proposals or dispositions are created here. An EX1 resolution
    labelled mock_executed is a script, NOT an actuator acknowledgement.
    """

    def __init__(self, ledger: MockExperienceLedger) -> None:
        if not isinstance(ledger, MockExperienceLedger):
            raise TypeError("EX2 requires an EX1 ledger")
        self._memory = ledger._memory
        with self._memory.conn:
            self._memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS ex2_mock_effects (
                    ex1_id INTEGER PRIMARY KEY,
                    cue_kind TEXT NOT NULL CHECK(cue_kind IN (
                        'motion','distance','social','sound')),
                    before_value TEXT NOT NULL,
                    after_value TEXT NOT NULL,
                    before_epoch_s REAL NOT NULL CHECK(before_epoch_s>=0),
                    after_epoch_s REAL NOT NULL CHECK(after_epoch_s>=0),
                    before_confidence REAL NOT NULL CHECK(
                        before_confidence BETWEEN 0 AND 1),
                    after_confidence REAL NOT NULL CHECK(
                        after_confidence BETWEEN 0 AND 1),
                    same_scene INTEGER NOT NULL CHECK(same_scene IN (0,1)),
                    competing_event INTEGER NOT NULL CHECK(
                        competing_event IN (0,1)),
                    effect_status TEXT NOT NULL CHECK(effect_status IN (
                        'changed','unchanged','indeterminate')),
                    association_status TEXT NOT NULL CHECK(
                        association_status IN (
                            'temporal_only','none','confounded','indeterminate')),
                    reason_code TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source='mock_fixture_only'),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    correction_reason TEXT CHECK(correction_reason IS NULL OR
                        correction_reason IN (
                            'fixture_annotation_error','source_retracted'))
                )
            """)
            self._memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS ex2_effects_recent
                ON ex2_mock_effects(after_epoch_s DESC,ex1_id DESC)
            """)

    def _prune(self, now: float) -> None:
        con = self._memory.conn
        con.execute("""
            DELETE FROM ex2_mock_effects WHERE after_epoch_s < ?
               OR ex1_id NOT IN (SELECT id FROM ex1_mock_experiences)
        """, (now - RETENTION_S,))
        con.execute("""
            DELETE FROM ex2_mock_effects WHERE ex1_id NOT IN (
                SELECT ex1_id FROM ex2_mock_effects
                ORDER BY after_epoch_s DESC,ex1_id DESC LIMIT ?
            )
        """, (MAX_STORED,))

    def record(self, pair: MockEffectPair) -> bool:
        """Store one scripted comparison with an exact EX1 mock provenance.

        Even a changed, close-in-time cue remains a temporal association.
        Two different attempts to claim an effect for one EX1 cycle fail.
        """
        if not isinstance(pair, MockEffectPair):
            raise TypeError("EX2 requires typed mock evidence")
        session, seq = _key(pair.session, pair.sequence)
        with self._memory.conn:
            parent = self._memory.conn.execute("""
                SELECT id,intention,target_kind,target_category,
                       proposed_at_epoch_s,status,resolved_at_epoch_s,active,
                       source
                FROM ex1_mock_experiences WHERE session=? AND sequence=?
            """, (session, seq)).fetchone()
            if (parent is None or parent["active"] != 1
                    or parent["status"] != "mock_executed"
                    or parent["source"] != _SOURCE):
                raise ValueError("an active, mock-executed EX1 cycle is required")
            if (parent["intention"] not in {"observe", "inspect", "listen"}
                    or parent["target_category"] is None):
                raise ValueError("an explicit passive target is required")
            if ((parent["target_kind"] == "sound_label") !=
                    (pair.before.kind == "sound")):
                raise ValueError("mock cue is inconsistent with target modality")
            proposed = float(parent["proposed_at_epoch_s"])
            resolved = float(parent["resolved_at_epoch_s"])
            if not (proposed - _MAX_PRE_S <= pair.before.observed_at_epoch_s
                    <= proposed < resolved <= pair.after.observed_at_epoch_s
                    <= resolved + _MAX_POST_S):
                raise ValueError("mock before/after evidence is stale or unordered")
            effect, association, reason = _assess(
                pair, unknown_target=parent["target_category"] == "unknown",
            )
            values = (
                pair.before.kind, pair.before.value, pair.after.value,
                float(pair.before.observed_at_epoch_s),
                float(pair.after.observed_at_epoch_s),
                float(pair.before.confidence), float(pair.after.confidence),
                int(pair.same_scene), int(pair.competing_event),
                effect, association, reason, _SOURCE,
            )
            previous = self._memory.conn.execute("""
                SELECT cue_kind,before_value,after_value,
                       before_epoch_s,after_epoch_s,
                       before_confidence,after_confidence,
                       same_scene,competing_event,effect_status,
                       association_status,reason_code,source,active
                FROM ex2_mock_effects WHERE ex1_id=?
            """, (parent["id"],)).fetchone()
            if previous is not None:
                if previous["active"] != 1:
                    raise ValueError("retracted mock effects cannot be reactivated")
                if tuple(previous)[:-1] == values:
                    return False
                raise ValueError("conflicting mock evidence for the same cycle")
            self._memory.conn.execute("""
                INSERT INTO ex2_mock_effects (
                    ex1_id,cue_kind,before_value,after_value,
                    before_epoch_s,after_epoch_s,
                    before_confidence,after_confidence,
                    same_scene,competing_event,effect_status,
                    association_status,reason_code,source
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (parent["id"], *values))
            self._prune(pair.after.observed_at_epoch_s)
            return True

    def retract(self, *, session: str, sequence: int, reason: str) -> bool:
        """Remove one mock effect from active recall, without touching EX1."""
        session, seq = _key(session, sequence)
        if type(reason) is not str or reason not in _RETRACTION_REASONS:
            raise ValueError("invalid EX2 correction reason")
        with self._memory.conn:
            changed = self._memory.conn.execute("""
                UPDATE ex2_mock_effects SET active=0,correction_reason=?
                WHERE ex1_id IN (
                    SELECT id FROM ex1_mock_experiences
                    WHERE session=? AND sequence=?
                ) AND active=1
            """, (reason, session, seq))
            return changed.rowcount == 1

    def history(
        self, *, now_wall_epoch_s: float, limit: int = 20,
    ) -> tuple[MockEffectTrace, ...]:
        """Read only valid, active mock effects with their active EX1 parent."""
        now = _epoch(now_wall_epoch_s)
        if type(limit) is not int or not 1 <= limit <= _MAX_HISTORY:
            raise ValueError("invalid EX2 query limit")
        rows = self._memory.conn.execute("""
            SELECT p.session,p.sequence,p.target_category,e.cue_kind,
                   e.before_value,e.after_value,e.effect_status,
                   e.association_status,e.reason_code
            FROM ex2_mock_effects e
            JOIN ex1_mock_experiences p ON p.id=e.ex1_id
            WHERE p.active=1 AND p.status='mock_executed'
              AND p.source='mock_fixture_only'
              AND e.active=1 AND e.source='mock_fixture_only'
              AND e.after_epoch_s BETWEEN ? AND ?
            ORDER BY e.after_epoch_s DESC,e.ex1_id DESC LIMIT ?
        """, (now - RETENTION_S, now, limit)).fetchall()
        return tuple(MockEffectTrace(
            session=r["session"], sequence=int(r["sequence"]),
            category=r["target_category"], cue_kind=r["cue_kind"],
            before=r["before_value"], after=r["after_value"],
            effect_status=r["effect_status"],
            association_status=r["association_status"],
            reason_code=r["reason_code"],
        ) for r in rows)
