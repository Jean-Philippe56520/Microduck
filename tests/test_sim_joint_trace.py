"""P0a joint trace: fail-closed parsing and passive-only data collection."""
import math
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from microduck_companion.sim_flat_zone import GroundTruthError
from microduck_companion.sim_ipc import Notification, TelemetryError
from microduck_companion.sim_joint_trace import (
    JOINT_COUNT, JOINT_NAMES, MAX_SAMPLES, collect_joint_trace,
    parse_joint_observation, parse_robotd_joint_tracking,
)


def body(sim_time=3., x=0.02, *, positions=None):
    return {
        "trunk": [x, 0.01, 0.115],
        "sim_time": sim_time,
        "imu": {"gravity": [0., 0., -1.]},
        "positions": [0.] * JOINT_COUNT if positions is None else positions,
        "velocities": [.05] * JOINT_COUNT,
        "currents_ma": [12.] * JOINT_COUNT,
    }


class FakeReadOnlyStream:
    calls = []

    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def request(self, method, *, hz):
        self.calls.append((method, hz))
        if method != "robot.subscribe":
            raise AssertionError("P0a must not send motor or other RPC commands")
        return {"accepted": True}

    def next_notification(self):
        return Notification(
            "robot.state",
            {"policy": "stand", "move": {
                "requested": [0., 0., 0.],
                "applied": [0., 0., 0.],
                "limited_by": ["deadman"],
            }},
            time.monotonic(),
        )


