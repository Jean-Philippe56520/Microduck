"""Read-only robotd command/policy diagnostics; cannot authorize movement."""
import math
import unittest

from microduck_companion.sim_ipc import Notification, TelemetryError
from microduck_companion.sim_policy_trace import (
    parse_policy_sample, summarize_policy_samples,
)


def state(*, policy="walk", requested=None, applied=None, limited_by=None):
    return Notification(
        "robot.state",
        {"policy": policy, "move": {
            "requested": [.12, 0., 0.] if requested is None else requested,
            "applied": [.08, 0., 0.] if applied is None else applied,
            "limited_by": [] if limited_by is None else limited_by,
        }},
        31.25,
    )


class PolicyTraceTests(unittest.TestCase):
    def test_valid_policy_and_applied_command(self):
        sample = parse_policy_sample(state())
        self.assertEqual("walk", sample.policy)
        self.assertEqual((.12, 0., 0.), sample.requested)
        self.assertEqual((.08, 0., 0.), sample.applied)
        self.assertEqual(31.25, sample.received_at)

    def test_standing_network_is_not_called_walking(self):
        samples = [parse_policy_sample(state(policy="stand")),
                   parse_policy_sample(state(policy="walk")),
                   parse_policy_sample(state(policy="held"))]
        rollup = summarize_policy_samples(samples)
        self.assertEqual(3, rollup["policy_samples"])
        self.assertEqual(1, rollup["walk_policy_samples"])
        self.assertEqual(1, rollup["stand_policy_samples"])
        self.assertEqual(1, rollup["held_policy_samples"])
        self.assertEqual(.08, rollup["max_applied_vx_mps"])

    def test_motion_limitations_are_reported_not_silenced(self):
        samples = [
            parse_policy_sample(state(limited_by=["deadman", "fall"])),
            parse_policy_sample(state(limited_by=["deadman"])),
        ]
        self.assertEqual(["deadman", "fall"],
                         summarize_policy_samples(samples)["limited_by"])

    def test_empty_stream_has_explicit_no_data(self):
        rollup = summarize_policy_samples([])
        self.assertEqual(0, rollup["policy_samples"])
        self.assertEqual(0., rollup["max_applied_vx_mps"])

    def test_missing_required_telemetry_fails_closed(self):
        for data in (
            {"policy": "walk"},
            {"policy": "", "move": {"requested": [0., 0., 0.],
                                    "applied": [0., 0., 0.]}},
            {"policy": "walk", "move": {"requested": [0., 0., 0.]}},
            {"policy": "walk", "move": {"requested": [0., 0., 0.],
                                       "applied": [0., 0., 0.], "limited_by": "fall"}},
        ):
            with self.subTest(data=data), self.assertRaises(TelemetryError):
                parse_policy_sample(Notification("robot.state", data, 1.))

    def test_nonfinite_and_incorrect_vector_rejected(self):
        for value in ([math.nan, 0., 0.], [float("inf"), 0., 0.],
                      [True, 0., 0.], [0., 0.], "none"):
            with self.subTest(value=value), self.assertRaises(TelemetryError):
                parse_policy_sample(state(applied=value))

    def test_method_is_strictly_robot_state(self):
        note = state()
        with self.assertRaises(TelemetryError):
            parse_policy_sample(Notification("tof.frame", note.params, 1.))


if __name__ == "__main__":
    unittest.main()
