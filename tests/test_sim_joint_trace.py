"""P0a joint trace: fail-closed parsing and passive-only data collection."""
import math
import time
import unittest
from unittest.mock import patch

from microduck_companion.sim_flat_zone import GroundTruthError
from microduck_companion.sim_ipc import Notification, TelemetryError
from microduck_companion.sim_joint_trace import (
    JOINT_COUNT, JOINT_NAMES, MAX_SAMPLES, collect_joint_trace,
    parse_joint_observation,
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

    def test_bounds_prevent_unlimited_trace(self):
        for n in (0, True, -1, MAX_SAMPLES + 1):
            with self.subTest(samples=n), self.assertRaises(ValueError):
                collect_joint_trace("/tmp", "/tmp", samples=n)
        for hz in (0, True, -1, 11):
            with self.subTest(hz=hz), self.assertRaises(ValueError):
                collect_joint_trace("/tmp", "/tmp", hz=hz)


if __name__ == "__main__":
    unittest.main()
