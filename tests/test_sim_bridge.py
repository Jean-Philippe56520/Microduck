"""The bridge is tested on invented frames and fake sockets, never on MuJoCo."""
import contextlib
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from microduck_companion import AutonomyBrain, ExperienceMemory
from microduck_companion.sim_bridge import (
    SimulatorTelemetry, read_simulator_telemetry,
)
from microduck_companion.sim_ipc import DepthReading, HealthReading, StateReading
from microduck_companion.sim_observer import main, observe_once


def bundle(*, battery=80., healthy=True, fallen=False, limp=False,
           control=49.9, stamp=100., depth_stamp=None, state_ns=12_000,
           depth_ns=12_500, errors=()):
    return SimulatorTelemetry(
        health=HealthReading(healthy, battery, 50., control, 0, stamp),
        state=StateReading(fallen, limp, control, 0, state_ns, stamp),
        depth=DepthReading(1, (1300,) * 64, (5,) * 64, depth_ns,
                           stamp if depth_stamp is None else depth_stamp),
        errors=tuple(errors),
    )


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.brain = AutonomyBrain(self.memory)
        self.addCleanup(self.memory.close)

    def choose(self, telemetry, now=100.2):
        return self.brain.choose_from_snapshot(
            telemetry.to_snapshot(now=now), now=now,
        ).intention

    def test_good_sensor_readings_still_cannot_certify_safe_floor(self):
        snap = bundle().to_snapshot(now=100.2)
        self.assertEqual("simulator", snap.environment)
        self.assertEqual(["battery_pct"], [e.kind for e in snap.events])
        self.assertEqual("robotd", snap.events[0].source)
        self.assertEqual("halt", self.choose(bundle()))
        self.assertFalse(snap.to_scene(now=100.2).safe_area)
        self.assertFalse(snap.to_scene(now=100.2).floor_clear)
        self.assertFalse(snap.to_scene(now=100.2).perception_valid)

    def test_low_battery_selects_rest_without_exploration(self):
        self.assertEqual("rest", self.choose(bundle(battery=12.)))

    def test_unknown_battery_remains_unknown(self):
        self.assertEqual((), bundle(battery=None).to_snapshot(now=100.2).events)
        self.assertEqual("halt", self.choose(bundle(battery=None)))

    def test_incomplete_or_failed_telemetry_halts(self):
        cases = [
            SimulatorTelemetry(),
            SimulatorTelemetry(health=bundle().health),
            SimulatorTelemetry(health=bundle().health, state=bundle().state),
            bundle(errors=("tofd offline",)),
        ]
        for reading in cases:
            with self.subTest(reading=reading):
                self.assertEqual("halt", self.choose(reading))
                self.assertEqual((), reading.to_snapshot(now=100.2).events)

    def test_fall_limp_and_unhealthy_are_conservative(self):
        for test in (bundle(fallen=True), bundle(limp=True), bundle(healthy=False)):
            with self.subTest(test=test):
                self.assertEqual("halt", self.choose(test))
                self.assertEqual((), test.to_snapshot(now=100.2).events)

    def test_slow_control_loop_never_authorizes_even_low_battery_rest(self):
        slow = bundle(control=40., battery=12.)
        self.assertEqual("halt", self.choose(slow))

    def test_stale_or_future_samples_halt(self):
        for now in (99., 105.):
            with self.subTest(now=now):
                self.assertEqual("halt", self.choose(bundle(), now=now))
        self.assertEqual("halt", self.choose(bundle(depth_stamp=95.)))

    def test_mismatched_daemon_clocks_halt(self):
        self.assertEqual("halt", self.choose(bundle(depth_ns=2_000_000_000)))

    def test_legacy_unknown_clock_still_cannot_certify_floor(self):
        telemetry = bundle(state_ns=None, depth_ns=None)
        self.assertEqual("halt", self.choose(telemetry))

    def test_invalid_max_age_and_now_rejected(self):
        for max_age in (0., -1., float("nan"), float("inf"), 8.):
            with self.subTest(max_age=max_age):
                with self.assertRaises(ValueError):
                    bundle().to_snapshot(now=100., max_age_s=max_age)
        with self.assertRaises(ValueError):
            bundle().to_snapshot(now=-2.)