class JointTraceTests(unittest.TestCase):
    def setUp(self):
        FakeReadOnlyStream.calls = []

    def _capture(self, states, *, samples=2):
        frames = [(p, time.monotonic()) for p in states]
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    FakeReadOnlyStream),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    side_effect=frames) as reader,
              patch("microduck_companion.sim_joint_trace.time.sleep")):
            trace = collect_joint_trace("/tmp/fake", "/tmp/pinned", samples=samples)
        self.assertEqual(samples, reader.call_count)
        return trace

    def test_14_actuated_joints_plus_unactuated_mouth(self):
        entry = parse_joint_observation(body(), 25.)
        self.assertEqual(15, len(JOINT_NAMES))
        self.assertEqual("mouth", JOINT_NAMES[9])
        self.assertEqual(15, len(entry["positions_rad"]))
        self.assertEqual([12.] * 15, entry["reported_currents_ma_proxy"])
        self.assertIsNone(entry["foot_contacts"])
        self.assertIsNone(entry["joint_targets_rad"])

    def test_oem_quaternion_is_preserved_or_explicitly_unknown(self):
        no_orientation = parse_joint_observation(body(), 25.)
        self.assertIsNone(no_orientation["trunk_quat_wxyz"])
        with_orientation = body()
        with_orientation["imu"]["quat"] = [1., 0., 0., 0.]
        self.assertEqual([1., 0., 0., 0.],
                         parse_joint_observation(with_orientation, 25.)
                         ["trunk_quat_wxyz"])

    def test_oem_quaternion_invalid_values_fail_closed(self):
        for quat in ([0., 0., 0., 0.], [2., 0., 0., 0.],
                     [1., False, 0., 0.], [float("inf"), 0., 0., 0.],
                     [1., 0., 0.], "upright"):
            with self.subTest(quat=quat):
                payload = body()
                payload["imu"]["quat"] = quat
                with self.assertRaises(GroundTruthError):
                    parse_joint_observation(payload, 25.)

    def test_reject_missing_wrong_length_nonfinite_or_boolean_joint_values(self):
        for field in ("positions", "velocities", "currents_ma"):
            for val in (None, [0.] * 14, [True] * 15,
                        [math.inf] * 15, [math.nan] * 15, "not an array"):
                bad = body()
                bad[field] = val
                with self.subTest(field=field, val=str(val)[:20]):
                    with self.assertRaises(GroundTruthError):
                        parse_joint_observation(bad, 25.)
        bad = body()
        bad["currents_ma"][1] = -1
        with self.assertRaises(GroundTruthError):
            parse_joint_observation(bad, 25.)

    def test_reject_invalid_pose_and_simulator_time(self):
        for key, value in (("trunk", [0., 0.]), ("sim_time", float("nan")),
                           ("imu", {})):
            bad = body()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(GroundTruthError):
                parse_joint_observation(bad, 25.)

    def test_passive_trace_records_policy_pose_and_joint_ranges(self):
        p = [0.] * 15
        q = [0.] * 15
        q[3] = .2
        trace = self._capture([
            body(3., positions=p),
            body(3.2, x=.023, positions=q),
        ])
        self.assertEqual("passive_read_only", trace["mode"])
        self.assertEqual(0, trace["commands_sent"])
        self.assertEqual([("robot.subscribe", 5)], FakeReadOnlyStream.calls)
        self.assertEqual(2, trace["summary"]["sample_count"])
        self.assertAlmostEqual(.003, trace["summary"]["net_trunk_xy_displacement_m"])
        self.assertAlmostEqual(.2, trace["summary"]["joint_position_range_rad"]["left_knee"])
        self.assertEqual(2, trace["summary"]["robotd_policy"]["stand_policy_samples"])
        self.assertFalse(trace["foot_contacts_available"])
        self.assertFalse(trace["joint_targets_available"])
        self.assertIsNone(trace["summary"]["gait_contact_evidence"])
        self.assertFalse(trace["summary"]["locomotion_validated"])

    def test_non_increasing_sim_time_is_rejected(self):
        with self.assertRaisesRegex(GroundTruthError, "clock"):
            self._capture([body(3.), body(3.)])

    def test_modified_scene_or_unverifiable_process_fails_without_movement(self):
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    FakeReadOnlyStream),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    side_effect=GroundTruthError("pinned scene missing")),
              self.assertRaisesRegex(GroundTruthError, "pinned scene")):
            collect_joint_trace("/tmp/fake", "/tmp/unknown", samples=1)
        self.assertEqual([("robot.subscribe", 5)], FakeReadOnlyStream.calls)

    def test_stale_or_future_robotd_policy_notification_is_rejected(self):
        class StaleStream(FakeReadOnlyStream):
            def next_notification(self):
                note = super().next_notification()
                return Notification(note.method, note.params, note.received_at - 5)
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    StaleStream),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    return_value=(body(), time.monotonic())),
              self.assertRaisesRegex(TelemetryError, "time-aligned")):
            collect_joint_trace("/tmp/fake", "/tmp/pinned", samples=1)

    def test_malformed_policy_is_rejected(self):
        class InvalidStream(FakeReadOnlyStream):
            def next_notification(self):
                return Notification("robot.state", {"policy": "stand"}, time.monotonic())
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    InvalidStream),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    return_value=(body(), time.monotonic())),
              self.assertRaises(TelemetryError)):
            collect_joint_trace("/tmp/fake", "/tmp/pinned", samples=1)

    def test_verified_viewer_passes_explicit_opt_in_only(self):
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    FakeReadOnlyStream),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    return_value=(body(), time.monotonic())) as reader):
            trace = collect_joint_trace("/tmp/fake", "/tmp/pinned", samples=1,
                                        verified_viewer=True)
        self.assertTrue(trace["verified_viewer_opt_in"])
        reader.assert_called_once_with(Path("/tmp/fake"), "/tmp/pinned", port=17801,
                                       allow_viewer=True)
        self.assertEqual(0, trace["commands_sent"])

    def test_non_boolean_viewer_opt_in_is_rejected(self):
        with self.assertRaises(ValueError):
            collect_joint_trace("/tmp", "/tmp", verified_viewer="yes")


    def _tracking_capture(self, stream_type, states=None):
        states = states or [body(3.), body(3.2, x=.021)]
        frames = [(p, time.monotonic()) for p in states]
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    stream_type),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    side_effect=frames) as reader,
              patch("microduck_companion.sim_joint_trace.time.sleep")):
            result = collect_joint_trace("/tmp/fake", "/tmp/pinned",
                                         samples=len(states), joint_tracking=True)
        self.assertEqual(len(states), reader.call_count)
        self.assertEqual([("robot.subscribe", 5)], FakeReadOnlyStream.calls)
        return result

    def test_optional_robotd_target_tracking_same_tick_and_no_motor(self):
        class TrackingStream(FakeReadOnlyStream):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.count = 0

            def request(self, method, *, hz):
                super().request(method, hz=hz)
                return {"accepted": True, "walk": "alpha_walking.onnx",
                        "stand": "alpha_stand.onnx", "unavailable": None}

            def next_notification(self):
                note = super().next_notification()
                self.count += 1
                measured = [0.] * JOINT_COUNT
                targets = [0.] * JOINT_COUNT
                measured[3] = .02 * self.count
                targets[3] = .10 * self.count
                now = time.monotonic()
                payload = dict(note.params, joints=measured, targets=targets,
                               t_ns=int((now - .01) * 1_000_000_000))
                return Notification(note.method, payload, now)

        result = self._tracking_capture(TrackingStream)
        self.assertEqual(2, result["schema_version"])
        self.assertTrue(result["robotd_controller_targets_available"])
        self.assertFalse(result["joint_targets_available"])  # body_server has no data.ctrl
        self.assertEqual(0, result["commands_sent"])
        self.assertEqual("alpha_walking.onnx",
                         result["robotd_subscribed_policy_names"]["walk"])
        first = result["observations"][0]["robotd_joint_tracking"]
        self.assertAlmostEqual(.08, first["controller_target_minus_measured_rad"][3])
        self.assertTrue(first["target_before_safety_write_not_motor_effect"])
        aggregate = result["summary"]["robotd_joint_tracking"]
        self.assertEqual(2, aggregate["sample_count"])
        self.assertAlmostEqual(.10, aggregate["leg_target_range_rad"]["left_knee"])
        self.assertAlmostEqual(.02, aggregate["leg_measured_range_rad"]["left_knee"])
        self.assertAlmostEqual(.16,
                               aggregate["leg_peak_abs_target_minus_measured_rad"]["left_knee"])
        self.assertFalse(aggregate["motor_write_or_contact_verified"])
        self.assertFalse(aggregate["locomotion_validated"])

    def test_tracking_refuses_wrong_unavailable_or_missing_policy_identity(self):
        class WrongIdentity(FakeReadOnlyStream):
            ack = {}
            def request(self, method, *, hz):
                super().request(method, hz=hz)
                return self.ack

        for invalid in (
            {"accepted": True, "walk": "velstand.onnx",
             "stand": None, "unavailable": None},
            {"accepted": True, "walk": "alpha_walking.onnx",
             "stand": "alpha_stand.onnx", "unavailable": "load error"},
            {"accepted": True, "walk": "alpha_walking.onnx"},
            {"accepted": False, "walk": "alpha_walking.onnx",
             "stand": "alpha_stand.onnx"},
        ):
            with self.subTest(invalid=invalid):
                WrongIdentity.ack = invalid
                FakeReadOnlyStream.calls = []
                with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                            WrongIdentity),
                      patch("microduck_companion.sim_joint_trace.read_verified_body_state")
                           as reader,
                      self.assertRaisesRegex(TelemetryError, "policy differs")):
                    collect_joint_trace("/tmp/fake", "/tmp/pinned",
                                        samples=1, joint_tracking=True)
                reader.assert_not_called()
                self.assertEqual([("robot.subscribe", 5)], FakeReadOnlyStream.calls)

    def test_joint_tracking_rejects_corrupt_missing_or_stale_oem_frame(self):
        now = time.monotonic()
        valid = Notification("robot.state", {
            "t_ns": int((now - .01) * 1_000_000_000),
            "joints": [0.] * JOINT_COUNT,
            "targets": [.2] * JOINT_COUNT,
        }, now)
        self.assertAlmostEqual(.2,
                               parse_robotd_joint_tracking(valid, now)
                               ["controller_target_minus_measured_rad"][0])
        for key, value in (
            ("t_ns", None), ("t_ns", True),
            ("t_ns", int((now - 5) * 1_000_000_000)),
            ("t_ns", int((now + 5) * 1_000_000_000)),
            ("targets", None), ("targets", [0.] * 14),
            ("targets", [float("nan")] * JOINT_COUNT),
            ("joints", [float("inf")] * JOINT_COUNT),
            ("joints", [True] * JOINT_COUNT),
        ):
            with self.subTest(field=key, value=str(value)[:30]):
                broken = dict(valid.params, **{key: value})
                with self.assertRaises(TelemetryError):
                    parse_robotd_joint_tracking(
                        Notification("robot.state", broken, now), now)
        with self.assertRaises(TelemetryError):
            parse_robotd_joint_tracking(
                Notification("tof.frame", valid.params, now), now)
        with self.assertRaisesRegex(TelemetryError, "too far apart"):
            parse_robotd_joint_tracking(valid, now - 1.0)

    def test_tracking_rejects_repeated_tick_and_unknown_skill(self):
        class DuplicateTick(FakeReadOnlyStream):
            def __init__(self, *args, **kwargs):
                self.same_ns = int((time.monotonic() - .02) * 1_000_000_000)
            label = "walk"

            def request(self, method, *, hz):
                super().request(method, hz=hz)
                return {"accepted": True, "walk": "alpha_walking.onnx",
                        "stand": "alpha_stand.onnx"}

            def next_notification(self):
                note = super().next_notification()
                params = dict(note.params, policy=self.label,
                              t_ns=self.same_ns, joints=[0.] * JOINT_COUNT,
                              targets=[.1] * JOINT_COUNT)
                return Notification("robot.state", params, time.monotonic())

        frames = [(body(3.), time.monotonic()),
                  (body(3.2), time.monotonic())]
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    DuplicateTick),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    side_effect=frames),
              patch("microduck_companion.sim_joint_trace.time.sleep"),
              self.assertRaisesRegex(TelemetryError, "did not advance")):
            collect_joint_trace("/tmp/fake", "/tmp/pinned",
                                samples=2, joint_tracking=True)
        DuplicateTick.label = "ground_pick"
        with (patch("microduck_companion.sim_joint_trace.ReadOnlyUnixRpc",
                    DuplicateTick),
              patch("microduck_companion.sim_joint_trace.read_verified_body_state",
                    return_value=(body(), time.monotonic())),
              self.assertRaisesRegex(TelemetryError, "unexpected active OEM skill")):
            collect_joint_trace("/tmp/fake", "/tmp/pinned",
                                samples=1, joint_tracking=True)

    def test_joint_tracking_opt_in_must_be_boolean(self):
        for wrong in ("yes", 1, None, []):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                collect_joint_trace("/tmp/fake", "/tmp/pinned",
                                    joint_tracking=wrong)

    def test_bounds_prevent_unlimited_trace(self):
        for n in (0, True, -1, MAX_SAMPLES + 1):
            with self.subTest(samples=n), self.assertRaises(ValueError):
                collect_joint_trace("/tmp", "/tmp", samples=n)
        for hz in (0, True, -1, 11):
            with self.subTest(hz=hz), self.assertRaises(ValueError):
                collect_joint_trace("/tmp", "/tmp", hz=hz)


if __name__ == "__main__":
    unittest.main()
