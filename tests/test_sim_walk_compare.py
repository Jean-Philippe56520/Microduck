"""P0b stand/walk comparison: same-scene metrics are NOT gait validation."""
import contextlib
import io
import math
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from microduck_companion.sim_flat_zone import GroundTruthError
from microduck_companion.sim_joint_trace import JOINT_COUNT, _summarize
from microduck_companion.sim_motion import SimMotionError
from microduck_companion.sim_policy_trace import PolicySample
from microduck_companion.sim_walk_compare import (
    REST_SAMPLES, SAMPLE_HZ, _checked_reference, compare_observed_states,
    main, run_comparison,
)
from microduck_companion.sim_walk_trial import (
    WALK_SPEED_MPS, WALK_TICKS, WalkTrialResult,
)


def observed(t, x, leg_rad=0., policy="stand"):
    positions = [0.] * JOINT_COUNT
    positions[3] = leg_rad
    requested = [0., 0., 0.] if policy == "stand" else [WALK_SPEED_MPS, 0., 0.]
    return {
        "observed_monotonic_s": time.monotonic(),
        "sim_time_s": t,
        "trunk_xyz_m": [x, 0.01, .115],
        "flat_scene_safe_area": True,
        "positions_rad": positions,
        "velocities_rad_s": [0.] * JOINT_COUNT,
        "reported_currents_ma_proxy": [0.] * JOINT_COUNT,
        "foot_contacts": None,
        "joint_targets_rad": None,
        "policy_skew_s": 0.,
        "robotd": {
            "policy": policy,
            "requested_vx_vy_mps_vyaw_rad_s": requested,
            "applied_vx_vy_mps_vyaw_rad_s": requested,
            "limited_by": ["deadman"] if policy == "stand" else [],
        },
    }


def policies(n, name):
    v = 0. if name == "stand" else WALK_SPEED_MPS
    return [
        PolicySample(name, (v, 0., 0.), (v, 0., 0.), (), time.monotonic())
        for _ in range(n)
    ]


def baseline(*, offset=0.0002):
    samples = [observed(1 + i*.1, i*offset/(REST_SAMPLES-1))
               for i in range(REST_SAMPLES)]
    return {
        "mode": "passive_read_only",
        "source": "pinned_official_mujoco_body_and_robotd",
        "foot_contacts_available": False,
        "joint_targets_available": False,
        "observations": samples,
        "summary": _summarize(samples, policies(REST_SAMPLES, "stand")),
    }


def walk_trial(*, stop=True, outcome="no_progress_observed", count=WALK_TICKS):
    return WalkTrialResult(
        commands_sent=count, stop_confirmed=stop,
        requested_speed_mps=WALK_SPEED_MPS,
        measured_displacement_m=.0012, baseline_displacement_m=.0002,
        simulated_duration_s=2.4, measured_forward_x_m=.0012,
        measured_lateral_y_m=0., outcome=outcome, reward=-.5,
        preference_before=0., preference_after=-.075,
        next_intention="explore", trials_in_memory=1,
        memory_source="mujoco_verified_pose", policy_diagnostics={},
    )


def walking():
    return [
        observed(3 + i*.1, .02 + i*.00005,
                 .03 if i % 2 else -.03, "walk")
        for i in range(WALK_TICKS)
    ]


