"""Observed simulator motion memory and fixed bounded gait trial tests.

Fake sockets/poses are not an alternative to the official MuJoCo integration
workflow. In particular, no test here proves actual stepping or locomotion.
"""
import contextlib
import io
import json
import math
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from microduck_companion import AutonomyBrain, ExperienceMemory, Scene
from microduck_companion.sim_bridge import SimulatorTelemetry
from microduck_companion.sim_flat_zone import FlatGroundTruth, GroundTruthError
from microduck_companion.sim_ipc import DepthReading, HealthReading, StateReading, Notification, TelemetryError
from microduck_companion.sim_motion import SimMotionError
from microduck_companion.sim_walk_demo import main
from microduck_companion.sim_walk_trial import (
    BASELINE_LIMIT_M, WALK_SPEED_MPS, WALK_TICKS, run_walk_trial,
)


def ground(t=1.0, x=0.02, *, clearance=0.71, safe=True):
    return FlatGroundTruth(
        observed_at=time.monotonic(), sim_time_s=t,
        x_m=x, y_m=0.01, z_m=0.116, gravity_z=-1.0,
        boundary_clearance_m=clearance, safe_area=safe, floor_clear=safe,
    )


def telemetry(*, battery=55., healthy=True):
    now = time.monotonic()
    return SimulatorTelemetry(
        health=HealthReading(healthy, battery, 50., 50., 0, now),
        state=StateReading(False, False, 50., 0, 10000, now),
        depth=DepthReading(1, (800,) * 64, (5,) * 64, 10000, now),
    )


def health(*, battery=55., healthy=True, hz=50.):
    return HealthReading(healthy, battery, 50., hz, 0, time.monotonic())


def safe_scene(environment="simulator"):
    return Scene(
        environment=environment, safe_area=True, floor_clear=True,
        obstacle_m=0.7, battery_pct=80.,
    )


class MotionMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "trial.sqlite"

    def test_verified_translation_is_persistent_and_source_labeled(self):
        memory = ExperienceMemory(self.path)
        before = memory.intent_preference("simulator", "explore")
        self.assertEqual(0., before)
        result = memory.record_simulated_motion(
            measured_m=0.035, baseline_m=.0003,
            simulated_duration_s=1.2,
            stop_confirmed=True, healthy_after=True, safe_after=True,
        )
        self.assertEqual("translation_observed", result.outcome)
        self.assertEqual("mujoco_verified_pose", result.source)
        self.assertEqual(.5, result.reward)
        self.assertAlmostEqual(.075, result.updated_preference)
        self.assertEqual(1, result.observed_trials)
        memory.close()
        restored = ExperienceMemory(self.path)
        self.addCleanup(restored.close)
        self.assertEqual(1, len(restored.simulated_motion_history()))
        self.assertAlmostEqual(.075, restored.intent_preference("simulator", "explore"))
        self.assertEqual(0., restored.intent_preference("robot", "explore"))

    def test_no_progress_reduces_preference_gradually(self):
        memory = ExperienceMemory(self.path)
        self.addCleanup(memory.close)
        one = memory.record_simulated_motion(
            measured_m=.0002, baseline_m=.0001, simulated_duration_s=1.,
            stop_confirmed=True, healthy_after=True, safe_after=True,
        )
        self.assertEqual("no_progress_observed", one.outcome)
        self.assertEqual(-.5, one.reward)
        self.assertAlmostEqual(-.075, one.updated_preference)
        for _ in range(7):
            memory.record_simulated_motion(
                measured_m=.0002, baseline_m=.0001, simulated_duration_s=1.,
                stop_confirmed=True, healthy_after=True, safe_after=True,
            )
        brain = AutonomyBrain(memory)
        self.assertEqual("rest", brain.choose(safe_scene()).intention)
        self.assertEqual("explore", brain.choose(safe_scene("mock")).intention)

    def test_control_limiter_does_not_create_simulated_reward(self):
        memory = ExperienceMemory(self.path)
        self.addCleanup(memory.close)
        result = memory.record_simulated_motion(
            measured_m=.035, baseline_m=.0001, simulated_duration_s=1.2,
            stop_confirmed=True, healthy_after=True, safe_after=True,
            control_limited=True,
        )
        self.assertEqual("inconclusive_control_limit", result.outcome)
        self.assertIsNone(result.reward)
        self.assertEqual(0.0, result.updated_preference)
        self.assertEqual(1, result.observed_trials)

    def test_inconclusive_drift_preserves_preferences(self):
        memory = ExperienceMemory(self.path)
        self.addCleanup(memory.close)
        data = memory.record_simulated_motion(
            measured_m=.04, baseline_m=.006, simulated_duration_s=2.,
            stop_confirmed=True, healthy_after=True, safe_after=True,
        )
        self.assertEqual("inconclusive_drift", data.outcome)
        self.assertIsNone(data.reward)
        self.assertEqual(0, data.updated_preference)

    def test_unverified_stop_or_health_never_trains(self):
        memory = ExperienceMemory(self.path)
        self.addCleanup(memory.close)
        for checks in (
            (False, True, True), (True, False, True), (True, True, False)
        ):
            outcome = memory.record_simulated_motion(
                measured_m=.03, baseline_m=.0001, simulated_duration_s=1.,
                stop_confirmed=checks[0], healthy_after=checks[1],
                safe_after=checks[2],
            )
            self.assertEqual("unverified", outcome.outcome)
            self.assertIsNone(outcome.reward)
        self.assertEqual(0., memory.intent_preference("simulator", "explore"))
        self.assertEqual(3, len(memory.simulated_motion_history()))

    def test_reject_invalid_measurements_without_writing(self):
        memory = ExperienceMemory(self.path)
        self.addCleanup(memory.close)
        for v in (float("nan"), float("inf"), -1., True):
            with self.subTest(v=v), self.assertRaises(ValueError):
                memory.record_simulated_motion(
                    measured_m=v, baseline_m=0., simulated_duration_s=1.,
                    stop_confirmed=True, healthy_after=True, safe_after=True,
                )
        with self.assertRaises(ValueError):
            memory.record_simulated_motion(
                measured_m=.1, baseline_m=0., simulated_duration_s=0.,
                stop_confirmed=True, healthy_after=True, safe_after=True,
            )
        self.assertEqual([], memory.simulated_motion_history())

    def test_observed_memory_is_not_an_object_identity(self):
        mem = ExperienceMemory(self.path)
        self.addCleanup(mem.close)
        mem.record_simulated_motion(
            measured_m=.02, baseline_m=.0001, simulated_duration_s=1.,
            stop_confirmed=True, healthy_after=True, safe_after=True,
        )
        self.assertIsNone(mem.get("simulator"))
        self.assertEqual(0, mem.experience_count())


