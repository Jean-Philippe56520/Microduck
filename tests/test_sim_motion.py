"""Fake motor socket tests; only one short impulse is allowed in MuJoCo."""
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from microduck_companion.sim_bridge import SimulatorTelemetry
from microduck_companion.sim_flat_zone import FlatGroundTruth, GroundTruthError
from microduck_companion.sim_ipc import HealthReading, StateReading, DepthReading
from microduck_companion.sim_motion import (
    MIN_CLEARANCE_M, SPEED_MPS, TICKS, SimMotionError, move_once,
)


def ground(sim_time=1., *, clearance=.71, safe=True):
    return FlatGroundTruth(
        observed_at=time.monotonic(), sim_time_s=sim_time,
        x_m=.02, y_m=.01, z_m=.116, gravity_z=-1.,
        boundary_clearance_m=clearance, safe_area=safe, floor_clear=safe,
    )


def telemetry(*, battery=50, healthy=True):
    now = time.monotonic()
    return SimulatorTelemetry(
        health=HealthReading(healthy, battery, 50., 50., 0, now),
        state=StateReading(False, False, 50., 0, 100, now),
        depth=DepthReading(1, (0,)*64, (255,)*64, 100, now),
    )


def health(*, healthy=True, battery=50, hz=50):
    return HealthReading(healthy, battery, 50., hz, 0, time.monotonic())


class FakeMotorDaemon:
    def __init__(self, root, *, acknowledge=True):
        self.path = Path(root) / "duck-a.sock"
        self.received = []
        self.error = None
        self.acknowledge = acknowledge
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(2.)
        self.sock.bind(str(self.path))
        self.sock.listen(1)

        def worker():
            try:
                with self.sock.accept()[0] as conn:
                    conn.settimeout(1.)
                    with conn.makefile("rb") as reader:
                        for raw in reader:
                            frame = json.loads(raw)
                            self.received.append(frame)
                            if frame["method"] == "robot.stop":
                                response = (
                                    {"jsonrpc": "2.0", "id": 1,
                                     "result": {"stopped": True}}
                                    if self.acknowledge
                                    else {"jsonrpc": "2.0", "id": 999,
                                          "result": {"stopped": True}}
                                )
                                conn.sendall((json.dumps(response) + "\n").encode())
                                break
            except Exception as exc:
                self.error = exc
            finally:
                self.sock.close()
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def join(self):
        self.thread.join(3.)
        if self.thread.is_alive():
            raise AssertionError("fake motor daemon did not finish")
        if self.error is not None:
            raise self.error


class SimMotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def server(self, **kwargs):
        fake = FakeMotorDaemon(self.path, **kwargs)
        self.addCleanup(fake.join)
        return fake

    def run_mock(self, poses=None, *, fake=None, readings=None, tel=None):
        if poses is None:
            poses = [ground(sim_time=1 + i * .1) for i in range(TICKS + 2)]
        if readings is None:
            readings = [health() for _ in range(TICKS)]
        with (patch("microduck_companion.sim_motion.read_simulator_telemetry",
                    return_value=telemetry() if tel is None else tel),
              patch("microduck_companion.sim_motion.read_verified_flat_ground",
                    side_effect=iter(poses)),
              patch("microduck_companion.sim_motion.read_health",
                    side_effect=iter(readings)),
              patch("microduck_companion.sim_motion.time.sleep")):
            return move_once(self.path, "/fake/rl")

    def test_fixed_velocity_and_stop_acknowledged(self):
        fake = self.server()
        result = self.run_mock()
        self.assertEqual(TICKS, result.commands_sent)
        self.assertTrue(result.stop_confirmed)
        self.assertGreaterEqual(result.measured_displacement_m, 0.)
        self.assertEqual(TICKS+1, len(fake.received))
        for req in fake.received[:TICKS]:
            self.assertEqual("robot.move", req["method"])
            self.assertNotIn("id", req)
            self.assertEqual({"vx": SPEED_MPS, "vy": 0., "vyaw": 0.},
                             req["params"])
        self.assertEqual("robot.stop", fake.received[-1]["method"])
        self.assertEqual(1, fake.received[-1]["id"])

    def test_no_clearance_no_motor_message(self):
        for g in (ground(clearance=.2), ground(safe=False)):
            with self.subTest(g=g):
                with self.assertRaises(SimMotionError):
                    self.run_mock(poses=[g])

    def test_no_battery_or_low_battery_refuses(self):
        for battery in (None, 10, 25):
            with self.subTest(battery=battery), self.assertRaises(SimMotionError):
                self.run_mock(tel=telemetry(battery=battery), poses=[ground()])

    def test_missing_or_unhealthy_telemetry_refuses(self):
        for tel in (SimulatorTelemetry(), telemetry(healthy=False)):
            with self.subTest(tel=tel), self.assertRaises(SimMotionError):
                self.run_mock(tel=tel, poses=[ground()])

    def test_unknown_world_refused_before_connect(self):
        with patch("microduck_companion.sim_motion.read_simulator_telemetry",
                   return_value=telemetry()), patch(
                       "microduck_companion.sim_motion.read_verified_flat_ground",
                       side_effect=GroundTruthError("wrong scene")
                   ):
            with self.assertRaises(SimMotionError):
                move_once(self.path, "/fake/rl")

    def test_health_failure_after_first_move_stops(self):
        fake = self.server()
        with self.assertRaises(SimMotionError):
            self.run_mock(readings=[health(), health(healthy=False)])
        self.assertEqual(["robot.move", "robot.stop"],
                         [req["method"] for req in fake.received])

    def test_zone_change_after_first_move_stops(self):
        fake = self.server()
        poses = [ground(1.), ground(1.01), ground(1.10, safe=False)]
        with self.assertRaises(SimMotionError):
            self.run_mock(poses=poses)
        self.assertEqual(["robot.move", "robot.stop"],
                         [req["method"] for req in fake.received])

    def test_stationary_sim_time_after_first_move_stops(self):
        fake = self.server()
        poses = [ground(1.), ground(1.02), ground(1.02)]
        with self.assertRaisesRegex(SimMotionError, "stalled"):
            self.run_mock(poses=poses)
        self.assertEqual(["robot.move", "robot.stop"],
                         [req["method"] for req in fake.received])

    def test_bad_stop_acknowledgment_fails(self):
        fake = self.server(acknowledge=False)
        with self.assertRaisesRegex(SimMotionError, "stop could not be confirmed"):
            self.run_mock()
        self.assertEqual("robot.stop", fake.received[-1]["method"])

    def test_missing_robot_socket_fails_after_safety_check(self):
        with self.assertRaisesRegex(SimMotionError, "socket unavailable"):
            self.run_mock()

    def test_degraded_achieved_hz_stops(self):
        fake = self.server()
        with self.assertRaises(SimMotionError):
            self.run_mock(readings=[health(), health(hz=38)])
        self.assertEqual("robot.stop", fake.received[-1]["method"])

    def test_tight_margin_stops(self):
        fake = self.server()
        poses = [ground(1.), ground(1.03), ground(1.15, clearance=MIN_CLEARANCE_M-.001)]
        with self.assertRaises(SimMotionError):
            self.run_mock(poses=poses)
        self.assertEqual("robot.stop", fake.received[-1]["method"])


if __name__ == "__main__":
    unittest.main()
