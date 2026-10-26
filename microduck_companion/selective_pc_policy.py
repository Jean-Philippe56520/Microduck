"""F5-C: sparse, explicitly opted-in PC consultations on the EXISTING SQLite.

The local F5-A intent exists before this gate. Persist only random request-ID
hashes, fictional trigger type, time and transport outcome. Never persist
tracks, names, category observations, prompts, images or model content.
No robotd, sensor, speaker or network access in the policy itself.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import sqlite3
from typing import TYPE_CHECKING

from .episodic_memory import ExperienceMemory
from .pc_hypothesis_contract import OptionalPCAdvisory, finish_optional_pc_cycle

if TYPE_CHECKING:
    from .ollama_local_client import OptionalOllamaWorker

COOLDOWN_S = 60.
WINDOW_S = 600.
WINDOW_LIMIT = 2
DAY_S = 86400.
DAY_LIMIT = 8
PENDING_GRACE_S = 3.
BACKOFF_S = 300.
FAILURE_THRESHOLD = 2
_FAILURES = frozenset({"pc_unavailable", "response_rejected"})
_RESULTS = _FAILURES | {"hypotheses_unverified"}
_TRIGGERS = frozenset({"unknown", "conflict"})


def _finite(x: object) -> bool:
    return type(x) in (int, float) and math.isfinite(x) and x >= 0


def _digest(request_id: str) -> str:
    return hashlib.sha256(request_id.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class ConsultationChoice:
    allowed: bool
    reason: str
    local_intention: str
    motor_commands_issued: int = 0
    network_commands_issued: int = 0

    def __post_init__(self) -> None:
        if (type(self.allowed) is not bool or not self.reason
                or type(self.local_intention) is not str
                or self.motor_commands_issued != 0
                or self.network_commands_issued != 0):
            raise ValueError("a quota decision cannot actuate the robot")


class SelectivePCPolicy:
    """Atomic reservations across processes; all errors fail closed.

    Uses shared ExperienceMemory SQLite, with a 20ms busy timeout. This is
    only a soft limit; no deterministic latency on a real RK3566 is claimed.
    """

    def __init__(self, memory: ExperienceMemory):
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("existing ExperienceMemory required")
        self.memory = memory
        c = memory.conn
        c.execute("PRAGMA busy_timeout=20")
        c.executescript("""
            CREATE TABLE IF NOT EXISTS f5c_pc_uses (
                request_hash TEXT PRIMARY KEY CHECK(length(request_hash)=64),
                at_epoch REAL NOT NULL,
                trigger TEXT NOT NULL CHECK(trigger IN ('unknown','conflict')),
                status TEXT NOT NULL CHECK(status IN ('pending','pc_unavailable',
                    'response_rejected','hypotheses_unverified'))
            );
            CREATE INDEX IF NOT EXISTS idx_f5c_pc_at
                ON f5c_pc_uses(at_epoch);
            CREATE TABLE IF NOT EXISTS f5c_pc_state (
                id INTEGER PRIMARY KEY CHECK(id=1),
                last_wall REAL NOT NULL DEFAULT 0,
                failures INTEGER NOT NULL DEFAULT 0,
                backoff_until REAL NOT NULL DEFAULT 0
            );
            INSERT OR IGNORE INTO f5c_pc_state(id) VALUES (1);
        """)
        c.commit()

    @staticmethod
    def _choice(cycle: OptionalPCAdvisory, yes: bool,
                reason: str) -> ConsultationChoice:
        return ConsultationChoice(yes, reason, cycle.local_intent.intention)

    @staticmethod
    def _trigger(cycle: OptionalPCAdvisory) -> str | None:
        if (cycle.status != "pending_transport" or cycle.request is None
                or cycle.local_intent.intention != "inspect"):
            return None
        statuses = {o.status for o in cycle.request.observations}
        if statuses == {"unknown"}:
            return "unknown"
        if "conflict" in statuses and statuses <= _TRIGGERS:
            return "conflict"
        return None

    def reserve(self, cycle: OptionalPCAdvisory, *,
                now_monotonic_s: float, now_wall_epoch_s: float,
                pc_opt_in: bool = False) -> ConsultationChoice:
        """No opt-in or unsafe/unavailable state => no remote consultation."""
        if not isinstance(cycle, OptionalPCAdvisory):
            raise TypeError("F5-A advisory required")
        if type(pc_opt_in) is not bool:
            raise ValueError("pc_opt_in must be a boolean")
        if not _finite(now_monotonic_s) or not _finite(now_wall_epoch_s):
            raise ValueError("invalid clocks")
        if not pc_opt_in:
            return self._choice(cycle, False, "pc_disabled")
        trigger = self._trigger(cycle)
        if trigger is None:
            return self._choice(cycle, False, "not_eligible")
        req = cycle.request
        if not req.created_monotonic_s <= now_monotonic_s < req.expires_monotonic_s:
            return self._choice(cycle, False, "request_expired")
        c = self.memory.conn
        try:
            c.execute("BEGIN IMMEDIATE")
            state = c.execute("SELECT * FROM f5c_pc_state WHERE id=1").fetchone()
            if state is None:
                raise sqlite3.DatabaseError("missing quota state")
            if now_wall_epoch_s < state["last_wall"]:
                c.rollback()
                return self._choice(cycle, False, "wall_clock_rollback")
            c.execute("UPDATE f5c_pc_state SET last_wall=? WHERE id=1",
                      (now_wall_epoch_s,))
            # Recover a crashed consultation without replaying its result.
            expired = c.execute("""
                SELECT COUNT(*) FROM f5c_pc_uses
                WHERE status='pending' AND at_epoch < ?
            """, (now_wall_epoch_s-PENDING_GRACE_S,)).fetchone()[0]
            if expired:
                c.execute("""
                    UPDATE f5c_pc_uses SET status='pc_unavailable'
                    WHERE status='pending' AND at_epoch < ?
                """, (now_wall_epoch_s-PENDING_GRACE_S,))
                failures = state["failures"] + expired
                backoff = state["backoff_until"]
                if failures >= FAILURE_THRESHOLD:
                    backoff = max(backoff, now_wall_epoch_s + BACKOFF_S)
                c.execute("""
                    UPDATE f5c_pc_state
                    SET failures=?, backoff_until=? WHERE id=1
                """, (failures, backoff))
            else:
                backoff = state["backoff_until"]
            c.execute("DELETE FROM f5c_pc_uses WHERE at_epoch < ?",
                      (now_wall_epoch_s-DAY_S,))
            h = _digest(req.request_id)
            reason = None
            if c.execute("SELECT 1 FROM f5c_pc_uses WHERE request_hash=?",
                         (h,)).fetchone():
                reason = "duplicate_request"
            elif now_wall_epoch_s < backoff:
                reason = "circuit_open"
            elif c.execute(
                "SELECT 1 FROM f5c_pc_uses WHERE status='pending' LIMIT 1"
            ).fetchone():
                reason = "already_pending"
            else:
                limits = c.execute("""
                    SELECT MAX(at_epoch) last,
                     COALESCE(SUM(at_epoch > ?),0) recent, COUNT(*) daily
                    FROM f5c_pc_uses
                """, (now_wall_epoch_s-WINDOW_S,)).fetchone()
                if (limits["last"] is not None
                        and now_wall_epoch_s-limits["last"] < COOLDOWN_S):
                    reason = "cooldown"
                elif limits["recent"] >= WINDOW_LIMIT:
                    reason = "window_quota"
                elif limits["daily"] >= DAY_LIMIT:
                    reason = "daily_quota"
            if reason is None:
                c.execute("""
                    INSERT INTO f5c_pc_uses(request_hash,at_epoch,trigger,status)
                    VALUES (?,?,?,'pending')
                """, (h,now_wall_epoch_s,trigger))
            c.commit()
            return self._choice(cycle, reason is None, reason or trigger)
        except sqlite3.Error:
            if c.in_transaction:
                c.rollback()
            return self._choice(cycle, False, "storage_unavailable")

    def complete(self, request_id: str, *, status: str,
                 now_wall_epoch_s: float) -> bool:
        """Idempotent status-only accounting; cannot authorize new actions."""
        if (type(request_id) is not str or len(request_id) != 32
                or any(x not in "0123456789abcdef" for x in request_id)):
            raise ValueError("invalid random request ID")
        if type(status) is not str or status not in _RESULTS:
            raise ValueError("invalid consultation result")
        if not _finite(now_wall_epoch_s):
            raise ValueError("invalid wall clock")
        c = self.memory.conn
        try:
            c.execute("BEGIN IMMEDIATE")
            state = c.execute("SELECT * FROM f5c_pc_state WHERE id=1").fetchone()
            if state is None or now_wall_epoch_s < state["last_wall"]:
                c.rollback()
                return False
            updated = c.execute("""
                UPDATE f5c_pc_uses SET status=?
                WHERE request_hash=? AND status='pending' AND at_epoch <= ?
                  AND at_epoch >= ?
            """, (status,_digest(request_id),now_wall_epoch_s,
                  now_wall_epoch_s-PENDING_GRACE_S))
            if updated.rowcount != 1:
                c.rollback()
                return False
            failures = (state["failures"]+1 if status in _FAILURES else 0)
            backoff = state["backoff_until"]
            if failures >= FAILURE_THRESHOLD:
                backoff = max(backoff,now_wall_epoch_s+BACKOFF_S)
            if status == "hypotheses_unverified":
                backoff = 0.
            c.execute("""
                UPDATE f5c_pc_state SET last_wall=?,failures=?,
                    backoff_until=? WHERE id=1
            """, (now_wall_epoch_s,failures,backoff))
            c.commit()
            return True
        except sqlite3.Error:
            if c.in_transaction:
                c.rollback()
            return False

    def counts(self) -> dict[str,int]:
        """Only anonymous transport outcomes, no model content."""
        rows = self.memory.conn.execute(
            "SELECT status, COUNT(*) n FROM f5c_pc_uses GROUP BY status"
        ).fetchall()
        return {row["status"]:row["n"] for row in rows}


class SelectivePCBridge:
    """Use the F5-B nonblocking worker AFTER the local F5-A decision."""

    def __init__(self, policy: SelectivePCPolicy,
                 worker: OptionalOllamaWorker) -> None:
        from .ollama_local_client import OptionalOllamaWorker
        if not isinstance(policy, SelectivePCPolicy) or not isinstance(
                worker, OptionalOllamaWorker):
            raise TypeError("existing F5-C policy and F5-B worker required")
        self.policy, self.worker = policy, worker
        self._pending: OptionalPCAdvisory | None = None

    def submit(self, cycle: OptionalPCAdvisory, *,
               now_monotonic_s: float, now_wall_epoch_s: float,
               pc_opt_in: bool = False) -> ConsultationChoice:
        if not isinstance(cycle, OptionalPCAdvisory):
            raise TypeError("F5-A cycle required")
        if self._pending is not None:
            return ConsultationChoice(False, "bridge_busy",
                                      cycle.local_intent.intention)
        decision = self.policy.reserve(
            cycle, now_monotonic_s=now_monotonic_s,
            now_wall_epoch_s=now_wall_epoch_s, pc_opt_in=pc_opt_in,
        )
        if not decision.allowed:
            return decision
        try:
            sent = self.worker.submit(cycle)
        except (RuntimeError,ValueError):
            sent = False
        if not sent:
            self.policy.complete(cycle.request.request_id,
                                 status="pc_unavailable",
                                 now_wall_epoch_s=now_wall_epoch_s)
            return ConsultationChoice(False,"worker_unavailable",
                                      cycle.local_intent.intention)
        self._pending = cycle
        return decision

    def poll(self, *, now_wall_epoch_s: float) -> OptionalPCAdvisory | None:
        if not _finite(now_wall_epoch_s):
            raise ValueError("invalid wall clock")
        cycle = self._pending
        if cycle is None:
            return None
        try:
            answer = self.worker.poll()
        except Exception:
            answer = finish_optional_pc_cycle(
                cycle,None,received_monotonic_s=0.,
            )
        if answer is None:
            return None
        self._pending = None
        if (not isinstance(answer,OptionalPCAdvisory)
                or answer.request != cycle.request
                or answer.local_intent != cycle.local_intent
                or answer.status not in _RESULTS):
            answer = finish_optional_pc_cycle(
                cycle,None,received_monotonic_s=0.,
            )
        if not self.policy.complete(cycle.request.request_id,
                                    status=answer.status,
                                    now_wall_epoch_s=now_wall_epoch_s):
            return finish_optional_pc_cycle(
                cycle,None,received_monotonic_s=0.,
            )
        return answer