class FakeRobotd:
    def __init__(self, path: Path, *, valid_stop=True):
        self.requested = []
        self.error = None
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(2.0)
        self.sock.bind(str(path))
        self.sock.listen(1)
        def worker():
            try:
                with self.sock.accept()[0] as conn:
                    conn.settimeout(1.0)
                    with conn.makefile("rb") as reader:
                        for data in reader:
                            payload = json.loads(data)
                            self.requested.append(payload)
                            if payload.get("method") == "robot.stop":
                                answer = {
                                    "jsonrpc": "2.0",
                                    "id": 1 if valid_stop else 10,
                                    "result": {"accepted": True},
                                }
                                conn.sendall((json.dumps(answer)+"\n").encode())
                                break
            except Exception as exc:
                self.error = exc
            finally:
                self.sock.close()
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def join(self):
        self.thread.join(timeout=3.)
        if self.thread.is_alive():
            raise AssertionError("fake robotd did not stop")
        if self.error:
            raise self.error


class FakePolicyStream:
    """A separate read-only robot.state subscriber, not a motor controller."""

    def __init__(self, path, *, timeout_s=.45):
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def request(self, method, *, hz):
        if method != "robot.subscribe" or hz != 10:
            raise AssertionError("unexpected telemetry subscription")
        return {"accepted": True}

    def next_notification(self):
        self.calls += 1
        return Notification(
            "robot.state",
            {"policy": "walk", "move": {
                "requested": [.12, 0., 0.],
                "applied": [.09, 0., 0.],
                "limited_by": [],
            }},
            time.monotonic(),
        )


class WalkTrialFakeSocketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "private-memory.sqlite"

    def start(self, *, valid_stop=True):
        robot = FakeRobotd(self.root / "duck-a.sock", valid_stop=valid_stop)
        self.addCleanup(robot.join)
        return robot

    def invoke(self, *, poses=None, readings=None, sensor=None,
               on_policy_sample=None, policy_stream_cls=FakePolicyStream):
        if poses is None:
            poses = [ground(1 + i*.1, .02 + i*.001) for i in range(WALK_TICKS+4)]
        if readings is None:
            readings = [health() for _ in range(WALK_TICKS+1)]
        if sensor is None:
            sensor = telemetry()
        with (patch("microduck_companion.sim_walk_trial._read_ground",
                    side_effect=iter(poses)),
              patch("microduck_companion.sim_walk_trial.read_health",
                    side_effect=iter(readings)),
              patch("microduck_companion.sim_walk_trial.read_simulator_telemetry",
                    return_value=sensor),
              patch("microduck_companion.sim_walk_trial.ReadOnlyUnixRpc",
                    policy_stream_cls),
              patch("microduck_companion.sim_walk_trial.time.sleep")):
            return run_walk_trial(self.root, "/fake/rl", self.db,
                                  on_policy_sample=on_policy_sample)

    def test_12_bounded_moves_then_stop_and_memory(self):
        robot = self.start()
        result = self.invoke()
        self.assertEqual(WALK_TICKS, result.commands_sent)
        self.assertTrue(result.stop_confirmed)
        self.assertEqual("translation_observed", result.outcome)
        self.assertEqual("mujoco_verified_pose", result.memory_source)
        self.assertEqual(1, result.trials_in_memory)
        self.assertEqual("explore", result.next_intention)
        self.assertEqual(WALK_TICKS, result.policy_diagnostics["policy_samples"])
        self.assertEqual(WALK_TICKS, result.policy_diagnostics["walk_policy_samples"])
        self.assertAlmostEqual(.09, result.policy_diagnostics["max_applied_vx_mps"])
        self.assertGreater(result.preference_after, result.preference_before)
        self.assertEqual(WALK_TICKS+1, len(robot.requested))
        for p in robot.requested[:-1]:
            self.assertEqual("robot.move", p["method"])
            self.assertNotIn("id", p)
            self.assertEqual({"vx": WALK_SPEED_MPS, "vy": 0., "vyaw": 0.},
                             p["params"])
        self.assertEqual("robot.stop", robot.requested[-1]["method"])
        mem = ExperienceMemory(self.db)
        self.addCleanup(mem.close)
        self.assertEqual(1, len(mem.simulated_motion_history()))

    def test_baseline_drift_refuses_before_motor_connect(self):
        poses = [ground(1., .02), ground(1.3, .02+BASELINE_LIMIT_M+.001)]
        with self.assertRaisesRegex(SimMotionError, "unstable"):
            self.invoke(poses=poses)
        self.assertFalse(self.db.exists())

    def test_low_battery_refuses_without_motor(self):
        with self.assertRaisesRegex(SimMotionError, "preflight"):
            self.invoke(sensor=telemetry(battery=10.))
        self.assertFalse(self.db.exists())

    def test_wrong_simulator_scene_never_reaches_socket(self):
        with (patch("microduck_companion.sim_walk_trial._read_ground",
                    side_effect=GroundTruthError("changed scene")),
              patch("microduck_companion.sim_walk_trial.read_simulator_telemetry",
                    return_value=telemetry())):
            with self.assertRaisesRegex(SimMotionError, "baseline"):
                run_walk_trial(self.root, "/fake/rl", self.db)

    def test_health_failure_after_first_notification_stops(self):
        robot = self.start()
        with self.assertRaisesRegex(SimMotionError, "aborted"):
            self.invoke(readings=[health(), health(healthy=False)])
        self.assertEqual(["robot.move", "robot.stop"],
                         [p["method"] for p in robot.requested])
        mem = ExperienceMemory(self.db)
        self.addCleanup(mem.close)
        self.assertEqual([], mem.simulated_motion_history())

    def test_zone_change_after_first_notification_stops(self):
        robot = self.start()
        poses = [ground(1.), ground(1.3), ground(1.4),
                 ground(1.5, clearance=.2, safe=False)]
        with self.assertRaises(SimMotionError):
            self.invoke(poses=poses)
        self.assertEqual(["robot.move", "robot.stop"],
                         [p["method"] for p in robot.requested])

    def test_stop_must_be_acknowledged_before_memory_update(self):
        robot = self.start(valid_stop=False)
        with self.assertRaisesRegex(SimMotionError, "stop unconfirmed"):
            self.invoke()
        self.assertEqual("robot.stop", robot.requested[-1]["method"])
        mem = ExperienceMemory(self.db)
        self.addCleanup(mem.close)
        self.assertEqual([], mem.simulated_motion_history())

    def test_implausible_pose_jump_rejected(self):
        robot = self.start()
        poses = [ground(1+i*.1, .02+i*.001)
                 for i in range(WALK_TICKS+4)]
        poses[WALK_TICKS+2] = ground(5., .7)
        with self.assertRaisesRegex(SimMotionError, "implausible"):
            self.invoke(poses=poses)
        self.assertEqual("robot.stop", robot.requested[-1]["method"])

    def test_live_policy_deadman_flag_prevents_learning(self):
        robot = self.start()
        class DeadmanPolicyStream(FakePolicyStream):
            def next_notification(self):
                note = super().next_notification()
                note.params["move"]["limited_by"] = ["deadman"]
                return note
        result = self.invoke(policy_stream_cls=DeadmanPolicyStream)
        self.assertTrue(result.stop_confirmed)
        self.assertEqual("inconclusive_control_limit", result.outcome)
        self.assertIsNone(result.reward)
        self.assertEqual(0., result.preference_after)
        self.assertEqual(["deadman"], result.policy_diagnostics["limited_by"])
        self.assertEqual("robot.stop", robot.requested[-1]["method"])

    def test_no_progress_is_recorded_without_positive_reward(self):
        robot = self.start()
        poses = [ground(1+i*.1, .02 + i*.00001)
                 for i in range(WALK_TICKS+4)]
        result = self.invoke(poses=poses)
        self.assertEqual("no_progress_observed", result.outcome)
        self.assertEqual(-.5, result.reward)
        self.assertLess(result.preference_after, 0)
        self.assertEqual("robot.stop", robot.requested[-1]["method"])

    def test_unsafe_final_pose_is_recorded_as_unverified(self):
        robot = self.start()
        poses = [ground(1+i*.1, .02 + i*.001)
                 for i in range(WALK_TICKS+4)]
        poses[WALK_TICKS+2] = ground(5., .04, safe=False)
        poses[WALK_TICKS+3] = ground(5.1, .04, safe=False)
        result = self.invoke(poses=poses)
        self.assertEqual("unverified", result.outcome)
        self.assertIsNone(result.reward)
        self.assertEqual(0, result.preference_after)

    def test_learned_idle_prevents_another_trial(self):
        mem = ExperienceMemory(self.db)
        for _ in range(10):
            mem.record_simulated_motion(
                measured_m=.0001, baseline_m=.0001,
                simulated_duration_s=1.,
                stop_confirmed=True, healthy_after=True, safe_after=True,
            )
        mem.close()
        poses = [ground(1.), ground(1.3)]
        with self.assertRaisesRegex(SimMotionError, "rest"):
            self.invoke(poses=poses)

    def test_lost_policy_stream_stops_motion_and_prevents_learning(self):
        robot = self.start()
        class OnePolicyFrame(FakePolicyStream):
            def next_notification(self):
                if self.calls:
                    raise TelemetryError("robot.state stream lost")
                return super().next_notification()
        with (patch("microduck_companion.sim_walk_trial.ReadOnlyUnixRpc",
                    OnePolicyFrame),
              patch("microduck_companion.sim_walk_trial._read_ground",
                    side_effect=[ground(1.), ground(1.3), ground(1.4), ground(1.5)]),
              patch("microduck_companion.sim_walk_trial.read_health",
                    side_effect=[health(), health()]),
              patch("microduck_companion.sim_walk_trial.read_simulator_telemetry",
                    return_value=telemetry()),
              patch("microduck_companion.sim_walk_trial.time.sleep")):
            with self.assertRaisesRegex(SimMotionError, "aborted"):
                run_walk_trial(self.root, "/fake/rl", self.db)
        self.assertEqual(["robot.move", "robot.move", "robot.stop"],
                         [p["method"] for p in robot.requested])
        mem = ExperienceMemory(self.db)
        self.addCleanup(mem.close)
        self.assertEqual([], mem.simulated_motion_history())

    def test_p0b_passive_hook_receives_all_policy_samples(self):
        robot = self.start()
        observed = []
        result = self.invoke(on_policy_sample=observed.append)
        self.assertTrue(result.stop_confirmed)
        self.assertEqual(WALK_TICKS, len(observed))
        self.assertTrue(all(note.policy == 'walk' for note in observed))
        self.assertEqual('robot.stop', robot.requested[-1]['method'])

    def test_p0b_passive_read_failure_stops_and_prevents_memory_write(self):
        robot = self.start()
        def failed_read(_sample):
            raise GroundTruthError('pinned simulator body read lost')
        with self.assertRaisesRegex(SimMotionError, 'aborted'):
            self.invoke(on_policy_sample=failed_read)
        self.assertEqual(['robot.move', 'robot.stop'],
                         [p['method'] for p in robot.requested])
        mem = ExperienceMemory(self.db)
        self.addCleanup(mem.close)
        self.assertEqual([], mem.simulated_motion_history())

    def test_p0b_passive_policy_alignment_failure_stops(self):
        robot = self.start()
        def failed_alignment(_sample):
            raise TelemetryError('policy observation misaligned')
        with self.assertRaisesRegex(SimMotionError, 'aborted'):
            self.invoke(on_policy_sample=failed_alignment)
        self.assertEqual(['robot.move', 'robot.stop'],
                         [p['method'] for p in robot.requested])

    def test_cli_demands_explicit_enable(self):
        with patch.dict("os.environ", {}, clear=True):
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(2, main([]))
            self.assertIn("disabled", output.getvalue())


if __name__ == "__main__":
    unittest.main()
