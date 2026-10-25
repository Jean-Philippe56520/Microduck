"""Fail-closed simulation-only flat-floor proof; no physical motor commands."""
import math
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from microduck_companion import AutonomyBrain, ExperienceMemory
from microduck_companion.sim_ipc import DepthReading, HealthReading, StateReading
from microduck_companion.sim_bridge import SimulatorTelemetry
from microduck_companion.sim_flat_zone import (
    FlatGroundTruth, GroundTruthError, MAX_GROUND_AGE_S,
    RL_COMMIT, ZONE_RADIUS_M, _read_body, flat_zone_snapshot, parse_flat_frame,
    read_verified_flat_ground, verify_body_process, verify_flat_scene,
)


def frame(*, x=0., y=0., z=.116, gravity=None, sim_time=15.):
    return {"trunk": [x, y, z], "sim_time": sim_time,
            "imu": {"gravity": gravity if gravity is not None else [0., 0., -1.]}}


def telemetry(*, at=100., battery=50., healthy=True, fallen=False, rate=50.):
    return SimulatorTelemetry(
        health=HealthReading(healthy, battery, 50., rate, 0, at),
        state=StateReading(fallen, False, rate, 0, 12345, at),
        depth=DepthReading(5, (0,) * 64, (255,) * 64, 12345, at),
    )