class CompareTests(unittest.TestCase):
    def test_valid_stand_reference(self):
        _checked_reference(baseline())

    def test_reject_stand_reference_drift_and_missing_samples(self):
        bad = baseline(offset=.012)
        with self.assertRaisesRegex(SimMotionError, "unstable"):
            _checked_reference(bad)
        bad = baseline()
        bad["observations"].pop()
        with self.assertRaisesRegex(SimMotionError, "incomplete"):
            _checked_reference(bad)

    def test_reject_wrong_policy_or_unsafe_stand_reference(self):
        bad = baseline()
        bad["summary"]["robotd_policy"]["walk_policy_samples"] = 1
        with self.assertRaisesRegex(SimMotionError, "non-stand"):
            _checked_reference(bad)
        bad = baseline()
        bad["observations"][3]["flat_scene_safe_area"] = False
        with self.assertRaisesRegex(SimMotionError, "unsafe"):
            _checked_reference(bad)

    def test_reject_unverified_or_false_baseline_provenance(self):
        for key, value in (
            ("source", "fake_scene"),
            ("mode", "not_passive"),
            ("foot_contacts_available", True),
            ("joint_targets_available", True),
        ):
            bad = baseline()
            bad[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                    SimMotionError, "provenance"):
                _checked_reference(bad)

    def test_reject_nonfinite_or_missing_displacement(self):
        for value in (None, True, math.nan, math.inf, -.1):
            bad = baseline()
            bad["summary"]["net_trunk_xy_displacement_m"] = value
            with self.subTest(value=value), self.assertRaises(SimMotionError):
                _checked_reference(bad)

    def test_no_progress_with_leg_motion_does_not_claim_walking(self):
        trial = walk_trial()
        trace = compare_observed_states(
            baseline(), walking(), policies(WALK_TICKS, "walk"), trial,
        )
        self.assertFalse(trace["gait_validated"])
        self.assertFalse(trace["traction_proven"])
        self.assertEqual("unknown", trace["locomotion_root_cause"])
        self.assertTrue(trace["leg_joint_motion_sampled"])
        self.assertTrue(trace["walk_policy_sampled"])
        self.assertIs(trace["stop_confirmed"], True)
        self.assertEqual(WALK_TICKS, trace["motion_commands_sent_by_existing_j2e_trial"])
        self.assertAlmostEqual(.06, trace["walk_trace"]["summary"]
                               ["joint_position_range_rad"]["left_knee"])
        self.assertEqual(REST_SAMPLES + WALK_TICKS,
                         trace["read_only_joint_samples"])

    def test_not_raising_false_success_even_with_translation(self):
        trace = compare_observed_states(
            baseline(), walking(), policies(WALK_TICKS, "walk"),
            walk_trial(outcome="translation_observed"),
        )
        self.assertFalse(trace["gait_validated"])
        self.assertEqual("unknown", trace["locomotion_root_cause"])

    def test_stop_and_full_trace_required(self):
        for trial in (walk_trial(stop=False), walk_trial(count=WALK_TICKS-1)):
            with self.subTest(trial=trial), self.assertRaises(SimMotionError):
                compare_observed_states(
                    baseline(), walking(), policies(WALK_TICKS, "walk"), trial,
                )
        with self.assertRaisesRegex(SimMotionError, "incomplete"):
            compare_observed_states(
                baseline(), walking()[:-1],
                policies(WALK_TICKS-1, "walk"), walk_trial(),
            )

    def test_single_walk_trial_reuses_existing_policy_and_checks_read_frames(self):
        stand = baseline()
        frames = [
            ({
                "trunk": [.02, .01, .115], "sim_time": 3+i*.1,
                "imu": {"gravity": [0., 0., -1.]},
                "positions": [0.] * 15, "velocities": [.01] * 15,
                "currents_ma": [1.] * 15,
            }, time.monotonic())
            for i in range(WALK_TICKS)
        ]
        def simulate_one_trial(*args, **kwargs):
            hook = kwargs["on_policy_sample"]
            for p in policies(WALK_TICKS, "walk"):
                hook(p)
            return walk_trial()
        with (patch("microduck_companion.sim_walk_compare.collect_joint_trace",
                    return_value=stand) as passive,
              patch("microduck_companion.sim_walk_compare.read_verified_body_state",
                    side_effect=frames) as body,
              patch("microduck_companion.sim_walk_compare.run_walk_trial",
                    side_effect=simulate_one_trial) as trial):
            got = run_comparison("/fake/state", "/fake/rl", "/fake/db", port=17801)
        passive.assert_called_once_with(
            "/fake/state", "/fake/rl", port=17801,
            samples=REST_SAMPLES, hz=SAMPLE_HZ,
        )
        trial.assert_called_once()
        self.assertEqual(WALK_TICKS, body.call_count)
        self.assertEqual(0, got["walk_trace"]["summary"]["joint_position_range_rad"]
                         ["left_knee"])
        self.assertFalse(got["leg_joint_motion_sampled"])

    def test_invalid_verified_body_frame_stops_diagnostic(self):
        with (patch("microduck_companion.sim_walk_compare.collect_joint_trace",
                    return_value=baseline()),
              patch("microduck_companion.sim_walk_compare.read_verified_body_state",
                    side_effect=GroundTruthError("tampered scene")),
              patch("microduck_companion.sim_walk_compare.run_walk_trial",
                    side_effect=lambda *a, **kw: kw["on_policy_sample"](
                        policies(1, "walk")[0])),
              self.assertRaisesRegex(GroundTruthError, "tampered")):
            run_comparison("/fake/state", "/fake/rl", "/fake/db")

    def test_incorrect_baseline_never_calls_motor_trial(self):
        with (patch("microduck_companion.sim_walk_compare.collect_joint_trace",
                    return_value=baseline(offset=.02)),
              patch("microduck_companion.sim_walk_compare.run_walk_trial") as move,
              self.assertRaises(SimMotionError)):
            run_comparison("/fake/state", "/fake/rl", "/fake/db")
        move.assert_not_called()

    def test_cli_refuses_without_double_opt_in(self):
        with (patch.dict("os.environ", {}, clear=True),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(2, main(["--state-dir", "/fake",
                                      "--rl-root", "/fake",
                                      "--memory", "/fake/db",
                                      "--output", "/fake/out.json",
                                      "--enable-once"]))

    def test_cli_negative_result_returns_diagnostic_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "walk.json"
            with (patch.dict("os.environ",
                             {"MICRODUCK_SIM_WALK_COMPARE": "YES"}),
                  patch("microduck_companion.sim_walk_compare.run_comparison",
                        return_value=compare_observed_states(
                            baseline(), walking(),
                            policies(WALK_TICKS, "walk"), walk_trial())),
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(3, main(["--state-dir", tmp,
                                          "--rl-root", tmp,
                                          "--memory", str(Path(tmp)/"mem.sqlite"),
                                          "--output", str(path),
                                          "--enable-once"]))
            self.assertTrue(path.exists())
            self.assertIn('"locomotion_root_cause": "unknown"', path.read_text())


if __name__ == "__main__":
    unittest.main()