class FakeDaemon:
    def __init__(self, path, serve):
        self.error = None
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.settimeout(2.)
        self.listener.bind(str(path))
        self.listener.listen(1)

        def runner():
            try:
                conn, _ = self.listener.accept()
                with conn:
                    conn.settimeout(1.)
                    with conn.makefile("rb") as reader:
                        serve(conn, reader)
            except Exception as exc:
                self.error = exc
            finally:
                self.listener.close()

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()

    def join(self):
        self.thread.join(timeout=2.)
        if self.thread.is_alive():
            raise AssertionError("fake daemon did not stop")
        if self.error:
            raise self.error


def send(sock, data):
    sock.sendall((json.dumps(data) + "\n").encode())


def request(reader):
    return json.loads(reader.readline())


class UnixIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)

    def start(self, *, healthy=True, sensor="simulated"):
        seen = []

        def robot(sock, reader):
            req = request(reader)
            seen.append(req["method"])
            send(sock, {"jsonrpc": "2.0", "id": req["id"], "result": {
                "healthy": healthy, "battery": {"percent": 81.},
                "control_loop": {"target_hz": 50., "achieved_hz": 49.8,
                                 "missed": 0},
            }})
            req = request(reader)
            seen.append(req["method"])
            send(sock, {"jsonrpc": "2.0", "id": req["id"],
                        "result": {"accepted": True}})
            send(sock, {"jsonrpc": "2.0", "method": "robot.state", "params": {
                "safety": {"fallen": False, "limp": False},
                "loop": {"hz": 49.8, "missed": 0}, "t_ns": 999999999,
            }})

        def tof(sock, reader):
            req = request(reader)
            seen.append(req["method"])
            send(sock, {"jsonrpc": "2.0", "id": req["id"],
                        "result": {"accepted": True, "sensor": sensor}})
            if sensor:
                send(sock, {"jsonrpc": "2.0", "method": "tof.frame", "params": {
                    "seq": 13, "rows": 8, "cols": 8,
                    "distance_mm": [1800] * 64,
                    "status": [5] * 64, "t_ns": 999999999,
                }})

        robot_daemon = FakeDaemon(self.root / "duck-a.sock", robot)
        tof_daemon = FakeDaemon(self.root / "duck-a-tof.sock", tof)
        self.addCleanup(tof_daemon.join)
        self.addCleanup(robot_daemon.join)
        return seen

    def test_acquire_official_method_names_only_and_choose_halt(self):
        seen = self.start()
        telemetry = read_simulator_telemetry(self.root)
        self.assertEqual([], list(telemetry.errors))
        self.assertIsNotNone(telemetry.depth)
        self.assertEqual({"robot.health", "robot.subscribe", "tof.stream"}, set(seen))
        snap = telemetry.to_snapshot()
        self.assertEqual("simulator", snap.environment)
        memory = ExperienceMemory()
        try:
            self.assertEqual("halt", AutonomyBrain(memory).choose_from_snapshot(snap).intention)
        finally:
            memory.close()

    def test_unavailable_tof_terminates_as_halt(self):
        self.start(sensor=None)
        telemetry = read_simulator_telemetry(self.root)
        self.assertIn("tofd telemetry unavailable", telemetry.errors)
        self.assertEqual((), telemetry.to_snapshot().events)

    def test_missing_all_sockets_fails_closed(self):
        telemetry = read_simulator_telemetry(self.root, timeout_s=.05)
        self.assertEqual(2, len(telemetry.errors))
        self.assertEqual((), telemetry.to_snapshot().events)

    def test_observer_is_read_only_and_returns_halt(self):
        seen = self.start()
        result = observe_once(self.root)
        self.assertEqual("halt", result["intention"])
        self.assertFalse(result["floor_certified"])
        self.assertFalse(result["movement_rpc_enabled"])
        self.assertEqual(3, len(seen))

    def test_observer_cli_reports_unhealthy_robot(self):
        self.start(healthy=False)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = main(["--state-dir", str(self.root)])
        self.assertEqual(1, result)
        parsed = json.loads(stdout.getvalue())
        self.assertIs(parsed["robot_healthy"], False)
        self.assertEqual("halt", parsed["intention"])

    def test_observer_cli_reports_missing_daemons(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = main(["--state-dir", str(self.root), "--timeout", "0.05"])
        self.assertEqual(1, result)
        parsed = json.loads(stdout.getvalue())
        self.assertEqual("halt", parsed["intention"])
        self.assertTrue(parsed["errors"])


if __name__ == "__main__":
    unittest.main()
