"""EX3: read-derived, tiny reversible MOCK attention hints, not causal learning.

This module reuses EX2/EX1 rows in the *existing* ExperienceMemory SQLite.
No additional table, writer, cached score, trained weights, sensor, network,
motor control or automatic positive/negative social reward is introduced.

A repeated EX2 temporal association can make an optional F2 *passive*
attention proposal slightly more/less likely in MOCK fixtures only. This is
an informational trend, not evidence that the intention CAUSED the effect.
"""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from .experience_effects import MockEffectJournal
from .experience_ledger import MAX_STORED, RETENTION_S, _epoch
from .passive_observations import OBJECT_CATEGORIES
from .perception import _SOUND_CATEGORIES

SOURCE = "mock_fixture_only"
MIN_DISTINCT_SESSIONS = 3  # fixture criterion, not measured reliability
MAX_DISTINCT_SESSIONS = 32
BIAS_STEP = 0.01
MAX_ATTENTION_BIAS = 0.04
_SUPPORTED = {
    "observe": (frozenset(OBJECT_CATEGORIES - {"unknown"}),
                "object_label", frozenset({"motion"})),
    "listen": (frozenset(_SOUND_CATEGORIES - {"unknown"}),
               "sound_label", frozenset({"sound"})),
}


@dataclass(frozen=True)
class MockAttentionTrend:
    """A context-limited, fictional attention hint, NEVER a physical preference."""

    intention: str
    category: str
    distinct_mock_sessions: int
    changed: int
    unchanged: int
    attention_bias: float
    status: str
    source: str = SOURCE
    causality_established: bool = False
    verified_on_robot: bool = False
    motor_commands_issued: int = 0


def _validate_context(intention: object, category: object) -> tuple[str, str]:
    if type(intention) is not str or intention not in _SUPPORTED:
        raise ValueError("only passive observe/listen mock trends are available")
    allowed, kind, _ = _SUPPORTED[intention]
    if type(category) is not str or category not in allowed:
        raise ValueError("unknown or unsupported mock category")
    return kind, intention


def compute_mock_attention_trend(
    connection: sqlite3.Connection,
    *, intention: str, category: str,
    now_wall_epoch_s: float,
) -> MockAttentionTrend:
    """Pure SELECT of active EX1+EX2 evidence; no extra table or UPDATE.

    Distinct claimed fixture session tokens, not event count, delimit the\n    pattern. Tokens do not prove independent real-world trials.
    Candidate rows are re-validated against the stored EX1 chronology and
    EX2 metadata; SQL tampering/mixed provenance must not become a hint.
    Competing events, social responses, missing cues, unknown targets,
    incorrect clocks and retracted claims contribute zero.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("existing SQLite connection required")
    kind, intention = _validate_context(intention, category)
    now = _epoch(now_wall_epoch_s)
    _, target_kind, allowed_cues = _SUPPORTED[intention]
    marks = ",".join("?" for _ in sorted(allowed_cues))
    sql = """
        SELECT p.session,e.effect_status
        FROM ex2_mock_effects e
        JOIN ex1_mock_experiences p ON p.id=e.ex1_id
        WHERE p.active=1 AND e.active=1
          AND p.source='mock_fixture_only'
          AND e.source='mock_fixture_only'
          AND p.status='mock_executed'
          AND p.intention=? AND p.target_kind=? AND p.target_category=?
          AND e.cue_kind IN (""" + marks + """)
          AND p.proposed_at_epoch_s BETWEEN ? AND ?
          AND e.after_epoch_s BETWEEN ? AND ?
          AND p.resolved_at_epoch_s BETWEEN p.proposed_at_epoch_s
                                         AND p.proposed_at_epoch_s+30
          AND e.before_epoch_s BETWEEN p.proposed_at_epoch_s-2
                                     AND p.proposed_at_epoch_s
          AND e.before_epoch_s<e.after_epoch_s
          AND e.after_epoch_s BETWEEN p.resolved_at_epoch_s
                                  AND p.resolved_at_epoch_s+2
          AND e.before_confidence BETWEEN .75 AND 1
          AND e.after_confidence BETWEEN .75 AND 1
          AND e.before_value!='unknown' AND e.after_value!='unknown'
          AND e.same_scene=1 AND e.competing_event=0
          AND (
               (e.effect_status='changed'
                AND e.before_value!=e.after_value
                AND e.association_status='temporal_only'
                AND e.reason_code='after_mock_resolution')
            OR (e.effect_status='unchanged'
                AND e.before_value=e.after_value
                AND e.association_status='none'
                AND e.reason_code='no_observed_change')
          )
        ORDER BY e.after_epoch_s DESC,e.ex1_id DESC
        LIMIT ?
    """
    rows = connection.execute(sql, (
        intention, target_kind, category, *sorted(allowed_cues),
        now - RETENTION_S, now, now - RETENTION_S, now,
        MAX_STORED,
    )).fetchall()
    seen_sessions: set[str] = set()
    changed = unchanged = 0
    for session, effect in rows:
        if session in seen_sessions:
            continue
        seen_sessions.add(session)
        if effect == "changed":
            changed += 1
        else:
            unchanged += 1
        if len(seen_sessions) >= MAX_DISTINCT_SESSIONS:
            break
    n = changed + unchanged
    if n < MIN_DISTINCT_SESSIONS:
        bias = 0.0
        status = "insufficient_mock_sessions"
    else:
        difference = changed - unchanged
        bias = round(max(-MAX_ATTENTION_BIAS,
                         min(MAX_ATTENTION_BIAS,
                             BIAS_STEP * difference)), 6)
        status = ("balanced_mock_pattern" if difference == 0
                  else "repeated_temporal_mock_pattern")
    return MockAttentionTrend(
        intention=intention, category=category,
        distinct_mock_sessions=n, changed=changed, unchanged=unchanged,
        attention_bias=bias, status=status,
    )


class MockAttentionTrends:
    """Optional F2 adapter. Reuse exactly the EX2/EX1 ExperienceMemory conn."""

    def __init__(self, effects: MockEffectJournal) -> None:
        if not isinstance(effects, MockEffectJournal):
            raise TypeError("requires an existing EX2 MockEffectJournal")
        self._memory = effects._memory

    def summary(self, *, intention: str, category: str,
                now_wall_epoch_s: float) -> MockAttentionTrend:
        return compute_mock_attention_trend(
            self._memory.conn, intention=intention, category=category,
            now_wall_epoch_s=now_wall_epoch_s,
        )

    def bias_for(self, *, intention: str, category: str,
                 now_wall_epoch_s: float) -> float:
        """A small MOCK-only ranking hint; never an action or motor command."""
        return self.summary(
            intention=intention, category=category,
            now_wall_epoch_s=now_wall_epoch_s,
        ).attention_bias