class FlatGroundTruthTests(unittest.TestCase):
    def test_pinned_flat_world_and_center_pose_certify_small_zone(self):
        ground = parse_flat_frame(frame(), 100.1)
        self.assertTrue(ground.safe_area)
        self.assertTrue(ground.floor_clear)
        self.assertAlmostEqual(ZONE_RADIUS_M - .16, ground.boundary_clearance_m)

    def test_verified_flat_pose_makes_explore_possible_without_qwen(self):
        truth = parse_flat_frame(frame(), 100.1)
        snap = flat_zone_snapshot(telemetry(), truth, now=100.2)
        self.assertEqual({"battery_pct", "safe_area", "floor_clear", "obstacle_m"},
                         {e.kind for e in snap.events})
        self.assertEqual("simulator", snap.environment)
        mem = ExperienceMemory()
        try:
            intent = AutonomyBrain(mem).choose_from_snapshot(snap, now=100.2).intention
        finally:
            mem.close()
        self.assertEqual("explore", intent)

    def test_region_near_boundary_fails_closed(self):
        for x in (.41, .75, 4., -4.):
            with self.subTest(x=x):
                ground = parse_flat_frame(frame(x=x), 100.)
                self.assertFalse(ground.safe_area)
                mem = ExperienceMemory()
                try:
                    snap = flat_zone_snapshot(telemetry(), ground, now=100.1)
                    self.assertEqual("halt",
                        AutonomyBrain(mem).choose_from_snapshot(snap, now=100.1).intention)
                finally:
                    mem.close()

    def test_flat_ground_but_fallen_pose_halts(self):
        for pose in (frame(z=.07), frame(z=.28), frame(gravity=[.8, 0, -.6])):
            with self.subTest(pose=pose):
                truth = parse_flat_frame(pose, 100.)
                self.assertFalse(truth.floor_clear)
                self.assertFalse(truth.safe_area)

    def test_invalid_frame_never_certifies(self):
        bad = [
            {}, {"trunk": [0., 0., .116], "sim_time": 10.},
            frame(x=float("nan")), frame(z=float("inf")),
            frame(sim_time=-1), frame(gravity=[0., -1.]),
            frame(gravity=[0., 0., float("nan")]),
            dict(frame(), trunk=[0., 0.]), frame(x=True),
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(GroundTruthError):
                parse_flat_frame(value, 100.)

    def test_no_ground_proof_keeps_previous_halt(self):
        snap = flat_zone_snapshot(telemetry(), None, now=100.1)
        self.assertEqual(["battery_pct"], [e.kind for e in snap.events])

    def test_expired_or_future_ground_proof_is_ignored(self):
        proof = parse_flat_frame(frame(), 100.)
        for now in (99., 100. + MAX_GROUND_AGE_S + .05):
            with self.subTest(now=now):
                snap = flat_zone_snapshot(telemetry(), proof, now=now)
                self.assertFalse(any(e.kind == "floor_clear" for e in snap.events))

    def test_unhealthy_or_incomplete_telemetry_does_not_authorize(self):
        proof = parse_flat_frame(frame(), 100.)
        for source in (
            SimulatorTelemetry(), telemetry(healthy=False),
            SimulatorTelemetry(health=telemetry().health),
            telemetry(fallen=True), telemetry(rate=35.),
            telemetry(at=95.),
        ):
            with self.subTest(source=source):
                snap = flat_zone_snapshot(source, proof, now=100.1)
                self.assertFalse(any(e.kind == "floor_clear" for e in snap.events))

    def test_no_battery_attestation_is_not_authorization(self):
        snap = flat_zone_snapshot(telemetry(battery=None),
                                  parse_flat_frame(frame(), 100.), now=100.1)
        self.assertFalse(any(e.kind == "floor_clear" for e in snap.events))

    def test_low_battery_rest_even_in_safe_zone(self):
        snap = flat_zone_snapshot(telemetry(battery=9.),
                                  parse_flat_frame(frame(), 100.), now=100.1)
        mem = ExperienceMemory()
        try:
            self.assertEqual("rest",
                AutonomyBrain(mem).choose_from_snapshot(snap, now=100.1).intention)
        finally:
            mem.close()

    def test_ground_truth_source_does_not_authenticate_real_robot(self):
        snap = flat_zone_snapshot(telemetry(),
                                  parse_flat_frame(frame(), 100.), now=100.1)
        from microduck_companion.perception import PerceptionSnapshot
        disguised = PerceptionSnapshot("robot", snap.events, 100.1)
        self.assertFalse(disguised.to_scene(now=100.1).floor_clear)

    def test_read_verified_requires_pinned_scene_and_process_twice(self):
        with (patch("microduck_companion.sim_flat_zone.verify_flat_scene") as verify,
              patch("microduck_companion.sim_flat_zone.verify_body_process") as proc,
              patch("microduck_companion.sim_flat_zone._read_body", return_value=frame())):
            got = read_verified_flat_ground("/tmp/test", "/tmp/rl", port=17801)
        verify.assert_called_once()
        self.assertEqual(2, proc.call_count)
        self.assertTrue(got.safe_area)

    def test_not_verified_means_no_ground_truth(self):
        with patch("microduck_companion.sim_flat_zone.verify_flat_scene",
                   side_effect=GroundTruthError("dirty")):
            with self.assertRaises(GroundTruthError):
                read_verified_flat_ground("/tmp/test", "/tmp/rl")

    def test_unknown_or_modified_checkout_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            with patch("microduck_companion.sim_flat_zone._git",
                       return_value="wrong"):
                with self.assertRaisesRegex(GroundTruthError, "revision"):
                    verify_flat_scene(p)
            with patch("microduck_companion.sim_flat_zone._git",
                       side_effect=[RL_COMMIT, " M src/modified"]):
                with self.assertRaisesRegex(GroundTruthError, "modified"):
                    verify_flat_scene(p)
            with patch("microduck_companion.sim_flat_zone._git",
                       side_effect=[RL_COMMIT, ""]):
                with self.assertRaises(GroundTruthError):
                    verify_flat_scene(p)

    def test_wrong_scene_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            scene = p / "src/mjlab_microduck/robot/microduck/scene.xml"
            scene.parent.mkdir(parents=True)
            scene.write_text("<mujoco><worldbody><geom type='plane'/></worldbody></mujoco>")
            with patch("microduck_companion.sim_flat_zone._git",
                       side_effect=[RL_COMMIT, ""]):
                with self.assertRaisesRegex(GroundTruthError, "not the pinned"):
                    verify_flat_scene(p)

    def test_pidfile_missing_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(GroundTruthError):
                verify_body_process(Path(tmp), Path(tmp), 17801)

    def test_foreign_program_or_dead_pid_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state / "body.pid").write_text(str(os.getpid()))
            with self.assertRaises(GroundTruthError):
                verify_body_process(state, state, 17801)
            (state / "body.pid").write_text("not-a-pid")
            with self.assertRaises(GroundTruthError):
                verify_body_process(state, state, 17801)

    def test_invalid_port_and_timeouts_rejected(self):
        for port in (0, 80, True, 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                read_verified_flat_ground("/tmp", "/tmp", port=port)
        for timeout in (-1., 0., float("nan"), 4.):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                read_verified_flat_ground("/tmp", "/tmp", timeout_s=timeout)


class FakeBodyProtocolTests(unittest.TestCase):
    def setUp(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        self.port = server.getsockname()[1]
        self.server = server

    def serve(self, *, hello='{"protocol":1}', body=None):
        responses = []
        def worker():
            try:
                with self.server.accept()[0] as conn:
                    conn.settimeout(1.)
                    stream = conn.makefile("rwb", buffering=0)
                    a = stream.readline()
                    responses.append(a)
                    stream.write((hello + "\n").encode())
                    if body is not None:
                        b = stream.readline()
                        responses.append(b)
                        stream.write((body + "\n").encode())
                    stream.close()
            finally:
                self.server.close()
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.addCleanup(t.join, 2.)
        return responses

    def test_reads_only_hello_and_pose(self):
        received = self.serve(body='{"trunk":[0,0,0.116],"sim_time":15,"imu":{"gravity":[0,0,-1]}}')
        data = _read_body(self.port, 0.5)
        self.assertEqual(2, len(received))
        self.assertIn(b'"op":"hello"', received[0])
        self.assertIn(b'"op":"read"', received[1])
        self.assertNotIn(b'"op":"write"', b"".join(received))
        self.assertEqual([0, 0, .116], data["trunk"])

    def test_wrong_protocol_rejected(self):
        self.serve(hello='{"protocol":9}')
        with self.assertRaises(GroundTruthError):
            _read_body(self.port, .5)

    def test_simulator_error_is_rejected(self):
        self.serve(hello='{"error":"not ready"}')
        with self.assertRaises(GroundTruthError):
            _read_body(self.port, .5)

    def test_nonfinite_json_rejected(self):
        self.serve(hello='{"protocol":NaN}')
        with self.assertRaises(GroundTruthError):
            _read_body(self.port, .5)


if __name__ == "__main__":
    unittest.main()
