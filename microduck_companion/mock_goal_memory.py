"""MEM-1: persistent MOCK goals referencing EX1, not a second attempt ledger.

Only the existing ExperienceMemory.conn writes two bounded tables. No sensor,
Qwen, reward, controller, motor, or authenticated robot execution is involved.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .episodic_memory import ExperienceMemory
from .experience_ledger import MockExperienceLedger, _epoch, _key
from .passive_observations import OBJECT_CATEGORIES

SOURCE = "mock_fixture_only"
MAX_GOALS = 32
MAX_LINKS_PER_GOAL = 8
MAX_LINKS_TOTAL = 128
MAX_LINK_AGE_S = 120.0
# DET-1 reads recent goals only; this is a prototype freshness gate.
MAX_FOCUS_AGE_S = 14 * 24 * 3600
GOAL_KINDS = frozenset({"observe_category", "inspect_unknown", "compare_views"})
STATES = frozenset({"candidate", "active", "suspended", "mock_closed", "abandoned"})
RESUME_CONDITIONS = frozenset({"new_view", "new_context", "new_evidence", "operator_review"})
RETRACTIONS = frozenset({"fixture_annotation_error", "source_retracted"})
STRATEGIES = {
    "observe_from_distance": "observe",
    "observe_over_time": "observe",
    "inspect_other_view": "inspect",
    "compare_memory": "inspect",
}
CONTEXTS = frozenset({"initial", "new_view", "new_context", "new_evidence"})
TRANSITIONS = {
    ("candidate", "active"): frozenset({"begin_mock_goal"}),
    ("candidate", "abandoned"): frozenset({"no_longer_relevant"}),
    ("active", "suspended"): frozenset({
        "uncertain", "repeat_blocked", "context_unavailable",
    }),
    ("active", "abandoned"): frozenset({"no_longer_relevant"}),
    ("active", "mock_closed"): frozenset({"fixture_review_only"}),
    ("suspended", "active"): RESUME_CONDITIONS,
    ("suspended", "abandoned"): frozenset({"no_longer_relevant"}),
}
_GOAL_ID = re.compile(r"g-[0-9a-f]{16}\Z")


def _goal_id(value: object) -> str:
    if type(value) is not str or _GOAL_ID.fullmatch(value) is None:
        raise ValueError("goal id must be opaque g-<16 hex>")
    return value


def _kind_category(kind: object, category: object) -> None:
    if (type(kind) is not str or kind not in GOAL_KINDS
            or type(category) is not str or category not in OBJECT_CATEGORIES
            or (kind == "inspect_unknown" and category != "unknown")
            or (kind == "observe_category" and category == "unknown")):
        raise ValueError("invalid public mock category and goal kind")


@dataclass(frozen=True)
class MockGoal:
    goal_id: str
    kind: str
    category: str
    state: str
    resume_when: str
    created_at_epoch_s: float
    updated_at_epoch_s: float
    revision: int
    corrected: bool
    source: str = SOURCE
    physical_completion_verified: bool = False
    motor_commands_issued: int = 0


@dataclass(frozen=True)
class MockGoalAttempt:
    goal_id: str
    strategy: str
    context: str
    linked_at_epoch_s: float
    evidence_state: str
    mock_resolution: str
    session: str | None
    sequence: int | None
    source: str = SOURCE
    physical_execution_verified: bool = False
    physical_effect_verified: bool = False
    causality_established: bool = False
    motor_commands_issued: int = 0


class MockGoalMemory:
    """Persist goals and EX1 references on the existing mono-writer connection.

    Only PC fixtures are accepted. No F2 arbitration or execution is triggered.
    """

    def __init__(self, memory: ExperienceMemory,
                 ex1: MockExperienceLedger) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("requires existing ExperienceMemory")
        if not isinstance(ex1, MockExperienceLedger):
            raise TypeError("requires existing EX1 mock ledger")
        if ex1._memory is not memory:
            raise ValueError("EX1 and MEM-1 must share one ExperienceMemory")
        self._memory = memory
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS mem1_mock_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL CHECK(kind IN (
                        'observe_category','inspect_unknown','compare_views')),
                    category TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'candidate' CHECK(state IN (
                        'candidate','active','suspended','mock_closed','abandoned')),
                    resume_when TEXT NOT NULL CHECK(resume_when IN (
                        'new_view','new_context','new_evidence','operator_review')),
                    created_at_epoch_s REAL NOT NULL CHECK(created_at_epoch_s>=0),
                    updated_at_epoch_s REAL NOT NULL CHECK(updated_at_epoch_s>=0),
                    revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=1),
                    source TEXT NOT NULL CHECK(source='mock_fixture_only'),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    correction_reason TEXT CHECK(correction_reason IS NULL OR
                        correction_reason IN (
                            'fixture_annotation_error','source_retracted'))
                )
            """)
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS mem1_mock_goal_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_row_id INTEGER NOT NULL,
                    ex1_row_id INTEGER NOT NULL UNIQUE,
                    strategy TEXT NOT NULL CHECK(strategy IN (
                        'observe_from_distance','observe_over_time',
                        'inspect_other_view','compare_memory')),
                    context TEXT NOT NULL CHECK(context IN (
                        'initial','new_view','new_context','new_evidence')),
                    linked_at_epoch_s REAL NOT NULL CHECK(linked_at_epoch_s>=0),
                    source TEXT NOT NULL CHECK(source='mock_fixture_only'),
                    UNIQUE(goal_row_id,strategy,context)
                )
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS mem1_links_by_goal
                ON mem1_mock_goal_links(goal_row_id,id DESC)
            """)

    def create(self, *, goal_id: str, kind: str, category: str,
               resume_when: str, at_epoch_s: float) -> bool:
        key = _goal_id(goal_id)
        _kind_category(kind, category)
        if type(resume_when) is not str or resume_when not in RESUME_CONDITIONS:
            raise ValueError("invalid mock resumption condition")
        at = _epoch(at_epoch_s)
        con = self._memory.conn
        with con:
            old = con.execute("""
                SELECT kind,category,resume_when,created_at_epoch_s,active
                FROM mem1_mock_goals WHERE goal_id=?
            """, (key,)).fetchone()
            if old is not None:
                if (tuple(old[:4]) == (kind, category, resume_when, at)
                        and old["active"] == 1):
                    return False
                raise ValueError("conflicting or retracted goal cannot be reused")
            if con.execute(
                "SELECT COUNT(*) FROM mem1_mock_goals"
            ).fetchone()[0] >= MAX_GOALS:
                raise ValueError("MEM-1 goal capacity reached")
            con.execute("""
                INSERT INTO mem1_mock_goals(
                    goal_id,kind,category,resume_when,
                    created_at_epoch_s,updated_at_epoch_s,source
                ) VALUES (?,?,?,?,?,?,?)
            """, (key, kind, category, resume_when, at, at, SOURCE))
            return True

    def transition(self, *, goal_id: str, expected_revision: int,
                   next_state: str, reason: str, at_epoch_s: float) -> None:
        key = _goal_id(goal_id)
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("invalid expected revision")
        if type(next_state) is not str or next_state not in STATES:
            raise ValueError("invalid goal state")
        if type(reason) is not str:
            raise ValueError("invalid transition reason")
        at = _epoch(at_epoch_s)
        con = self._memory.conn
        with con:
            row = con.execute("""
                SELECT id,state,resume_when,revision,updated_at_epoch_s,active
                FROM mem1_mock_goals WHERE goal_id=?
            """, (key,)).fetchone()
            if row is None or row["active"] != 1:
                raise ValueError("missing or retracted mock goal")
            if row["revision"] != expected_revision:
                raise ValueError("stale goal revision")
            if at < row["updated_at_epoch_s"]:
                raise ValueError("out-of-order mock goal transition")
            current = row["state"]
            if reason not in TRANSITIONS.get((current, next_state), frozenset()):
                raise ValueError("forbidden mock goal transition")
            if ((current, next_state) == ("suspended", "active")
                    and reason != row["resume_when"]):
                raise ValueError("mock resumption condition differs")
            if next_state == "mock_closed":
                # This verifies only that an EX1 script was recorded, not
                # physical execution, any real outcome, or achieved goal.
                exists = con.execute("""
                    SELECT 1 FROM mem1_mock_goal_links l
                    JOIN ex1_mock_experiences e ON e.id=l.ex1_row_id
                    WHERE l.goal_row_id=? AND l.source='mock_fixture_only'
                      AND e.active=1 AND e.source='mock_fixture_only'
                      AND e.status='mock_executed' LIMIT 1
                """, (row["id"],)).fetchone()
                if exists is None:
                    raise ValueError("mock closure lacks active EX1 script")
            updated = con.execute("""
                UPDATE mem1_mock_goals
                SET state=?,updated_at_epoch_s=?,revision=revision+1
                WHERE id=? AND active=1 AND revision=?
            """, (next_state, at, row["id"], expected_revision))
            if updated.rowcount != 1:
                raise ValueError("concurrent goal revision changed")

    def link_attempt(self, *, goal_id: str, session: str, sequence: int,
                     strategy: str, context: str, at_epoch_s: float) -> bool:
        key = _goal_id(goal_id)
        session, sequence = _key(session, sequence)
        if type(strategy) is not str or strategy not in STRATEGIES:
            raise ValueError("unknown fixture strategy")
        if type(context) is not str or context not in CONTEXTS:
            raise ValueError("unknown fixture context")
        at = _epoch(at_epoch_s)
        con = self._memory.conn
        with con:
            goal = con.execute("""
                SELECT id,state,category,created_at_epoch_s,updated_at_epoch_s,active
                FROM mem1_mock_goals WHERE goal_id=?
            """, (key,)).fetchone()
            if goal is None or goal["active"] != 1 or goal["state"] != "active":
                raise ValueError("goal must be active and non-retracted")
            event = con.execute("""
                SELECT id,intention,target_kind,target_category,
                       proposed_at_epoch_s,status,source,active
                FROM ex1_mock_experiences WHERE session=? AND sequence=?
            """, (session, sequence)).fetchone()
            if (event is None or event["active"] != 1
                    or event["source"] != SOURCE
                    or event["target_kind"] != "object_label"
                    or event["target_category"] != goal["category"]
                    or event["intention"] != STRATEGIES[strategy]
                    or event["status"] not in {
                        "proposed","mock_executed","refused","interrupted",
                    }):
                raise ValueError("no matching active EX1 mock proposal")
            proposed = float(event["proposed_at_epoch_s"])
            if (proposed < goal["updated_at_epoch_s"]
                    or not proposed <= at <= proposed + MAX_LINK_AGE_S):
                raise ValueError("stale EX1 proposal or pre-goal event")
            previous = con.execute("""
                SELECT goal_row_id,strategy,context,linked_at_epoch_s
                FROM mem1_mock_goal_links WHERE ex1_row_id=?
            """, (event["id"],)).fetchone()
            if previous is not None:
                if tuple(previous) == (goal["id"], strategy, context, at):
                    return False
                raise ValueError("EX1 event already linked with other context")
            if con.execute("""
                SELECT COUNT(*) FROM mem1_mock_goal_links WHERE goal_row_id=?
            """, (goal["id"],)).fetchone()[0] >= MAX_LINKS_PER_GOAL:
                raise ValueError("per-goal mock attempts capacity reached")
            if con.execute(
                "SELECT COUNT(*) FROM mem1_mock_goal_links"
            ).fetchone()[0] >= MAX_LINKS_TOTAL:
                raise ValueError("total mock attempts capacity reached")
            if con.execute("""
                SELECT 1 FROM mem1_mock_goal_links
                WHERE goal_row_id=? AND strategy=? AND context=? LIMIT 1
            """, (goal["id"], strategy, context)).fetchone() is not None:
                raise ValueError("identical strategy/context is not novel")
            con.execute("""
                INSERT INTO mem1_mock_goal_links(
                    goal_row_id,ex1_row_id,strategy,context,
                    linked_at_epoch_s,source
                ) VALUES (?,?,?,?,?,?)
            """, (goal["id"], event["id"], strategy, context, at, SOURCE))
            return True

    def retract(self, *, goal_id: str, reason: str) -> bool:
        key = _goal_id(goal_id)
        if type(reason) is not str or reason not in RETRACTIONS:
            raise ValueError("invalid mock correction reason")
        with self._memory.conn:
            changed = self._memory.conn.execute("""
                UPDATE mem1_mock_goals
                SET active=0,correction_reason=?,revision=revision+1
                WHERE goal_id=? AND active=1
            """, (reason, key))
            return changed.rowcount == 1

    @staticmethod
    def _as_goal(row) -> MockGoal:
        _goal_id(row["goal_id"])
        _kind_category(row["kind"], row["category"])
        if (row["state"] not in STATES or row["resume_when"] not in RESUME_CONDITIONS
                or row["source"] != SOURCE):
            raise ValueError("untrusted persisted goal")
        return MockGoal(
            goal_id=row["goal_id"], kind=row["kind"], category=row["category"],
            state=row["state"], resume_when=row["resume_when"],
            created_at_epoch_s=float(row["created_at_epoch_s"]),
            updated_at_epoch_s=float(row["updated_at_epoch_s"]),
            revision=int(row["revision"]), corrected=row["active"] != 1,
        )

    def get(self, goal_id: str, *,
            include_withdrawn: bool = False) -> MockGoal | None:
        key = _goal_id(goal_id)
        if type(include_withdrawn) is not bool:
            raise ValueError("invalid include_withdrawn flag")
        row = self._memory.conn.execute("""
            SELECT goal_id,kind,category,state,resume_when,
                   created_at_epoch_s,updated_at_epoch_s,revision,source,active
            FROM mem1_mock_goals WHERE goal_id=?
        """, (key,)).fetchone()
        if row is None or (row["active"] != 1 and not include_withdrawn):
            return None
        return self._as_goal(row)

    def recent(self, *, limit: int = 20,
               include_withdrawn: bool = False) -> tuple[MockGoal, ...]:
        if type(limit) is not int or not 1 <= limit <= MAX_GOALS:
            raise ValueError("invalid goal query limit")
        if type(include_withdrawn) is not bool:
            raise ValueError("invalid include_withdrawn flag")
        if include_withdrawn:
            rows = self._memory.conn.execute("""
                SELECT goal_id,kind,category,state,resume_when,
                       created_at_epoch_s,updated_at_epoch_s,revision,source,active
                FROM mem1_mock_goals WHERE source='mock_fixture_only'
                ORDER BY created_at_epoch_s DESC,id DESC LIMIT ?
            """, (limit,)).fetchall()
        else:
            rows = self._memory.conn.execute("""
                SELECT goal_id,kind,category,state,resume_when,
                       created_at_epoch_s,updated_at_epoch_s,revision,source,active
                FROM mem1_mock_goals
                WHERE source='mock_fixture_only' AND active=1
                ORDER BY created_at_epoch_s DESC,id DESC LIMIT ?
            """, (limit,)).fetchall()
        return tuple(self._as_goal(row) for row in rows)

    def attention_focus(self, *, now_wall_epoch_s: float) -> frozenset[tuple[str, str]]:
        """Read-only DET-1 hints from active, unattempted MOCK goals.

        A linked EX1 proposal blocks the bias regardless of execution,
        refusal, retraction or expiry. Context labels never prove a new
        physical circumstance. No target is added to F2's candidate list.
        """
        now = _epoch(now_wall_epoch_s)
        rows = self._memory.conn.execute("""
            SELECT g.kind,g.category,g.source,g.state,g.active,
                   g.updated_at_epoch_s
            FROM mem1_mock_goals g
            WHERE g.active=1 AND g.state='active'
              AND g.source='mock_fixture_only'
              AND g.updated_at_epoch_s BETWEEN ? AND ?
              AND NOT EXISTS (
                  SELECT 1 FROM mem1_mock_goal_links l
                  WHERE l.goal_row_id=g.id
              )
            ORDER BY g.id ASC LIMIT ?
        """, (now - MAX_FOCUS_AGE_S, now, MAX_GOALS + 1)).fetchall()
        if len(rows) > MAX_GOALS:
            raise ValueError("MEM-1 goal count exceeds the fixture budget")
        focus: set[tuple[str, str]] = set()
        for row in rows:
            _kind_category(row["kind"], row["category"])
            if (row["source"] != SOURCE or row["state"] != "active"
                    or row["active"] != 1):
                raise ValueError("untrusted DET-1 goal evidence")
            if row["kind"] == "observe_category":
                focus.add(("observe", row["category"]))
            elif row["category"] == "unknown":
                focus.add(("inspect", "unknown"))
            # A compare_views goal for a known category does not invent
            # an "inspect" F2 candidate which the sensor did not permit.
        return frozenset(focus)

    def attempts(self, goal_id: str, *,
                 include_withdrawn: bool = False) -> tuple[MockGoalAttempt, ...]:
        key = _goal_id(goal_id)
        if self.get(key, include_withdrawn=include_withdrawn) is None:
            return ()
        rows = self._memory.conn.execute("""
            SELECT l.strategy,l.context,l.linked_at_epoch_s,l.source,
                   e.session,e.sequence,e.status,e.source AS ex1_source,
                   e.active AS ex1_active
            FROM mem1_mock_goal_links l
            JOIN mem1_mock_goals g ON g.id=l.goal_row_id
            LEFT JOIN ex1_mock_experiences e ON e.id=l.ex1_row_id
            WHERE g.goal_id=? AND l.source='mock_fixture_only'
            ORDER BY l.id DESC LIMIT ?
        """, (key, MAX_LINKS_PER_GOAL)).fetchall()
        result = []
        for row in rows:
            if (row["strategy"] not in STRATEGIES
                    or row["context"] not in CONTEXTS or row["source"] != SOURCE):
                raise ValueError("untrusted mock attempt link")
            if row["session"] is None:
                provenance, resolution = "missing_ex1", "unavailable"
            elif row["ex1_source"] != SOURCE or row["ex1_active"] != 1:
                provenance, resolution = "retracted_or_untrusted_ex1", "unavailable"
            elif row["status"] in {
                "proposed","mock_executed","refused","interrupted",
            }:
                provenance, resolution = "active_mock_ex1", row["status"]
            else:
                raise ValueError("untrusted mock EX1 resolution")
            result.append(MockGoalAttempt(
                goal_id=key, strategy=row["strategy"], context=row["context"],
                linked_at_epoch_s=float(row["linked_at_epoch_s"]),
                evidence_state=provenance, mock_resolution=resolution,
                session=row["session"] if resolution != "unavailable" else None,
                sequence=(int(row["sequence"]) if resolution != "unavailable"
                          else None),
            ))
        return tuple(result)
