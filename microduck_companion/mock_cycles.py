"""P2a: persistent MOCK-only cognitive cycles; no robot/motor/network APIs.

All outcomes are explicitly scripted mock evidence. A plan never means that
an actuator executed it. No LLM statement can promote mock data to a fact.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
import uuid

from .autonomy import AutonomyBrain, Plan
from .episodic_memory import ExperienceMemory
from .perception import PerceptionSnapshot, DETECTION_CONFIDENCE

MOTION = frozenset({"explore", "play_with_object"})
RESULT_REWARD = {"positive": 0.4, "negative": -0.4}


@dataclass(frozen=True)
class MockConsequence:
    """Explicit fictional observation; never inferred from a chosen plan."""

    target: str
    result: str
    observed_at: float
    source: str = "mock"

    def __post_init__(self) -> None:
        if (not isinstance(self.target, str) or not self.target.strip()
                or len(self.target) > 128):
            raise ValueError("tracked mock target required")
        if self.result not in RESULT_REWARD or self.source != "mock":
            raise ValueError("unsupported or untrusted mock consequence")
        if (type(self.observed_at) not in (float, int)
                or not math.isfinite(self.observed_at) or self.observed_at < 0):
            raise ValueError("invalid mock consequence timestamp")


@dataclass(frozen=True)
class MockCycle:
    session: str
    sequence: int
    plan: Plan
    disposition: str
    outcome: str
    reward: float | None
    preference_after: float | None


class MockCycleRunner:
    """Offline loop; SQLite persists mock outcomes across runner restarts."""

    def __init__(self, memory: ExperienceMemory, *,
                 session: str | None = None) -> None:
        self.memory = memory
        self.session = session or uuid.uuid4().hex
        if (not 1 <= len(self.session) <= 64 or not self.session.isascii()
                or not all(c.isalnum() or c in "-_" for c in self.session)):
            raise ValueError("invalid local mock session")
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS mock_cognitive_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session TEXT NOT NULL, sequence INTEGER NOT NULL,
                    observed_at REAL NOT NULL,
                    intention TEXT NOT NULL, target TEXT,
                    disposition TEXT NOT NULL, outcome TEXT NOT NULL,
                    reward REAL, source TEXT NOT NULL CHECK(source='mock'),
                    UNIQUE(session,sequence)
                )""")
        self.brain = AutonomyBrain(memory)
        row = memory.conn.execute(
            "SELECT intention FROM mock_cognitive_cycles ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.brain.previous_intention = row[0] if row else None
        row = memory.conn.execute(
            "SELECT COALESCE(MAX(sequence),0) FROM mock_cognitive_cycles "
            "WHERE session=?", (self.session,),
        ).fetchone()
        self.sequence = int(row[0]) + 1
        self._last_observed = None

    @staticmethod
    def _mock(snapshot: PerceptionSnapshot) -> None:
        if (not isinstance(snapshot, PerceptionSnapshot)
                or snapshot.environment != "mock"
                or any(e.source != "mock" for e in snapshot.events)):
            raise ValueError("P2a accepts only explicitly mocked perceptions")

    def step(self, snapshot: PerceptionSnapshot, *, now: float,
             followup: PerceptionSnapshot | None = None,
             consequence: MockConsequence | None = None) -> MockCycle:
        self._mock(snapshot)
        if (type(now) not in (int, float) or not math.isfinite(now)
                or now < snapshot.observed_at):
            raise ValueError("invalid monotonic mock decision time")
        if self._last_observed is not None and snapshot.observed_at <= self._last_observed:
            raise ValueError("mock snapshots must advance")
        if (followup is None) != (consequence is None):
            raise ValueError("mock outcome requires an independent followup")
        if followup is not None:
            self._mock(followup)
            if not isinstance(consequence, MockConsequence):
                raise ValueError("explicit mock consequence required")
            if not (snapshot.observed_at < consequence.observed_at
                    <= followup.observed_at <= now
                    and followup.observed_at - snapshot.observed_at <= 2.0):
                raise ValueError("expired or non-monotonic mock consequence")
            if not any(
                e.kind == "object_label" and e.track_id == consequence.target
                and e.confidence >= DETECTION_CONFIDENCE
                and e.value != "unknown" and e.fresh_at(now)
                for e in followup.events
            ):
                raise ValueError("no fresh matching mock track corroborates outcome")

        plan = self.brain.choose_from_snapshot(snapshot, now=now)
        reward = None
        if plan.intention in MOTION:
            if consequence is not None:
                raise ValueError("motor intentions cannot receive mock feedback")
            disposition, outcome = "blocked_motion", "no_motor_command_issued"
        elif consequence is not None:
            if plan.intention != "inspect_object" or plan.target != consequence.target:
                raise ValueError("mock outcome is unrelated to selected inspection")
            disposition, outcome = "mock_feedback", "explicit_mock_" + consequence.result
            reward = RESULT_REWARD[consequence.result]
        elif plan.intention == "inspect_object":
            disposition, outcome = "unverified", "no_mock_consequence_provided"
        else:
            disposition, outcome = "observation_only", "no_actuation_or_causal_claim"

        updated = None
        with self.memory.conn:
            # The unique pair prevents a replayed cycle rewarding twice.
            self.memory.conn.execute(
                """INSERT INTO mock_cognitive_cycles(
                      session,sequence,observed_at,intention,target,disposition,
                      outcome,reward,source) VALUES (?,?,?,?,?,?,?,?,'mock')""",
                (self.session, self.sequence, snapshot.observed_at,
                 plan.intention, plan.target, disposition, outcome, reward),
            )
            if reward is not None:
                row = self.memory.conn.execute(
                    "SELECT preference FROM objects WHERE identifier=? "
                    "AND label_source='mock' AND label!='unknown'",
                    (plan.target,),
                ).fetchone()
                if row is None:
                    raise ValueError("cannot reward an unverified mock category")
                updated = max(-1., min(1., float(row[0]) * .85 + reward * .15))
                self.memory.conn.execute(
                    "UPDATE objects SET preference=? WHERE identifier=?",
                    (updated, plan.target),
                )
                self.memory.conn.execute(
                    """INSERT INTO experiences(
                          timestamp,object_id,action,outcome,note)
                       VALUES (?,?,?,?,'explicit_mock_feedback')""",
                    (time.time(), plan.target, plan.intention, reward),
                )

        record = MockCycle(
            self.session, self.sequence, plan, disposition, outcome,
            reward, updated,
        )
        self.sequence += 1
        self._last_observed = snapshot.observed_at
        return record

    def history(self) -> list[dict]:
        """Entire persistent synthetic record; no robot actions were executed."""
        rows = self.memory.conn.execute(
            """SELECT session,sequence,observed_at,intention,target,
                      disposition,outcome,reward,source
               FROM mock_cognitive_cycles ORDER BY id"""
        ).fetchall()
        return [dict(row) for row in rows]
