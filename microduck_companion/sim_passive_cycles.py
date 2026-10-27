"""P2b: passive multi-cycle cognition using official simulated telemetry only.

Reads robotd/tofd through sim_bridge; NEVER sends an intent or motor RPC.
A selected intention is NOT an executed action or an observed outcome.
The Unix-socket role is a simulator claim, not authentication of hardware.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
import time
import uuid

from .autonomy import AutonomyBrain, Plan
from .episodic_memory import ExperienceMemory
from .perception import PerceptionSnapshot
from .sim_bridge import (
    DEFAULT_MAX_AGE_S, SimulatorTelemetry, read_simulator_telemetry,
)

_MOTION = frozenset({"explore", "play_with_object"})
_QUALITY = frozenset({"coherent", "invalid_or_missing", "nonadvancing_frame"})
# Comparison windows are for *historical cognition*, never sensor TTL or
# physical safety. Their bound limits how far back a prior simulator report
# may influence a descriptive attention hint.
MAX_CONTEXT_AGE_S = 60.
_ATTENTION = frozenset({"not_evaluated", "abstain", "idle", "rest", "observe_status"})
_COMPARISON = frozenset({
    "not_evaluated", "no_reference", "interrupted", "incompatible_clock",
    "expired", "unknown_battery", "stable_band", "low_to_normal",
    "normal_to_low",
})


@dataclass(frozen=True)
class PassiveSimCycle:
    session: str
    sequence: int
    plan: Plan
    quality: str
    disposition: str
    depth_seq: int | None
    battery_pct: float | None
    attention: str = "not_evaluated"
    comparison: str = "not_evaluated"
    reference_id: int | None = None


class PassiveSimCycleRunner:
    """Persist proposed decisions and data quality, never a simulated success.

    A resumed session checks frame progression against its last good sample.
    Start a new session after a simulator restart (ToF sequence may reset).
    No raw ToF, audio, images, individual identities or rewards are retained.
    """

    def __init__(self, memory: ExperienceMemory, *,
                 session: str | None = None) -> None:
        self.memory = memory
        self.session = uuid.uuid4().hex if session is None else session
        if (not isinstance(self.session, str)
                or not 1 <= len(self.session) <= 64
                or not self.session.isascii()
                or not all(c.isalnum() or c in "-_" for c in self.session)):
            raise ValueError("invalid passive simulator session")
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_passive_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    observed_at REAL NOT NULL,
                    quality TEXT NOT NULL
                        CHECK(quality IN (
                            'coherent','invalid_or_missing','nonadvancing_frame')),
                    intention TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    depth_seq INTEGER,
                    state_t_ns INTEGER,
                    depth_t_ns INTEGER,
                    battery_pct REAL,
                    source TEXT NOT NULL CHECK(source='simulator_ipc'),
                    outcome TEXT NOT NULL CHECK(outcome='no_action_executed'),
                    reward REAL CHECK(reward IS NULL),
                    motor_commands INTEGER NOT NULL DEFAULT 0
                        CHECK(motor_commands=0),
                    attention TEXT NOT NULL DEFAULT 'not_evaluated'
                        CHECK(attention IN (
                            'not_evaluated','abstain','idle','rest','observe_status')),
                    comparison TEXT NOT NULL DEFAULT 'not_evaluated'
                        CHECK(comparison IN (
                            'not_evaluated','no_reference','interrupted',
                            'incompatible_clock','expired','unknown_battery',
                            'stable_band','low_to_normal','normal_to_low')),
                    reference_id INTEGER CHECK(reference_id IS NULL OR reference_id>0),
                    UNIQUE(session, sequence)
                )""")
            # Add only three columns to P2b's existing journal. No second DB,
            # second writer, history purge or fabricated simulator event.
            existing = {
                row["name"] for row in memory.conn.execute(
                    "PRAGMA table_info(sim_passive_cycles)"
                )
            }
            additions = {
                "attention": """TEXT NOT NULL DEFAULT 'not_evaluated'
                    CHECK(attention IN (
                        'not_evaluated','abstain','idle','rest','observe_status'))""",
                "comparison": """TEXT NOT NULL DEFAULT 'not_evaluated'
                    CHECK(comparison IN (
                        'not_evaluated','no_reference','interrupted',
                        'incompatible_clock','expired','unknown_battery',
                        'stable_band','low_to_normal','normal_to_low'))""",
                "reference_id": "INTEGER CHECK(reference_id IS NULL OR reference_id>0)",
            }
            for column, definition in additions.items():
                if column not in existing:
                    memory.conn.execute(
                        f"ALTER TABLE sim_passive_cycles ADD COLUMN {column} {definition}"
                    )
        self.brain = AutonomyBrain(memory)
        previous = memory.conn.execute(
            "SELECT intention FROM sim_passive_cycles ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.brain.previous_intention = previous[0] if previous else None
        last = memory.conn.execute(
            """SELECT sequence,observed_at FROM sim_passive_cycles
               WHERE session=? ORDER BY sequence DESC LIMIT 1""",
            (self.session,),
        ).fetchone()
        self.sequence = int(last["sequence"]) + 1 if last else 1
        self._last_observed = float(last["observed_at"]) if last else None
        good = memory.conn.execute(
            """SELECT depth_seq,state_t_ns,depth_t_ns FROM sim_passive_cycles
               WHERE session=? AND quality='coherent'
               ORDER BY sequence DESC LIMIT 1""",
            (self.session,),
        ).fetchone()
        self._last_depth_seq = good["depth_seq"] if good else None
        self._last_state_ns = good["state_t_ns"] if good else None
        self._last_depth_ns = good["depth_t_ns"] if good else None

    def _prior_power_context(self, *, now: float,
                             depth_seq: int, state_ns: int | None,
                             depth_ns: int | None,
                             battery: float) -> tuple[str, int | None, bool | None]:
        """Recall only the LAST journal row, not an unbounded search or sensor.

        Do not bridge an invalid sample, reset simulator frame sequence or a
        different monotonic clock. Old P2b rows are accepted *as history* only
        when their original source, no-action outcome and timestamps agree.
        """
        row = self.memory.conn.execute(
            """SELECT id, session, observed_at, quality, source, outcome,
                      motor_commands, reward, depth_seq, state_t_ns,
                      depth_t_ns, battery_pct
               FROM sim_passive_cycles ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            return "no_reference", None, None
        if (row["quality"] != "coherent"
                or row["source"] != "simulator_ipc"
                or row["outcome"] != "no_action_executed"
                or row["motor_commands"] != 0
                or row["reward"] is not None):
            return "interrupted", None, None
        # Time base may change across processes or simulator restarts.
        if row["observed_at"] >= now:
            return "incompatible_clock", None, None
        if now - row["observed_at"] > MAX_CONTEXT_AGE_S:
            return "expired", None, None
        if (row["depth_seq"] is None or depth_seq <= row["depth_seq"]
                or (state_ns is not None and row["state_t_ns"] is not None
                    and state_ns <= row["state_t_ns"])
                or (depth_ns is not None and row["depth_t_ns"] is not None
                    and depth_ns <= row["depth_t_ns"])):
            return "incompatible_clock", None, None
        if row["battery_pct"] is None:
            return "unknown_battery", None, None
        prior_low = row["battery_pct"] <= 15
        current_low = battery <= 15
        comparison = ("stable_band" if prior_low == current_low else
                      "low_to_normal" if prior_low else "normal_to_low")
        return comparison, int(row["id"]), prior_low

    def step(self, telemetry: SimulatorTelemetry, *, now: float,
             max_age_s: float = DEFAULT_MAX_AGE_S) -> PassiveSimCycle:
        if type(telemetry) is not SimulatorTelemetry:
            raise TypeError("P2b needs parsed simulator daemon readings")
        if (type(now) not in (int, float) or not math.isfinite(now)
                or now < 0 or (self._last_observed is not None
                               and now <= self._last_observed)):
            raise ValueError("cycle times must advance monotonically")

        # The existing bridge rejects stale, inconsistent, unsafe or missing
        # daemon signals; its only possible event is a verified battery value.
        snapshot = telemetry.to_snapshot(now=now, max_age_s=max_age_s)
        coherent = telemetry._coherent(now, max_age_s)
        quality = "coherent" if coherent else "invalid_or_missing"
        state, depth = telemetry.state, telemetry.depth
        if coherent:
            assert depth is not None and state is not None
            if (self._last_depth_seq is not None
                    and depth.seq <= self._last_depth_seq) or (
                    state.t_ns is not None and self._last_state_ns is not None
                    and state.t_ns <= self._last_state_ns) or (
                    depth.t_ns is not None and self._last_depth_ns is not None
                    and depth.t_ns <= self._last_depth_ns):
                quality = "nonadvancing_frame"

        if quality != "coherent":
            # Even a valid *previous* low-battery reading must not be reused.
            # An empty snapshot forces halt, not a synthetic safety clearance.
            snapshot = PerceptionSnapshot("simulator", (), now)

        plan = self.brain.choose_from_snapshot(snapshot, now=now)
        if quality != "coherent" and plan.intention != "halt":
            raise RuntimeError("invalid simulator telemetry must halt")
        disposition = (
            "blocked_motion" if plan.intention in _MOTION
            else "observation_only"
        )
        battery = (telemetry.health.battery_pct
                   if quality == "coherent" and telemetry.health else None)
        comparison, reference_id, prior_low = (
            ("interrupted", None, None) if quality != "coherent" else
            ("unknown_battery", None, None) if battery is None else
            self._prior_power_context(
                now=now, depth_seq=depth.seq,
                state_ns=state.t_ns, depth_ns=depth.t_ns, battery=battery,
            )
        )
        attention = self.brain.consider_simulator_status(
            quality=quality, battery_pct=battery, prior_battery_low=prior_low,
            comparable_memory=reference_id is not None,
        )
        # The cognitive hint is strictly descriptive; no extra decision,
        # change to object preference, motion, PC request, or OEM signal.
        with self.memory.conn:
            self.memory.conn.execute(
                """INSERT INTO sim_passive_cycles(
                       session,sequence,observed_at,quality,intention,
                       disposition,depth_seq,state_t_ns,depth_t_ns,battery_pct,
                       source,outcome,reward,motor_commands,
                       attention,comparison,reference_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,
                           'simulator_ipc','no_action_executed',NULL,0,?,?,?)""",
                (self.session, self.sequence, now, quality, plan.intention,
                 disposition, depth.seq if depth else None,
                 state.t_ns if state else None, depth.t_ns if depth else None,
                 battery, attention, comparison, reference_id),
            )

        result = PassiveSimCycle(
            self.session, self.sequence, plan, quality, disposition,
            depth.seq if depth else None, battery,
            attention, comparison, reference_id,
        )
        self.sequence += 1
        self._last_observed = now
        if quality == "coherent":
            assert state is not None and depth is not None
            self._last_depth_seq = depth.seq
            self._last_state_ns = state.t_ns
            self._last_depth_ns = depth.t_ns
        return result

    def history(self) -> list[dict]:
        rows = self.memory.conn.execute(
            """SELECT session,sequence,observed_at,quality,intention,
                      disposition,depth_seq,battery_pct,source,outcome,reward,
                      motor_commands,attention,comparison,reference_id
               FROM sim_passive_cycles ORDER BY id"""
        ).fetchall()
        return [dict(row) for row in rows]


def run_session(state_dir: Path, database: Path, *, session: str,
                cycles: int = 3, interval_s: float = .4,
                timeout_s: float = 3.0) -> dict:
    if type(cycles) is not int or not 2 <= cycles <= 20:
        raise ValueError("cycles must be between 2 and 20")
    if (type(interval_s) not in (int, float) or not math.isfinite(interval_s)
            or not 0 <= interval_s <= 2):
        raise ValueError("interval must be in [0, 2] seconds")
    if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
            or not 0 < timeout_s <= 10):
        raise ValueError("timeout must be in (0, 10] seconds")
    memory = ExperienceMemory(database)
    try:
        runner = PassiveSimCycleRunner(memory, session=session)
        records = []
        for index in range(cycles):
            if index:
                time.sleep(interval_s)
            # New connections and fresh observations at *each* cycle.
            # This function has only three read/subscribe RPCs whitelisted.
            telemetry = read_simulator_telemetry(state_dir, timeout_s=timeout_s)
            records.append(runner.step(telemetry, now=time.monotonic()))
        history = runner.history()
        return {
            "source": "official_simulator_sockets_unverified_hardware",
            "session": runner.session,
            "cycles": [
                {"sequence": r.sequence, "quality": r.quality,
                 "intention": r.plan.intention, "disposition": r.disposition,
                 "depth_seq": r.depth_seq, "attention": r.attention,
                 "comparison": r.comparison, "reference_id": r.reference_id}
                for r in records
            ],
            "journal_count": len(history),
            "coherent_cycles": sum(r.quality == "coherent" for r in records),
            "motor_commands_issued": 0,
            "verified_consequences": 0,
            "hardware_validated": False,
            "floor_certified": False,
        }
    finally:
        memory.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P2b passive MuJoCo cognition; no motor commands")
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".cache" / "duck-sim")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--session", default="sim-passive")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--interval", type=float, default=.4)
    parser.add_argument("--timeout", type=float, default=3.)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_session(
            args.state_dir, args.database, session=args.session,
            cycles=args.cycles, interval_s=args.interval, timeout_s=args.timeout,
        )
    except (ValueError, TypeError) as exc:
        print(f"invalid P2b configuration: {exc}", file=sys.stderr)
        return 2
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    # Invalid telemetry is correctly fail-closed, but is not a passing
    # integration demonstration of multiple *fresh* simulator cycles.
    return 0 if result["coherent_cycles"] == args.cycles else 1


if __name__ == "__main__":
    raise SystemExit(main())
