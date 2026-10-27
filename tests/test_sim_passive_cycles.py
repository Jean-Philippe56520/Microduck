"""P2b passive cycles: synthetic daemon fixtures plus actual Unix RPC stub I/O.

No test uses MuJoCo or a physical robot; GitHub Actions MuJoCo tests these
against the official simulated services separately.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.sim_bridge import SimulatorTelemetry
from microduck_companion.sim_ipc import DepthReading, HealthReading, StateReading
from microduck_companion.sim_passive_cycles import (
    PassiveSimCycleRunner, run_session,
)


def bundle(*, at: float = 100., seq: int = 10, battery: float | None = 85.,
           healthy: bool = True) -> SimulatorTelemetry:
    stamp = at - .05
    t_ns = seq * 1_000_000
    return SimulatorTelemetry(
        health=HealthReading(healthy, battery, 50., 49.9, 0, stamp),
        state=StateReading(False, False, 49.9, 0, t_ns, stamp),
        depth=DepthReading(seq, (1400,) * 64, (5,) * 64, t_ns + 10_000,
                           stamp),
    )


class PassiveCycleUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Path(self.tmp.name) / "p2b.sqlite3"
        self.memory = ExperienceMemory(self.database)
        self.addCleanup(self.memory.close)

    def test_three_fresh_cycles_are_passive_and_persistent(self):
        runner = PassiveSimCycleRunner(self.memory, session="test")
        cycles = [
            runner.step(bundle(at=t, seq=i), now=t)
            for t, i in ((100., 10), (101., 11), (102., 12))
        ]
        self.assertEqual(["coherent"] * 3, [c.quality for c in cycles])
        self.assertEqual(["halt"] * 3, [c.plan.intention for c in cycles])
        self.assertEqual(["observation_only"] * 3,
                         [c.disposition for c in cycles])
        self.assertEqual([1, 2, 3], [c.sequence for c in cycles])
        self.assertEqual([10, 11, 12],
                         [c["depth_seq"] for c in runner.history()])
        self.assertEqual({"simulator_ipc"},
                         {c["source"] for c in runner.history()})
        self.assertEqual({"no_action_executed"},
                         {c["outcome"] for c in runner.history()})
        self.assertEqual({0}, {c["motor_commands"] for c in runner.history()})
        self.assertEqual({None}, {c["reward"] for c in runner.history()})
        # Three *proposals* are already recorded in sim_passive_cycles;
        # do not also count them as executed legacy experiences.
        self.assertEqual(3, len(runner.history()))
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(
            0, self.memory.conn.execute(
                "SELECT count(*) FROM sim_motion_trials"
            ).fetchone()[0])
        self.assertEqual(
            0, self.memory.conn.execute(
                "SELECT count(*) FROM intent_preferences"
            ).fetchone()[0])
        self.assertEqual(
            0, self.memory.conn.execute(
                "SELECT count(*) FROM objects"
            ).fetchone()[0])

    def test_restart_same_session_resumes_sequence_and_rejects_duplicate(self):
        a = PassiveSimCycleRunner(self.memory, session="resumable")
        self.assertEqual(1, a.step(bundle(seq=3), now=100.).sequence)
        # Close and reopen durable SQLite: not merely a new runner with RAM state.
        self.memory.close()
        self.addCleanup(lambda: None)
        reopened = ExperienceMemory(self.database)
        try:
            b = PassiveSimCycleRunner(reopened, session="resumable")
            self.assertEqual(2, b.sequence)
            self.assertEqual("halt", b.brain.previous_intention)
            duplicate = b.step(bundle(at=101., seq=3), now=101.)
            self.assertEqual("nonadvancing_frame", duplicate.quality)
            self.assertEqual("halt", duplicate.plan.intention)
            self.assertEqual("coherent",
                             b.step(bundle(at=102., seq=4), now=102.).quality)
            self.assertEqual([1, 2, 3],
                             [x["sequence"] for x in b.history()])
            self.assertEqual({None}, {x["reward"] for x in b.history()})
        finally:
            reopened.close()

    def test_missing_stale_unhealthy_and_incoherent_sources_all_halt(self):
        t = 100.
        examples = [
            SimulatorTelemetry(),
            replace(bundle(), depth=None, errors=("tofd telemetry unavailable",)),
            replace(bundle(), health=replace(bundle().health, healthy=False)),
            replace(bundle(), state=replace(bundle().state, fallen=True)),
            replace(bundle(), state=replace(bundle().state, limp=True)),
            replace(bundle(), state=replace(bundle().state, achieved_hz=39.)),
            replace(bundle(), depth=replace(bundle().depth, received_at=80.)),
            replace(bundle(), depth=replace(bundle().depth, t_ns=3_000_000_000)),
            replace(bundle(), health=replace(bundle().health, battery_pct=None)),
        ]
        runner = PassiveSimCycleRunner(self.memory, session="invalid")
        for i, data in enumerate(examples):
            at = t + i * 3
            # Rebase fresh readings for every case so only each corruption
            # drives the expected result; missing battery remains halt too.
            reading = bundle(at=at, seq=10 + i)
            if i == 0:
                reading = data
            elif i == 1:
                reading = replace(reading, depth=None, errors=data.errors)
            elif i == 2:
                reading = replace(reading, health=replace(reading.health, healthy=False))
            elif i == 3:
                reading = replace(reading, state=replace(reading.state, fallen=True))
            elif i == 4:
                reading = replace(reading, state=replace(reading.state, limp=True))
            elif i == 5:
                reading = replace(reading, state=replace(reading.state,
                                                         achieved_hz=39.))
            elif i == 6:
                reading = replace(reading, depth=replace(reading.depth,
                                                         received_at=at - 9))
            elif i == 7:
                reading = replace(reading, depth=replace(reading.depth,
                                                         t_ns=3_000_000_000))
            elif i == 8:
                reading = replace(reading, health=replace(reading.health,
                                                          battery_pct=None))
            cycle = runner.step(reading, now=at)
            self.assertEqual("halt", cycle.plan.intention)
            if i < 8:
                self.assertEqual("invalid_or_missing", cycle.quality)
            else:
                self.assertEqual("coherent", cycle.quality)
        self.assertEqual(9, len(runner.history()))

    def test_low_battery_rest_only_with_coherent_fresh_telemetry(self):
        runner = PassiveSimCycleRunner(self.memory, session="battery")
        a = runner.step(bundle(battery=12., seq=1), now=100.)
        self.assertEqual(("coherent", "rest"), (a.quality, a.plan.intention))
        b = runner.step(
            replace(bundle(at=101., seq=2, battery=12.),
                    errors=("robotd telemetry unavailable",)),
            now=101.,
        )
        self.assertEqual(("invalid_or_missing", "halt"),
                         (b.quality, b.plan.intention))
        self.assertIsNone(b.battery_pct)
        self.assertIsNone(runner.history()[-1]["battery_pct"])

    def test_duplicate_sequences_and_timestamps_fail_closed(self):
        runner = PassiveSimCycleRunner(self.memory, session="order")
        runner.step(bundle(seq=10), now=100.)
        self.assertEqual(
            "nonadvancing_frame",
            runner.step(bundle(at=101., seq=10), now=101.).quality,
        )
        self.assertEqual(
            "nonadvancing_frame",
            runner.step(
                replace(bundle(at=102., seq=11),
                        state=replace(bundle(at=102., seq=11).state,
                                      t_ns=10_000_000)), now=102.,
            ).quality,
        )
        self.assertEqual(
            "nonadvancing_frame",
            runner.step(
                replace(bundle(at=103., seq=11),
                        depth=replace(bundle(at=103., seq=11).depth,
                                      t_ns=10_010_000)), now=103.,
            ).quality,
        )
        self.assertEqual(
            "coherent",
            runner.step(bundle(at=104., seq=12), now=104.).quality,
        )
        self.assertEqual(["halt"] * 5,
                         [v["intention"] for v in runner.history()])

    def test_invalid_types_times_and_sessions_rejected(self):
        for session in ("", "outside directory", "../hello", "é", "x" * 65):
            with self.subTest(session=session):
                with self.assertRaises(ValueError):
                    PassiveSimCycleRunner(self.memory, session=session)
        runner = PassiveSimCycleRunner(self.memory, session="valid")
        for now in (-1., float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                runner.step(bundle(), now=now)
        with self.assertRaises(TypeError):
            runner.step("not telemetry", now=100.)
        runner.step(bundle(), now=100.)
        with self.assertRaises(ValueError):
            runner.step(bundle(), now=100.)
        with self.assertRaises(ValueError):
            runner.step(bundle(at=101., seq=11), now=101., max_age_s=20.)
        self.assertEqual(1, len(runner.history()))

    def test_session_scoping_handles_simulator_reset_without_reusing_old_frames(self):
        first = PassiveSimCycleRunner(self.memory, session="first")
        first.step(bundle(seq=120), now=100.)
        second = PassiveSimCycleRunner(self.memory, session="second")
        new = second.step(bundle(at=101., seq=1), now=101.)
        self.assertEqual("coherent", new.quality)
        self.assertEqual([1, 1], [r["sequence"] for r in second.history()])


class FakeReadOnlyDaemon:
    def __init__(self, path: Path, *, role: str, sessions: int, seen: list):
        self.error = None
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(4.)
        self.socket.bind(str(path))
        self.socket.listen(2)

        def send(conn, frame):
            conn.sendall((json.dumps(frame) + "\n").encode())

        def handle(conn, index):
            with conn.makefile("rb") as reader:
                def incoming():
                    return json.loads(reader.readline())
                seq = 10 + index
                stamp = seq * 1_000_000
                if role == "robot":
                    msg = incoming()
                    seen.append(msg["method"])
                    send(conn, {"jsonrpc": "2.0", "id": msg["id"], "result": {
                        "healthy": True, "battery": {"percent": 81.},
                        "control_loop": {"target_hz": 50.,
                                         "achieved_hz": 49.8, "missed": 0},
                    }})
                    msg = incoming()
                    seen.append(msg["method"])
                    send(conn, {"jsonrpc": "2.0", "id": msg["id"],
                                "result": {"accepted": True}})
                    send(conn, {"jsonrpc": "2.0", "method": "robot.state",
                                "params": {"safety": {"fallen": False,
                                                      "limp": False},
                                           "loop": {"hz": 49.8, "missed": 0},
                                           "t_ns": stamp}})
                else:
                    msg = incoming()
                    seen.append(msg["method"])
                    send(conn, {"jsonrpc": "2.0", "id": msg["id"],
                                "result": {"accepted": True, "sensor": "simulated-tof"}})
                    send(conn, {"jsonrpc": "2.0", "method": "tof.frame",
                                "params": {"seq": seq, "rows": 8, "cols": 8,
                                           "distance_mm": [1200] * 64,
                                           "status": [5] * 64,
                                           "t_ns": stamp}})

        def run():
            try:
                for index in range(sessions):
                    conn, _ = self.socket.accept()
                    with conn:
                        conn.settimeout(2.)
                        handle(conn, index)
            except Exception as exc:
                self.error = exc
            finally:
                self.socket.close()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def join(self):
        self.thread.join(timeout=5.)
        if self.thread.is_alive():
            raise AssertionError("simulated daemon thread did not stop")
        if self.error:
            raise self.error


class PassiveCycleUnixTests(unittest.TestCase):
    def test_multiple_sessions_use_whitelisted_real_unix_rpc_and_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            seen: list[str] = []
            robot = FakeReadOnlyDaemon(
                root / "duck-a.sock", role="robot", sessions=5, seen=seen)
            tof = FakeReadOnlyDaemon(
                root / "duck-a-tof.sock", role="tof", sessions=5, seen=seen)
            try:
                db = root / "memory.sqlite3"
                first = run_session(root, db, session="a", cycles=3,
                                    interval_s=0., timeout_s=1.)
                second = run_session(root, db, session="b", cycles=2,
                                     interval_s=0., timeout_s=1.)
                self.assertEqual((3, 3), (first["coherent_cycles"],
                                          first["journal_count"]))
                self.assertEqual((2, 5), (second["coherent_cycles"],
                                          second["journal_count"]))
                self.assertEqual(["halt"] * 3,
                                 [x["intention"] for x in first["cycles"]])
                self.assertEqual(0, second["motor_commands_issued"])
                self.assertEqual(0, second["verified_consequences"])
                self.assertEqual({"robot.health", "robot.subscribe", "tof.stream"},
                                 set(seen))
                self.assertEqual(
                    {"robot.health": 5, "robot.subscribe": 5, "tof.stream": 5},
                    {method: seen.count(method) for method in set(seen)},
                )
                db_check = ExperienceMemory(db)
                try:
                    rows = db_check.conn.execute(
                        "SELECT source,outcome,reward,motor_commands "
                        "FROM sim_passive_cycles"
                    ).fetchall()
                    self.assertEqual(5, len(rows))
                    self.assertTrue(all(
                        x["source"] == "simulator_ipc"
                        and x["outcome"] == "no_action_executed"
                        and x["reward"] is None
                        and x["motor_commands"] == 0 for x in rows
                    ))
                finally:
                    db_check.close()
            finally:
                robot.join()
                tof.join()

    def test_failed_socket_is_journaled_as_halt_without_motor_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = root / "memory.sqlite3"
            with patch(
                "microduck_companion.sim_passive_cycles.read_simulator_telemetry",
                return_value=SimulatorTelemetry(errors=("disconnected",))
            ):
                output = run_session(root, db, session="disconnected",
                                     cycles=2, interval_s=0., timeout_s=.05)
            self.assertEqual(0, output["coherent_cycles"])
            self.assertEqual(["invalid_or_missing"] * 2,
                             [r["quality"] for r in output["cycles"]])
            self.assertEqual(["halt"] * 2,
                             [r["intention"] for r in output["cycles"]])
            self.assertEqual(0, output["motor_commands_issued"])

    def test_invalid_cycle_limits_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for n in (0, 1, 21, True):
                with self.assertRaises(ValueError):
                    run_session(root, root / "db", session="bad", cycles=n)
            with self.assertRaises(ValueError):
                run_session(root, root / "db", session="bad",
                            interval_s=float("nan"))


if __name__ == "__main__":
    unittest.main()
